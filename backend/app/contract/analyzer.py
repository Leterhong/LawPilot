"""合同 AI 分析编排（Step3 落地）。

职责：给定已解析的合同（``Contract``，含 ``full_text`` / ``ocr_text``），扇出多个
``AIManager`` feature 完成：

1. **综合审查** ``contract_review``（json_mode）
   → 风险清单（contract_risks）、风险总分/等级（contracts.risk_score/risk_level）、
     摘要（summary）、涉及法律（law_involved）、霸王条款（king_clauses）、
     付款/违约/赔偿责任（payment/breach/liability_risk）、检查清单（checklist）。
2. **逐条款解释** ``law_explain``（json_mode）
   → 为每个条款生成 explanation / risk_note / suggested_version，写入 contract_clauses。

设计要点（与项目「统一调用规范」「优雅降级」一致）：
- 所有 AI 调用失败（无 key / 401 / 超时）均不抛异常，降级为「结构化解 + 空结果」，
  合同状态仍记为 ``analyzed``，并在 ``analysis_meta`` 标注 ``ai_available``，
  便于前端友好提示「当前未配置 AI 模型」。
- 真实 key 时通过 ``AIManager.chat_model`` 取详细 token / 延迟用于可追溯；
  未配置路由规则时回退 ``AIManager.chat``（settings 回退，仅拿文本）。
- 条款切分采用启发式正则（中文合同常见「第一条 / 1. / 一、」），AI 不可用时仍能
  产出条款骨架（无解释），Clause Analyzer 不会空转。
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import (
    CONTRACT_RISK_CATEGORIES,
    CONTRACT_RISK_LEVELS,
    Contract,
    ContractClause,
    ContractRisk,
)
from app.services.ai.manager import AIManager

# 单次喂给模型的最大正文字符数（超出截断，避免超 token 限制）
_MAX_REVIEW_TEXT = 12000
_CLAUSE_TEXT_LIMIT = 4000
_MAX_CLAUSES = 80

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
_SYSTEM_REVIEW = (
    "你是一位资深的中国执业律师，擅长合同审查与风险识别。用户会提供一份合同的标题、"
    "类型与正文。请严格按下面的 JSON Schema 输出审查结果，不要输出任何多余文字、"
    "不要使用 Markdown 代码块：\n"
    "{\n"
    '  "summary": "一句话合同摘要（<60字）",\n'
    '  "risk_score": 0-100 的整数（综合风险分，越高越危险）,\n'
    '  "risk_level": "low" | "medium" | "high",\n'
    '  "law_involved": [{"law_id":"法律ID","name":"法律名称","article":"条款","url":null}],\n'
    '  "risks": [\n'
    '    {"clause_ref":"第X条","clause_text":"风险条款原文","category":"风险分类",'
    '"risk_level":"low|medium|high","score":0-100,"reason":"风险原因",'
    '"suggestion":"修改建议","suggested_text":"推荐条款表述","king_clause":false}\n'
    "  ],\n"
    '  "king_clauses": [{"clause":"条款原文","reason":"为何是霸王条款","suggestion":"修改建议"}],\n'
    '  "payment_risk": {"level":"low|medium|high","detail":"付款相关风险","suggestion":"建议"},\n'
    '  "breach_risk": {"level":"low|medium|high","detail":"违约相关风险","suggestion":"建议"},\n'
    '  "liability_risk": {"level":"low|medium|high","detail":"赔偿责任风险","suggestion":"建议"},\n'
    '  "checklist": [{"item":"签署前需确认的事项","checked":false,"category":"检查分类"}]\n'
    "}\n"
    "风险分类只能从以下枚举中选："
    + "、".join(CONTRACT_RISK_CATEGORIES)
    + "。若合同未涉及某类风险，对应字段可省略或给空数组/空对象。"
)

_SYSTEM_EXPLAIN = (
    "你是一位资深的中国执业律师。用户会提供一份合同的若干关键条款（JSON 数组，"
    "每项含 clause_no、section、clause_text）。请对**每一条**给出通俗解释、风险点"
    "与修改建议，严格按输入顺序返回 JSON：\n"
    '{"clauses":[{"clause_no":"与输入一致","explanation":"这条在说什么（通俗）",'
    '"risk_level":"low|medium|high","risk_note":"有什么风险","suggested_version":"推荐修改表述"}]}'
    "\n不要输出多余文字，不要使用 Markdown 代码块。"
)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def _safe_json(text: str | None) -> dict | None:
    """从模型输出中尽量解析出 JSON 对象（兼容包裹了代码块或多余文字的情况）。"""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        # 去掉 ```json ... ``` 包裹
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


def _clamp_level(val: Any, default: str = "medium") -> str:
    if val in CONTRACT_RISK_LEVELS:
        return val  # type: ignore[return-value]
    # 兼容中文
    cn = {"低": "low", "中": "medium", "高": "high"}
    return cn.get(str(val), default)


def _clamp_score(val: Any) -> int:
    try:
        v = int(val)
    except Exception:
        return 0
    return max(0, min(100, v))


def _clamp_category(val: Any) -> str:
    if val in CONTRACT_RISK_CATEGORIES:
        return val  # type: ignore[return-value]
    return "other"


def split_clauses(text: str) -> list[dict]:
    """启发式切分合同条款。

    识别常见中文合同条款头（第一条 / 第1条 / 1. / 1.1 / 一、 / （一）），
    将后续内容归并到该条款，直到下一个条款头。无法识别时按段落切分。
    """
    if not text:
        return []
    lines = text.splitlines()
    # 条款头正则
    header_re = re.compile(
        r"^\s*(?:"
        r"第[一二三四五六七八九十百千0-9]+[条章节款]"
        r"|[0-9]+(?:\.[0-9]+)+"
        r"|[0-9]+[.、．]"
        r"|[一二三四五六七八九十]+[、．.]"
        r"|（[一二三四五六七八九十]+）"
        r")\s*"
    )

    blocks: list[dict] = []
    current: dict | None = None
    buf: list[str] = []

    def _flush() -> None:
        nonlocal current, buf
        if current is not None:
            body = "\n".join(buf).strip()
            if body:
                current["clause_text"] = body[:_CLAUSE_TEXT_LIMIT]
                blocks.append(current)
        current = None
        buf = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current is not None:
                buf.append(line)
            continue
        m = header_re.match(stripped)
        if m:
            _flush()
            head = stripped[: m.end()].strip()
            # 头作为 clause_no，剩余文本并入 body
            rest = stripped[m.end():].strip()
            current = {
                "clause_no": head,
                "section": None,
                "clause_text": "",
            }
            buf = [rest] if rest else []
        else:
            if current is None:
                # 还没有遇到任何条款头：按段落累积为无编号条款
                if blocks and blocks[-1].get("_loose"):
                    blocks[-1]["clause_text"] = (
                        (blocks[-1]["clause_text"] or "") + "\n" + stripped
                    )[:_CLAUSE_TEXT_LIMIT]
                else:
                    current = {
                        "clause_no": None,
                        "section": None,
                        "clause_text": stripped,
                        "_loose": True,
                    }
                    buf = []
                    blocks.append(current)
                    current = None
            else:
                buf.append(line)

    _flush()

    # 清理临时字段、编号、赋 order_index
    out: list[dict] = []
    for i, b in enumerate(blocks[:_MAX_CLAUSES]):
        b.pop("_loose", None)
        b["order_index"] = i
        out.append(b)
    return out


# ---------------------------------------------------------------------------
# 分析编排
# ---------------------------------------------------------------------------
async def analyze_contract(
    contract: Contract,
    db: AsyncSession,
    mgr: AIManager,
    user_id: UUID | None = None,
) -> dict:
    """对一份合同执行 AI 分析，写入 contract_risks / contract_clauses / contracts。

    返回结果摘要（供端点响应与日志）：
    ``{ai_available, risks_count, clauses_count, status, latency_ms, error}``
    """
    t0 = time.monotonic()
    text = contract.full_text or contract.ocr_text or ""

    # 先做一次启发式条款切分（无论 AI 是否可用，保证 Clause Analyzer 有骨架）
    clauses = split_clauses(text)

    review_data: dict | None = None
    explain_data: dict | None = None
    review_tokens: dict = {"in": 0, "out": 0}
    review_model_id: UUID | None = None
    explain_model_id: UUID | None = None

    # ---- 1) 综合审查：contract_review ----
    review_msgs = [
        {"role": "system", "content": _SYSTEM_REVIEW},
        {
            "role": "user",
            "content": (
                f"合同标题：{contract.title or '（无标题）'}\n"
                f"合同类型：{contract.contract_type or '未知'}\n\n"
                f"合同正文：\n{text[:_MAX_REVIEW_TEXT]}"
            ),
        },
    ]
    review_content = await _call_json(mgr, "contract_review", review_msgs, user_id)
    if review_content is not None:
        if isinstance(review_content, str):
            review_data = _safe_json(review_content)
        else:
            # ChatResult（chat_model 路径）：含 token / model 明细
            rc = review_content
            review_data = _safe_json(rc.content)
            review_tokens = {"in": rc.tokens_in or 0, "out": rc.tokens_out or 0}
            review_model_id = rc.model_id

    ai_available = review_data is not None

    # ---- 2) 逐条款解释：law_explain（仅当综合审查成功，避免无效调用） ----
    if ai_available and clauses:
        explain_msgs = [
            {"role": "system", "content": _SYSTEM_EXPLAIN},
            {
                "role": "user",
                "content": json.dumps(
                    [
                        {
                            "clause_no": c.get("clause_no"),
                            "section": c.get("section"),
                            "clause_text": c.get("clause_text", "")[:2000],
                        }
                        for c in clauses
                    ],
                    ensure_ascii=False,
                ),
            },
        ]
        explain_content = await _call_json(mgr, "law_explain", explain_msgs, user_id)
        if explain_content is not None:
            if isinstance(explain_content, str):
                explain_data = _safe_json(explain_content)
            else:
                ec = explain_content
                explain_data = _safe_json(ec.content)
                explain_model_id = getattr(ec, "model_id", None)

    # ---- 3) 写入子表（先清旧，再插新，保证可重入） ----
    await db.execute(delete(ContractRisk).where(ContractRisk.contract_id == contract.id))
    await db.execute(delete(ContractClause).where(ContractClause.contract_id == contract.id))

    risks_count = 0
    if review_data:
        risks_count = await _persist_review(db, contract, review_data)

    clauses_count = await _persist_clauses(db, contract, clauses, explain_data)

    # ---- 4) 回写 contracts 主表分析列 ----
    _apply_review_to_contract(contract, review_data)
    contract.model_id = review_model_id or explain_model_id or contract.model_id
    contract.analyzed_at = datetime.now(timezone.utc)
    contract.status = "analyzed"
    contract.analysis_meta = {
        "ai_available": ai_available,
        "review_model_id": str(review_model_id) if review_model_id else None,
        "explain_model_id": str(explain_model_id) if explain_model_id else None,
        "latency_ms": int((time.monotonic() - t0) * 1000),
    }
    if ai_available:
        cost = (review_tokens["in"] + review_tokens["out"]) / 1000.0 * 0.0  # 估算留空，成本以 model_logs 为准
        contract.token_usage = {
            "in": review_tokens["in"],
            "out": review_tokens["out"],
            "total": review_tokens["in"] + review_tokens["out"],
            "cost": cost,
            "currency": "USD",
        }
    else:
        contract.token_usage = None

    await db.flush()
    return {
        "ai_available": ai_available,
        "risks_count": risks_count,
        "clauses_count": clauses_count,
        "status": "analyzed",
        "latency_ms": int((time.monotonic() - t0) * 1000),
        "error": None if ai_available else "AI_UNAVAILABLE",
    }


async def _call_json(mgr: AIManager, feature: str, messages: list[dict], user_id: UUID | None):
    """优先按路由选模型走 chat_model（拿 token/延迟），无路由规则则回退 chat。

    返回 str（chat 路径）或 ChatResult 对象（chat_model 路径）。失败返回 None。
    """
    try:
        model = await mgr.auto_route(feature, "chat")
    except Exception:
        model = None
    try:
        if model is not None:
            return await mgr.chat_model(model.id, messages, json_mode=True, user_id=user_id)
        return await mgr.chat(feature, messages, json_mode=True, user_id=user_id)
    except Exception:
        return None


async def _persist_review(db: AsyncSession, contract: Contract, data: dict) -> int:
    """将审查 JSON 的风险清单写入 contract_risks，返回写入条数。"""
    risks = data.get("risks") or []
    if not isinstance(risks, list):
        return 0
    count = 0
    for r in risks:
        if not isinstance(r, dict):
            continue
        cat = _clamp_category(r.get("category"))
        db.add(
            ContractRisk(
                contract_id=contract.id,
                clause_ref=r.get("clause_ref"),
                clause_text=(r.get("clause_text") or "")[:4000] or None,
                category=cat,
                risk_level=_clamp_level(r.get("risk_level")),
                score=_clamp_score(r.get("score")),
                reason=r.get("reason"),
                suggestion=r.get("suggestion"),
                suggested_text=r.get("suggested_text"),
                king_clause=bool(r.get("king_clause", False)),
            )
        )
        count += 1
    await db.flush()
    return count


async def _persist_clauses(
    db: AsyncSession, contract: Contract, clauses: list[dict], explain_data: dict | None
) -> int:
    """写入 contract_clauses；若 explain_data 存在，按序把解释补回。"""
    explain_list = []
    if isinstance(explain_data, dict):
        explain_list = explain_data.get("clauses") or []
    if not isinstance(explain_list, list):
        explain_list = []

    # 用 clause_no 建索引以便对齐（AI 返回顺序大概率与输入一致，双重保险）
    by_no: dict[str, dict] = {}
    for e in explain_list:
        if isinstance(e, dict) and e.get("clause_no"):
            by_no[str(e.get("clause_no"))] = e

    count = 0
    for i, c in enumerate(clauses):
        expl = None
        if i < len(explain_list) and isinstance(explain_list[i], dict):
            expl = explain_list[i]
        elif c.get("clause_no") and str(c.get("clause_no")) in by_no:
            expl = by_no[str(c.get("clause_no"))]
        db.add(
            ContractClause(
                contract_id=contract.id,
                clause_no=c.get("clause_no"),
                section=c.get("section"),
                clause_text=c.get("clause_text"),
                category=None,
                order_index=i,
                explanation=expl.get("explanation") if expl else None,
                risk_level=_clamp_level(expl.get("risk_level")) if expl and expl.get("risk_level") else None,
                risk_note=expl.get("risk_note") if expl else None,
                suggested_version=expl.get("suggested_version") if expl else None,
            )
        )
        count += 1
    await db.flush()
    return count


def _apply_review_to_contract(contract: Contract, data: dict | None) -> None:
    """把审查结果回写到 contracts 主表的分析列（AI 不可用时保持默认/None）。"""
    if not isinstance(data, dict):
        contract.summary = contract.summary or None
        contract.risk_score = contract.risk_score or 0
        return
    contract.summary = data.get("summary")
    contract.risk_score = _clamp_score(data.get("risk_score"))
    contract.risk_level = _clamp_level(data.get("risk_level"))
    law = data.get("law_involved")
    contract.law_involved = law if isinstance(law, list) else None
    kings = data.get("king_clauses")
    contract.king_clauses = kings if isinstance(kings, list) else None
    contract.payment_risk = data.get("payment_risk") if isinstance(data.get("payment_risk"), dict) else None
    contract.breach_risk = data.get("breach_risk") if isinstance(data.get("breach_risk"), dict) else None
    contract.liability_risk = data.get("liability_risk") if isinstance(data.get("liability_risk"), dict) else None
    checklist = data.get("checklist")
    contract.checklist = checklist if isinstance(checklist, list) else None
