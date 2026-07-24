"""合同审查报告生成（Step5 落地）。

职责：给定已分析的合同（含 ``full_text`` / ``summary`` / ``risk_*`` / ``contract_risks`` /
``contract_clauses``），生成一份结构化的 Markdown 审查报告，并可选地调用 AI（feature
``case_summary``）生成「审查结论与建议」叙事段落，提升可读性。

设计要点（与项目「统一调用规范」「优雅降级」一致）：
- 报告**正文**完全由结构化数据拼装，AI 不可用时也能输出一份完整、可读的报告
  （规则降级），不阻断业务。
- AI 仅用于「审查结论与建议」叙事增强；失败则 ``ai_assisted=False``，报告仍可用。
- 同一 ``contract_id + report_type`` 仅保留最新一条（重新生成时先删旧再插新）。
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.contract.service import ContractService
from app.models.contract import (
    CONTRACT_RISK_CATEGORIES,
    CONTRACT_TYPE_LABELS,
    Contract,
    ContractClause,
    ContractReport,
    ContractRisk,
)
from app.services.ai.manager import AIManager

# 风险等级 / 分类中文标签（与前端 constants.ts 对齐）
_RISK_LEVEL_LABELS = {"low": "低", "medium": "中", "high": "高"}
_RISK_CATEGORY_LABELS = {
    "payment": "付款",
    "breach": "违约",
    "confidentiality": "保密",
    "ip": "知识产权",
    "termination": "解除合同",
    "liability": "赔偿责任",
    "force_majeure": "不可抗力",
    "dispute": "争议解决",
    "other": "其他",
}

_REPORT_TITLE = {
    "review": "合同审查报告",
    "summary": "合同摘要报告",
    "full": "合同完整审查报告",
    "checklist": "签署前检查清单",
}


# ---------------------------------------------------------------------------
# AI 叙事（可选增强）
# ---------------------------------------------------------------------------
_SYSTEM_NARRATIVE = (
    "你是一位资深的中国执业律师。用户会提供一份合同的审查摘要、风险评分与主要风险点。"
    "请用 3-5 段通俗易懂的中文，给出「总体审查结论与签约建议」，重点提示最需要注意的"
    "事项、谈判要点与风险缓释建议。不要使用 Markdown 代码块，直接输出纯文本。"
)


async def _build_narrative(
    contract: Contract,
    risks: list[ContractRisk],
    clauses: list[ContractClause],
    mgr: AIManager,
    user_id: UUID | None,
) -> tuple[str | None, UUID | None]:
    """调用 AI（case_summary）生成审查结论叙事；不可用返回 (None, None)。"""
    if not (contract.summary or risks):
        return None, None
    top = sorted(risks, key=lambda r: r.score, reverse=True)[:5]
    risk_lines = "\n".join(
        f"- [{_RISK_LEVEL_LABELS.get(r.risk_level, r.risk_level)}] "
        f"{_RISK_CATEGORY_LABELS.get(r.category, r.category)}"
        f"（{r.clause_ref or '—'}）：{r.reason or ''}"
        for r in top
    )
    user_content = (
        f"合同标题：{contract.title or '（无标题）'}\n"
        f"合同类型：{contract.contract_type or '未知'}\n"
        f"风险评分：{contract.risk_score}/100（{_RISK_LEVEL_LABELS.get(contract.risk_level, contract.risk_level)}）\n"
        f"一句话摘要：{contract.summary or '（无）'}\n\n"
        f"主要风险点：\n{risk_lines or '（无）'}"
    )
    try:
        model = await mgr.auto_route("case_summary", "chat")
    except Exception:
        model = None
    try:
        if model is not None:
            res = await mgr.chat_model(
                model.id,
                [
                    {"role": "system", "content": _SYSTEM_NARRATIVE},
                    {"role": "user", "content": user_content},
                ],
                user_id=user_id,
            )
            text = getattr(res, "content", None)
            model_id = getattr(res, "model_id", None)
        else:
            text = await mgr.chat(
                "case_summary",
                [
                    {"role": "system", "content": _SYSTEM_NARRATIVE},
                    {"role": "user", "content": user_content},
                ],
                user_id=user_id,
            )
            model_id = None
    except Exception:
        return None, None
    if not text:
        return None, None
    return str(text).strip(), model_id


# ---------------------------------------------------------------------------
# Markdown 拼装
# ---------------------------------------------------------------------------
def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        return dt.strftime("%Y-%m-%d %H:%M")
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def build_report_markdown(
    contract: Contract,
    risks: list[ContractRisk],
    clauses: list[ContractClause],
    report_type: str,
    narrative: str | None,
) -> tuple[str, dict]:
    """根据报告类型拼装 Markdown 正文 + 结构化 content_json。"""
    type_label = CONTRACT_TYPE_LABELS.get(contract.contract_type or "", contract.contract_type or "未知")
    risk_level_label = _RISK_LEVEL_LABELS.get(contract.risk_level, contract.risk_level)
    now = datetime.now(timezone.utc)
    ai_assisted = bool(narrative)

    L: list[str] = []
    L.append(f"# {_REPORT_TITLE.get(report_type, '合同审查报告')}")
    L.append("")
    L.append(f"**合同名称**：{contract.title or '（无标题）'}")
    L.append(f"**合同类型**：{type_label}")
    L.append(f"**风险评分**：{contract.risk_score}/100（{risk_level_label}）")
    L.append(f"**生成时间**：{_fmt_dt(now)}")
    L.append(f"**生成方式**：{'AI 辅助生成' if ai_assisted else '规则自动生成（AI 暂不可用）'}")
    L.append("")

    sections: list[dict] = []

    # 摘要
    if report_type in ("review", "summary", "full"):
        L.append("## 一、合同摘要")
        L.append("")
        L.append(contract.summary or "（暂未生成摘要，请先执行 AI 分析）")
        L.append("")
        sections.append({"key": "summary", "title": "合同摘要", "text": contract.summary or ""})

    # 总体风险
    if report_type in ("review", "summary", "full"):
        n_high = sum(1 for r in risks if r.risk_level == "high")
        n_mid = sum(1 for r in risks if r.risk_level == "medium")
        L.append("## 二、总体风险评估")
        L.append("")
        L.append(f"- 风险总分：**{contract.risk_score}/100**（{risk_level_label}）")
        L.append(f"- 识别风险点：共 **{len(risks)}** 项（高危 {n_high} 项 / 中危 {n_mid} 项）")
        if contract.law_involved:
            laws = "、".join(
                f"{l.get('name', '法律')}{(' ' + l.get('article', '')) if l.get('article') else ''}"
                for l in contract.law_involved[:8]
                if isinstance(l, dict)
            )
            if laws:
                L.append(f"- 涉及法律：{laws}")
        L.append("")

    # 风险明细
    if report_type in ("review", "full") and risks:
        L.append("## 三、风险明细")
        L.append("")
        for i, r in enumerate(sorted(risks, key=lambda x: x.score, reverse=True), 1):
            cat = _RISK_CATEGORY_LABELS.get(r.category, r.category)
            lvl = _RISK_LEVEL_LABELS.get(r.risk_level, r.risk_level)
            king = " ⚠️**霸王条款**" if r.king_clause else ""
            L.append(f"### 3.{i} [{lvl}] {cat}（{r.clause_ref or '条款'}）{king}")
            if r.clause_text:
                L.append("")
                L.append(f"> {r.clause_text.strip()[:600]}")
            if r.reason:
                L.append("")
                L.append(f"- **风险原因**：{r.reason}")
            if r.suggestion:
                L.append(f"- **修改建议**：{r.suggestion}")
            if r.suggested_text:
                L.append(f"- **推荐表述**：{r.suggested_text}")
            L.append("")
        sections.append({"key": "risks", "title": "风险明细", "text": f"共 {len(risks)} 项"})

    # 霸王条款
    kings = [r for r in risks if r.king_clause]
    if report_type in ("review", "full") and kings:
        L.append("## 四、霸王条款提示")
        L.append("")
        for r in kings:
            L.append(f"- **{r.clause_ref or '条款'}**：{r.reason or ''}")
            if r.suggestion:
                L.append(f"  - 建议：{r.suggestion}")
        L.append("")

    # 专项风险
    if report_type in ("review", "full"):
        specials = [
            ("payment_risk", "付款风险"),
            ("breach_risk", "违约风险"),
            ("liability_risk", "赔偿责任"),
        ]
        any_special = False
        for attr, label in specials:
            val = getattr(contract, attr, None)
            if isinstance(val, dict) and (val.get("detail") or val.get("level")):
                if not any_special:
                    L.append("## 五、专项风险")
                    L.append("")
                    any_special = True
                lvl = _RISK_LEVEL_LABELS.get(val.get("level", ""), val.get("level", ""))
                L.append(f"### {label}（{lvl or '—'}）")
                if val.get("detail"):
                    L.append(f"- {val['detail']}")
                if val.get("suggestion"):
                    L.append(f"- 建议：{val['suggestion']}")
                L.append("")
        if any_special:
            sections.append({"key": "special", "title": "专项风险", "text": ""})

    # 逐条款解读
    if report_type in ("review", "full") and clauses:
        L.append("## 六、逐条款解读（Clause Analyzer）")
        L.append("")
        for c in clauses:
            no = c.clause_no or "条款"
            L.append(f"### {no}")
            if c.explanation:
                L.append(f"- **解读**：{c.explanation}")
            if c.risk_level or c.risk_note:
                lvl = _RISK_LEVEL_LABELS.get(c.risk_level, c.risk_level) if c.risk_level else ""
                L.append(f"- **风险**：{('[' + lvl + '] ') if lvl else ''}{c.risk_note or ''}")
            if c.suggested_version:
                L.append(f"- **建议修改**：{c.suggested_version}")
            if not (c.explanation or c.risk_note or c.suggested_version):
                L.append("- （暂无可解读内容，请先执行 AI 分析）")
            L.append("")
        sections.append({"key": "clauses", "title": "逐条款解读", "text": f"共 {len(clauses)} 条"})

    # 检查清单（所有类型都给，尤其是 checklist 类型）
    checklist = contract.checklist if isinstance(contract.checklist, list) else []
    if report_type == "checklist":
        L.append("## 签署前检查清单")
        L.append("")
        if checklist:
            for item in checklist:
                if isinstance(item, dict):
                    L.append(f"- [ ] {item.get('item', '')}")
        else:
            L.append("（暂无可生成的检查项，请先执行 AI 分析）")
        L.append("")
    elif report_type in ("review", "summary", "full") and checklist:
        L.append("## 七、签署前检查清单")
        L.append("")
        for item in checklist:
            if isinstance(item, dict):
                L.append(f"- [ ] {item.get('item', '')}")
        L.append("")

    # 审查结论（AI 叙事）
    if narrative:
        L.append("## 八、审查结论与签约建议")
        L.append("")
        L.append(narrative)
        L.append("")
        sections.append({"key": "conclusion", "title": "审查结论", "text": narrative})

    # 完整报告：追加全文附录
    if report_type == "full" and contract.full_text:
        L.append("## 附录：合同全文")
        L.append("")
        L.append("<details>")
        L.append("<summary>点击展开合同原文</summary>")
        L.append("")
        L.append("```text")
        L.append(contract.full_text[:30000])
        L.append("```")
        L.append("")
        L.append("</details>")
        L.append("")

    L.append("---")
    L.append("*本报告由 LawPilot 合同智能中心自动生成，仅供参卡，不构成正式法律意见。*")

    content = "\n".join(L)
    content_json = {
        "report_type": report_type,
        "contract_id": str(contract.id),
        "contract_title": contract.title,
        "contract_type": contract.contract_type,
        "risk_score": contract.risk_score,
        "risk_level": contract.risk_level,
        "risks_count": len(risks),
        "clauses_count": len(clauses),
        "ai_assisted": ai_assisted,
        "generated_at": _fmt_dt(now),
        "sections": sections,
    }
    return content, content_json


# ---------------------------------------------------------------------------
# 生成编排
# ---------------------------------------------------------------------------
async def generate_report(
    contract: Contract,
    db: AsyncSession,
    mgr: AIManager,
    user_id: UUID | None = None,
    report_type: str = "review",
    regenerate: bool = False,
) -> tuple[ContractReport, bool]:
    """生成（或取回）一份合同审查报告。

    返回 ``(report, generated)``：``generated=True`` 表示本次新生成，``False`` 表示
    命中了已存储的同类型报告（且未要求 regenerate）。
    """
    if report_type not in ("review", "summary", "full", "checklist"):
        report_type = "review"

    svc = ContractService(db)
    existing = await svc.get_report(contract.id, report_type)
    if existing is not None and not regenerate:
        return existing, False

    risks = await svc.get_risks(contract.id)
    clauses = await svc.get_clauses(contract.id)

    narrative: str | None = None
    model_id: UUID | None = None
    # 仅在已有分析数据（summary/risks）时尝试 AI 叙事，避免无效调用
    if contract.summary or risks:
        narrative, model_id = await _build_narrative(contract, risks, clauses, mgr, user_id)

    content, content_json = build_report_markdown(
        contract, risks, clauses, report_type, narrative
    )

    # 同类型先删后插，保证只保留最新一条
    await db.execute(
        delete(ContractReport).where(
            ContractReport.contract_id == contract.id,
            ContractReport.report_type == report_type,
        )
    )
    report = ContractReport(
        contract_id=contract.id,
        report_type=report_type,
        title=_REPORT_TITLE.get(report_type, "合同审查报告"),
        content=content,
        content_json=content_json,
        format="markdown",
        generated_by=user_id,
        model_id=model_id,
    )
    db.add(report)
    await db.flush()
    return report, True
