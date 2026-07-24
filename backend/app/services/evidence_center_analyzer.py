"""智能证据中心：AI 证据分析编排（Step3）。

职责：给定一条 ``EvidenceFile``（已落盘），完成：

1. **文本获取**：图片 → OCR（``ocr_analysis`` feature，回退 pytesseract）；
   文档 → 文本提取；音视频 → 跳过（基于文件名/元信息弱分析）。
   结果写入 ``evidence_files.ocr_text``，状态推进到 ``ocr_done``。
2. **AI 理解与分析**（``evidence_analysis`` feature，json_mode）：
   - 重新判定证据类型（category）；
   - 结构化提取：时间 / 人物 / 金额 / 地点 / 事件 / 关键内容 → ``evidence_files.metadata``；
   - 证明事项（proof_point）、证明力星级（1-5）、风险点、补强建议；
   - 五维评分（完整性/真实性/关联性/合法性/证明力，各 1-5）；
   → 写入 ``evidence_analysis``（唯一约束，可重入 upsert），状态推进到 ``analyzed``。
3. **向量化**：ocr_text 摘要向 ``embedding``（BGE-M3, 1024 维），失败不阻断。

降级策略（与合同分析器一致）：
- AI 不可用（无 key / 超时 / 401）→ 启发式兜底（正则抽金额/日期、扩展名分类、
  默认星级），仍写入 ``evidence_analysis`` 并置 ``analyzed``，
  ``raw.ai_available=false`` 供前端提示「未配置 AI 模型」。
- 任何子步骤异常绝不向上抛，单条证据分析失败不影响批量。
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EvidenceFileCategoryEnum, EvidenceFileStatusEnum
from app.models.evidence_center import EvidenceAnalysis, EvidenceFile
from app.services.ai.manager import AIManager
from app.services.evidence_center_parser import is_media, parse_evidence_file
from app.utils.storage import resolve_path

# 送模型的最大文本长度（超出截断，避免超 token）
_MAX_ANALYZE_TEXT = 10000
# 向量化文本上限
_MAX_EMBED_TEXT = 2000

_CATEGORY_KEYS = [e.value for e in EvidenceFileCategoryEnum]

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
_SYSTEM_ANALYZE = (
    "你是一位资深的中国执业律师与证据工程专家，擅长像整理卷宗一样分析证据材料。"
    "用户会提供一份证据的文件名、来源与文本内容（可能来自 OCR）。"
    "请严格按下面的 JSON Schema 输出分析结果，不要输出任何多余文字、"
    "不要使用 Markdown 代码块：\n"
    "{\n"
    '  "category": "证据类型，只能从给定枚举中选一个",\n'
    '  "summary": "这份证据是什么、说了什么（<120字，通俗）",\n'
    '  "extraction": {\n'
    '    "times": ["涉及的时间点，如 2024-01-01 或 2024年1月1日"],\n'
    '    "persons": ["涉及人物/主体名称"],\n'
    '    "amounts": ["涉及金额，如 100000元"],\n'
    '    "locations": ["涉及地点"],\n'
    '    "events": ["关键事件，一句话一个"],\n'
    '    "key_content": "最关键的原文摘录（<200字）"\n'
    "  },\n"
    '  "formed_at": "证据形成时间，ISO 格式如 2024-01-01，无法判断则 null",\n'
    '  "proof_point": "这份证据能证明什么（面向诉讼的证明事项表述）",\n'
    '  "proof_strength": 1-5 的整数（证明力星级，5 最强）,\n'
    '  "risk": "该证据存在的风险/瑕疵（如：截图未公证、无原件、主体无法核实）",\n'
    '  "suggestion": "如何补强（如：申请调取原始记录、公证、补充佐证）",\n'
    '  "dimensions": {"completeness":1-5,"authenticity":1-5,"relevance":1-5,'
    '"legality":1-5,"proof_strength":1-5}\n'
    "}\n"
    "证据类型枚举：" + "、".join(_CATEGORY_KEYS) + "。"
    "其中 contract=合同协议、payment=转账/支付/流水凭证、chat=聊天记录、"
    "identity=身份/主体资料、notice=通知/催告/函件、audio=录音、photo=现场照片、"
    "video=视频、email=电子邮件、webpage=网页截图、document=一般文书、other=其他。"
)


def _build_user_prompt(ef: EvidenceFile, text: str | None) -> str:
    lines = [
        f"文件名：{ef.name}",
        f"文件类型：{ef.file_type or '未知'}",
        f"来源说明：{ef.source or '未提供'}",
        f"用户标签：{'、'.join(ef.tags) if ef.tags else '无'}",
    ]
    if text:
        lines.append(f"\n证据文本内容：\n{text[:_MAX_ANALYZE_TEXT]}")
    else:
        lines.append(
            "\n（该证据暂无可提取文本——可能是音视频或无法解析的文件，"
            "请基于文件名/来源/标签做有限分析，并在 risk 中说明需人工核对内容。）"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _safe_json(text: str | None) -> dict | None:
    """从模型输出中尽量解析出 JSON 对象。"""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
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


def _clamp_star(val: Any, default: int = 3) -> int:
    try:
        v = int(val)
    except Exception:
        return default
    return max(1, min(5, v))


def _clamp_dimensions(val: Any) -> dict:
    keys = ("completeness", "authenticity", "relevance", "legality", "proof_strength")
    out: dict[str, int] = {}
    src = val if isinstance(val, dict) else {}
    for k in keys:
        out[k] = _clamp_star(src.get(k))
    return out


def _parse_formed_at(val: Any) -> datetime | None:
    if not val or not isinstance(val, str):
        return None
    val = val.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(val, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# 启发式兜底（AI 不可用）
# ---------------------------------------------------------------------------
_AMOUNT_RE = re.compile(r"(?:¥|￥|人民币)?\s*([0-9][0-9,，]*(?:\.[0-9]{1,2})?)\s*(?:元|万元|块钱)")
_DATE_RE = re.compile(r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})日?")


def _heuristic_analysis(ef: EvidenceFile, text: str | None) -> dict:
    """无 AI 时的兜底分析：正则抽金额/日期，扩展名保底分类。"""
    text = text or ""
    amounts = [m.group(0).strip() for m in _AMOUNT_RE.finditer(text)][:10]
    dates = ["-".join(g for g in m.groups()) for m in _DATE_RE.finditer(text)][:10]
    return {
        "category": ef.category.value if ef.category else "other",
        "summary": f"证据文件「{ef.name}」" + ("，已提取文本内容。" if text else "，暂未提取到文本内容。"),
        "extraction": {
            "times": dates,
            "persons": [],
            "amounts": amounts,
            "locations": [],
            "events": [],
            "key_content": text[:200] if text else None,
        },
        "formed_at": None,
        "proof_point": None,
        "proof_strength": 3,
        "risk": "当前未配置 AI 模型，未能进行智能分析；建议配置模型后重新分析。",
        "suggestion": "在「AI 能力中心」配置可用模型后，对该证据点击「重新分析」。",
        "dimensions": {k: 3 for k in ("completeness", "authenticity", "relevance", "legality", "proof_strength")},
    }


# ---------------------------------------------------------------------------
# 主编排
# ---------------------------------------------------------------------------
async def analyze_evidence(
    ef: EvidenceFile,
    db: AsyncSession,
    mgr: AIManager,
    user_id: UUID | None = None,
    *,
    force_reparse: bool = False,
) -> dict:
    """对一条证据执行「文本获取 → AI 分析 → 落库」全流程。

    可重入：重复调用会覆盖旧的分析结果（evidence_analysis 唯一约束 upsert）。
    返回摘要：``{ai_available, ocr_kind, text_len, proof_strength, status, latency_ms}``
    """
    t0 = time.monotonic()

    # ---- 1) 文本获取（OCR / 提取） ----
    ef.status = EvidenceFileStatusEnum.PROCESSING
    await db.flush()

    text: str | None = ef.ocr_text
    kind = "cached"
    if force_reparse or not text:
        path = resolve_path(ef.file_url)
        ext = f".{ef.file_type}" if ef.file_type else ""
        if path:
            try:
                text, kind = await parse_evidence_file(path, ext, mgr)
            except Exception:
                text, kind = None, "error"
        else:
            text, kind = None, "missing_file"
        if text:
            ef.ocr_text = text
    if ef.ocr_text or (ef.file_type and is_media(f".{ef.file_type}")):
        ef.status = EvidenceFileStatusEnum.OCR_DONE
        await db.flush()

    # ---- 2) AI 分析 ----
    messages = [
        {"role": "system", "content": _SYSTEM_ANALYZE},
        {"role": "user", "content": _build_user_prompt(ef, text)},
    ]
    data: dict | None = None
    model_used: str | None = None
    raw_content: str | None = None
    try:
        model = None
        try:
            model = await mgr.auto_route("evidence_analysis", "chat")
        except Exception:
            model = None
        if model is not None:
            rc = await mgr.chat_model(model.id, messages, json_mode=True, user_id=user_id)
            raw_content = rc.content
            model_used = rc.model_name
            data = _safe_json(rc.content)
        else:
            raw_content = await mgr.chat("evidence_analysis", messages, json_mode=True, user_id=user_id)
            data = _safe_json(raw_content)
    except Exception:
        data = None

    ai_available = data is not None
    if not ai_available:
        data = _heuristic_analysis(ef, text)

    # ---- 3) 回写 evidence_files（分类 / 元数据 / 形成时间） ----
    cat = data.get("category")
    if ai_available and cat in _CATEGORY_KEYS:
        ef.category = EvidenceFileCategoryEnum(cat)
    extraction = data.get("extraction") if isinstance(data.get("extraction"), dict) else {}
    ef.meta = {
        "times": extraction.get("times") or [],
        "persons": extraction.get("persons") or [],
        "amounts": extraction.get("amounts") or [],
        "locations": extraction.get("locations") or [],
        "events": extraction.get("events") or [],
        "key_content": extraction.get("key_content"),
    }
    formed = _parse_formed_at(data.get("formed_at"))
    if formed is not None:
        ef.formed_at = formed

    # ---- 4) upsert evidence_analysis（唯一约束：evidence_id） ----
    existing = (
        await db.scalars(
            select(EvidenceAnalysis).where(EvidenceAnalysis.evidence_id == ef.id)
        )
    ).first()
    analysis = existing or EvidenceAnalysis(evidence_id=ef.id)
    analysis.summary = data.get("summary")
    analysis.proof_point = data.get("proof_point")
    analysis.proof_strength = _clamp_star(data.get("proof_strength"))
    analysis.risk = data.get("risk")
    analysis.suggestion = data.get("suggestion")
    analysis.dimensions = _clamp_dimensions(data.get("dimensions"))
    analysis.model_used = model_used
    analysis.raw = {
        "ai_available": ai_available,
        "content": (raw_content or "")[:4000] or None,
    }
    db.add(analysis)

    # ---- 5) 向量化（失败不阻断） ----
    embed_src = (analysis.summary or "") + "\n" + (text or "")
    embed_src = embed_src.strip()[:_MAX_EMBED_TEXT]
    if embed_src:
        try:
            if await mgr.available("embedding", "embedding"):
                ef.embedding = await mgr.embed_doc("embedding", embed_src, user_id=user_id)
        except Exception:
            pass

    ef.status = EvidenceFileStatusEnum.ANALYZED
    await db.flush()

    return {
        "ai_available": ai_available,
        "ocr_kind": kind,
        "text_len": len(text or ""),
        "proof_strength": analysis.proof_strength,
        "status": ef.status.value,
        "latency_ms": int((time.monotonic() - t0) * 1000),
    }
