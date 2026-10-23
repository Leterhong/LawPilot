"""智能证据中心 Step5：证据报告生成（目录 / 评分 / 缺失分析 / 策略 / 综合）。

职责：
- 给定案件（``case_id``）或显式证据集合（``evidence_ids``），汇总 Step1~4 的产物
  （证据文件 + AI 分析 + 证据关系 + 时间线），生成一份结构化报告。
- 五种报告类型（``EvidenceReportTypeEnum``）：
  - ``directory`` 证据目录（法院格式）
  - ``score``    证据评分报告（证明力 / 五维评分 / 风险 / 建议）
  - ``missing``  证据缺失与薄弱分析
  - ``strategy`` 举证策略与建议
  - ``full``     综合报告（以上汇总 + AI 结论）
- 导出：Markdown（始终可用）、Word(.docx，零依赖 OOXML)、PDF(reportlab + 中文字体)。

设计要点（与合同中心 Step5、项目「优雅降级」一致）：
- 报告**正文**完全由结构化数据拼装，AI 不可用时也能产出完整报告；
- AI 仅用于「缺失/策略/综合」的叙事增强；不可用时 ``ai_assisted=False``，规则报告仍可用；
- 同一 ``case_id + report_type`` 仅保留最新一条（重新生成先删旧再插新）。
"""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    CaseTypeEnum,
    EvidenceFileCategoryEnum,
    EvidenceRelationTypeEnum,
    EvidenceReportTypeEnum,
)
from app.models.evidence_center import (
    EvidenceAnalysis,
    EvidenceFile,
    EvidenceRelation,
    EvidenceReport,
    EvidenceTimelineNode,
)
from app.models.user import User
from app.services.ai.manager import AIManager
from app.services.case_service import CaseService
from app.services.evidence_center_chain import EvidenceChainService, _evidence_time

# ---------------------------------------------------------------------------
# 中文标签
# ---------------------------------------------------------------------------
CATEGORY_LABELS: dict[EvidenceFileCategoryEnum, str] = {
    EvidenceFileCategoryEnum.CONTRACT: "合同/协议",
    EvidenceFileCategoryEnum.PAYMENT: "转账/支付凭证",
    EvidenceFileCategoryEnum.CHAT: "聊天记录",
    EvidenceFileCategoryEnum.IDENTITY: "身份/主体资料",
    EvidenceFileCategoryEnum.NOTICE: "通知/催告/函件",
    EvidenceFileCategoryEnum.AUDIO: "录音",
    EvidenceFileCategoryEnum.PHOTO: "现场照片",
    EvidenceFileCategoryEnum.VIDEO: "视频",
    EvidenceFileCategoryEnum.EMAIL: "电子邮件",
    EvidenceFileCategoryEnum.WEBPAGE: "网页截图",
    EvidenceFileCategoryEnum.DOCUMENT: "一般文书",
    EvidenceFileCategoryEnum.OTHER: "其他",
}

RELATION_LABELS: dict[EvidenceRelationTypeEnum, str] = {
    EvidenceRelationTypeEnum.SEQUENCE: "时间先后",
    EvidenceRelationTypeEnum.SUPPORT: "相互印证",
    EvidenceRelationTypeEnum.CONTRADICT: "相互矛盾",
    EvidenceRelationTypeEnum.PREREQUISITE: "前提基础",
    EvidenceRelationTypeEnum.RELATED: "一般关联",
}

REPORT_TITLE: dict[str, str] = {
    "directory": "证据目录",
    "score": "证据评分报告",
    "missing": "证据缺失与薄弱分析",
    "strategy": "举证策略与建议",
    "full": "证据综合报告",
}

# 不同案由「通常应当收集」的证据（启发式缺失分析用）
# (证据类型枚举, 中文说明)
RECOMMENDED_EVIDENCE: dict[str, list[tuple[EvidenceFileCategoryEnum, str]]] = {
    CaseTypeEnum.LOAN.value: [
        (EvidenceFileCategoryEnum.CONTRACT, "借款合同 / 借条 / 欠条"),
        (EvidenceFileCategoryEnum.PAYMENT, "转账 / 支付凭证（银行流水、微信支付宝记录）"),
        (EvidenceFileCategoryEnum.CHAT, "沟通与催款记录（聊天截图）"),
        (EvidenceFileCategoryEnum.IDENTITY, "双方身份证明（身份证 / 营业执照）"),
    ],
    CaseTypeEnum.RENT.value: [
        (EvidenceFileCategoryEnum.CONTRACT, "房屋租赁合同"),
        (EvidenceFileCategoryEnum.PAYMENT, "租金与押金支付凭证"),
        (EvidenceFileCategoryEnum.PHOTO, "房屋及物品状况照片 / 交接单"),
        (EvidenceFileCategoryEnum.CHAT, "与房东的沟通记录"),
    ],
    CaseTypeEnum.LABOR.value: [
        (EvidenceFileCategoryEnum.CONTRACT, "劳动合同 / 用工协议"),
        (EvidenceFileCategoryEnum.PAYMENT, "工资流水 / 工资条"),
        (EvidenceFileCategoryEnum.NOTICE, "解除通知 / 处分决定 / 入职证明"),
        (EvidenceFileCategoryEnum.DOCUMENT, "考勤 / 工作成果记录"),
    ],
    CaseTypeEnum.CONSUMER.value: [
        (EvidenceFileCategoryEnum.CONTRACT, "订单 / 购买合同"),
        (EvidenceFileCategoryEnum.PAYMENT, "支付凭证"),
        (EvidenceFileCategoryEnum.PHOTO, "商品 / 服务问题照片或视频"),
        (EvidenceFileCategoryEnum.CHAT, "与商家的沟通记录"),
    ],
    CaseTypeEnum.MARRIAGE.value: [
        (EvidenceFileCategoryEnum.IDENTITY, "结婚证 / 身份证"),
        (EvidenceFileCategoryEnum.PAYMENT, "夫妻共同财产与债务证明"),
        (EvidenceFileCategoryEnum.DOCUMENT, "子女抚养相关材料"),
    ],
}


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        return dt.strftime("%Y-%m-%d %H:%M")
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def _fmt_date(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d")


def _stars(n: int | None) -> str:
    if not n:
        return "—"
    return "★" * n + "☆" * (5 - n)


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _category_label(cat: EvidenceFileCategoryEnum) -> str:
    return CATEGORY_LABELS.get(cat, cat.value if cat else "其他")


# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------
async def _load_report_data(
    current: User,
    *,
    case_id: UUID | None,
    evidence_ids: list[UUID] | None,
    db: AsyncSession,
) -> dict:
    """汇总生成报告所需的全部数据（含权限校验）。"""
    case = None
    if case_id is not None:
        case = await CaseService(db).get_owned(case_id, current)
        if case is None:
            raise ValueError("案件不存在或无权访问")

    chain = EvidenceChainService(db)
    evidences = await chain.pick_evidences(
        current, case_id=case_id, evidence_ids=evidence_ids, limit=200
    )
    if not evidences:
        raise ValueError("没有可用于生成报告的（已授权）证据")

    ids = [e.id for e in evidences]
    analyses = (
        await db.scalars(
            select(EvidenceAnalysis).where(EvidenceAnalysis.evidence_id.in_(ids))
        )
    ).all()
    analysis_map = {a.evidence_id: a for a in analyses}

    relations: list[EvidenceRelation] = []
    if ids:
        relations = list(
            (
                await db.scalars(
                    select(EvidenceRelation).where(
                        EvidenceRelation.source_id.in_(ids),
                        EvidenceRelation.target_id.in_(ids),
                    )
                )
            ).all()
        )

    timeline: list[EvidenceTimelineNode] = []
    if case_id is not None:
        timeline = await chain.list_timeline(case_id)

    name_map = {e.id: e.name for e in evidences}
    return {
        "case": case,
        "evidences": evidences,
        "analysis_map": analysis_map,
        "relations": relations,
        "timeline": timeline,
        "name_map": name_map,
    }


# ---------------------------------------------------------------------------
# 缺失 / 薄弱分析（启发式，供 missing/strategy/full 复用）
# ---------------------------------------------------------------------------
def _build_missing_findings(data: dict) -> dict:
    evidences: list[EvidenceFile] = data["evidences"]
    analysis_map: dict[UUID, EvidenceAnalysis] = data["analysis_map"]
    relations: list[EvidenceRelation] = data["relations"]

    weak: list[dict] = []
    for e in evidences:
        a = analysis_map.get(e.id)
        reasons: list[str] = []
        if a is None:
            reasons.append("尚未进行 AI 分析，证明力未知")
        else:
            if (a.proof_strength or 0) <= 2:
                reasons.append(f"证明力较弱（{_stars(a.proof_strength)}）")
            if a.risk:
                rs = a.risk
                if any(k in rs for k in ("未公证", "无原件", "无法核实", "瑕疵", "截图")):
                    reasons.append(f"存在风险点：{rs[:60]}")
        if reasons:
            weak.append(
                {
                    "name": e.name,
                    "category": _category_label(e.category),
                    "reasons": reasons,
                    "suggestion": (a.suggestion if a and a.suggestion else None),
                }
            )

    # 缺失证据（按案由推荐清单比对已有证据类型）
    missing: list[dict] = []
    case = data.get("case")
    case_type = case.case_type.value if case and getattr(case, "case_type", None) else None
    recs = RECOMMENDED_EVIDENCE.get(case_type or "", [])
    have_cats = {e.category for e in evidences}
    for cat, desc in recs:
        if cat not in have_cats:
            missing.append({"category": _category_label(cat), "desc": desc})

    # 矛盾证据
    contradicts: list[dict] = []
    name_map = {e.id: e.name for e in evidences}
    for r in relations:
        if r.relation_type == EvidenceRelationTypeEnum.CONTRADICT:
            contradicts.append(
                {
                    "a": name_map.get(r.source_id, str(r.source_id)),
                    "b": name_map.get(r.target_id, str(r.target_id)),
                    "note": r.note,
                }
            )

    return {"weak": weak, "missing": missing, "contradicts": contradicts}


# ---------------------------------------------------------------------------
# AI 叙事（可选增强）
# ---------------------------------------------------------------------------
_SYSTEM_NARRATIVE = (
    "你是一位资深的中国执业律师，擅长证据组织与举证策略。用户会提供一组证据的概况"
    "（证明事项、证明力、风险点、缺失与矛盾）。请用 3-5 段通俗易懂的中文，给出"
    "「举证策略与整体建议」：重点提示最需要注意的事项、举证顺序、补强方向与风险缓释。"
    "直接输出纯文本，不要使用 Markdown 代码块，每一段用换行分隔。"
)


async def _build_narrative(
    data: dict, mgr: AIManager, user_id: UUID | None
) -> tuple[str | None, UUID | None]:
    """调用 AI（evidence_analysis feature）生成举证策略叙事；不可用返回 (None, None)。"""
    evidences: list[EvidenceFile] = data["evidences"]
    analysis_map: dict[UUID, EvidenceAnalysis] = data["analysis_map"]
    findings = _build_missing_findings(data)

    lines = []
    for e in evidences:
        a = analysis_map.get(e.id)
        pp = (a.proof_point or a.summary or "未分析") if a else "未分析"
        ps = _stars(a.proof_strength) if a else "—"
        lines.append(
            f"- {e.name}（{_category_label(e.category)}）：证明「{pp}」，证明力 {ps}"
        )
    context = "\n".join(lines)
    miss = "；".join(m["desc"] for m in findings["missing"]) or "无明显缺失"
    weak = "；".join(w["name"] for w in findings["weak"]) or "无明显薄弱证据"
    cont = "；".join(f"{c['a']} 与 {c['b']}" for c in findings["contradicts"]) or "无"

    user_content = (
        f"证据总数：{len(evidences)}\n"
        f"证据清单与证明目的：\n{context}\n\n"
        f"缺失证据：{miss}\n"
        f"薄弱证据：{weak}\n"
        f"矛盾证据：{cont}\n\n"
        "请据此给出举证策略与整体建议。"
    )

    try:
        model = await mgr.auto_route("evidence_analysis", "chat")
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
                "evidence_analysis",
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
# 块（blocks）构造：目录 / 评分 / 缺失 / 策略 / 综合
# ---------------------------------------------------------------------------
def _meta_blocks(data: dict, report_type: str) -> list[dict]:
    case = data["case"]
    evidences: list[EvidenceFile] = data["evidences"]
    analysis_map = data["analysis_map"]
    case_label = (
        f"{getattr(case, 'title', '') or case.case_type.value}"
        if case
        else "（未关联案件）"
    )
    analyzed = sum(1 for e in evidences if e.id in analysis_map)
    strengths = [a.proof_strength for a in analysis_map.values() if a.proof_strength]
    avg = round(sum(strengths) / len(strengths), 1) if strengths else None
    now = datetime.now(timezone.utc)

    blocks: list[dict] = [
        {"t": "title", "text": REPORT_TITLE.get(report_type, "证据报告")},
        {"t": "p", "text": f"**关联案件**：{case_label}"},
        {"t": "p", "text": f"**证据总数**：{len(evidences)}（已分析 {analyzed} 项）"},
        {"t": "p", "text": f"**平均证明力**：{_stars(round(avg)) if avg else '—'}（{avg}/5）"},
        {"t": "p", "text": f"**生成时间**：{_fmt_dt(now)}"},
    ]
    return blocks


def _directory_blocks(data: dict) -> list[dict]:
    evidences: list[EvidenceFile] = data["evidences"]
    analysis_map = data["analysis_map"]

    # 按形成时间排序（无时间则按上传顺序）
    def _sort_key(e: EvidenceFile):
        t = _evidence_time(e)
        return t or datetime.max.replace(tzinfo=timezone.utc)

    ordered = sorted(evidences, key=_sort_key)
    headers = ["序号", "证据名称", "证据来源", "证据种类", "形成时间", "证明目的"]
    rows = []
    for i, e in enumerate(ordered, 1):
        a = analysis_map.get(e.id)
        purpose = (a.proof_point or a.summary or "（尚未分析，暂无法明确证明目的）") if a else "（尚未分析）"
        rows.append(
            [
                str(i),
                e.name,
                e.source or "—",
                _category_label(e.category),
                _fmt_date(_evidence_time(e)),
                (purpose[:200] if purpose else "—"),
            ]
        )
    return [
        {"t": "h2", "text": "一、证据目录"},
        {"t": "table", "headers": headers, "rows": rows},
    ]


def _score_blocks(data: dict) -> list[dict]:
    evidences: list[EvidenceFile] = data["evidences"]
    analysis_map = data["analysis_map"]
    blocks: list[dict] = [{"t": "h2", "text": "一、证据评分明细"}]
    idx = 0
    for e in evidences:
        a = analysis_map.get(e.id)
        idx += 1
        blocks.append({"t": "h3", "text": f"{idx}. {e.name}（{_category_label(e.category)}）"})
        if a is None:
            blocks.append({"t": "p", "text": "该证据尚未分析，暂无法评分。建议先执行 AI 分析。"})
            continue
        blocks.append({"t": "p", "text": f"**证明力**：{_stars(a.proof_strength)}（{a.proof_strength or 0}/5）"})
        dims = a.dimensions or {}
        blocks.append(
            {
                "t": "table",
                "headers": ["维度", "评分"],
                "rows": [
                    ["完整性", f"{dims.get('completeness', '—')}/5"],
                    ["真实性", f"{dims.get('authenticity', '—')}/5"],
                    ["关联性", f"{dims.get('relevance', '—')}/5"],
                    ["合法性", f"{dims.get('legality', '—')}/5"],
                    ["证明力", f"{dims.get('proof_strength', '—')}/5"],
                ],
            }
        )
        if a.summary:
            blocks.append({"t": "p", "text": f"**理解**：{a.summary}"})
        if a.proof_point:
            blocks.append({"t": "p", "text": f"**证明事项**：{a.proof_point}"})
        if a.risk:
            blocks.append({"t": "p", "text": f"**风险点**：{a.risk}"})
        if a.suggestion:
            blocks.append({"t": "p", "text": f"**补强建议**：{a.suggestion}"})
    return blocks


def _missing_blocks(data: dict, narrative: str | None) -> list[dict]:
    findings = _build_missing_findings(data)
    blocks: list[dict] = [
        {"t": "h2", "text": "一、薄弱 / 需补强证据"},
    ]
    if findings["weak"]:
        items = []
        for w in findings["weak"]:
            reasons = "；".join(w["reasons"])
            line = "**" + w["name"] + "**（" + w["category"] + "）：" + reasons
            if w["suggestion"]:
                line += "；建议：" + w["suggestion"]
            items.append(line)
        blocks.append({"t": "bullets", "items": items})
    else:
        blocks.append({"t": "p", "text": "未发现明显薄弱证据。"})

    blocks.append({"t": "h2", "text": "二、建议补充的缺失证据"})
    if findings["missing"]:
        items = [
            "缺少【" + m["category"] + "】：建议补充 " + m["desc"]
            for m in findings["missing"]
        ]
        blocks.append({"t": "bullets", "items": items})
    else:
        blocks.append({"t": "p", "text": "就本案案由而言，常用证据类型已基本齐备。"})

    blocks.append({"t": "h2", "text": "三、矛盾证据提示"})
    if findings["contradicts"]:
        items = []
        for c in findings["contradicts"]:
            note = c["note"] or "请核实并说明"
            items.append("**" + c["a"] + "** 与 **" + c["b"] + "** 存在矛盾：" + note)
        blocks.append({"t": "bullets", "items": items})
    else:
        blocks.append({"t": "p", "text": "未发现相互矛盾的证据。"})

    if narrative:
        blocks.append({"t": "h2", "text": "四、AI 补强建议"})
        blocks.append({"t": "p", "text": narrative})
    return blocks


def _strategy_blocks(data: dict, narrative: str | None) -> list[dict]:
    evidences: list[EvidenceFile] = data["evidences"]
    analysis_map = data["analysis_map"]
    findings = _build_missing_findings(data)

    # 举证顺序：按时间线（若有）否则按形成时间
    timeline: list[EvidenceTimelineNode] = data["timeline"]
    order_names: list[str] = []
    if timeline:
        for node in timeline:
            ev_ids = node.evidence_ids or []
            names = [data["name_map"].get(UUID(x)) for x in ev_ids]
            names = [n for n in names if n]
            label = f"{node.event}（{_fmt_date(node.event_time)}）"
            if names:
                label += "：" + "、".join(names[:5])
            order_names.append(label)
    if not order_names:
        def _sk(e: EvidenceFile):
            t = _evidence_time(e)
            return t or datetime.max.replace(tzinfo=timezone.utc)

        for e in sorted(evidences, key=_sk):
            a = analysis_map.get(e.id)
            pp = (a.proof_point or a.summary or "证明目的待明确") if a else "（未分析）"
            t = _evidence_time(e)
            order_names.append(f"{e.name}（{_fmt_date(t)}）：{pp[:60]}")

    blocks: list[dict] = [
        {"t": "h2", "text": "一、建议举证顺序"},
        {"t": "bullets", "items": [f"{i}. {x}" for i, x in enumerate(order_names, 1)]},
        {"t": "h2", "text": "二、证据优势（证明力较强）"},
    ]
    strong = [
        e for e in evidences
        if (analysis_map.get(e.id) and (analysis_map[e.id].proof_strength or 0) >= 4)
    ]
    if strong:
        blocks.append(
            {
                "t": "bullets",
                "items": [
                    f"**{e.name}**：{_stars(analysis_map[e.id].proof_strength)}"
                    for e in strong
                ],
            }
        )
    else:
        blocks.append({"t": "p", "text": "暂无明显高证明力（≥4 星）证据，建议优先补强关键证据。"})

    blocks.append({"t": "h2", "text": "三、风险与薄弱点"})
    if findings["weak"]:
        items = [
            "**" + w["name"] + "**：" + "；".join(w["reasons"])
            for w in findings["weak"]
        ]
        blocks.append({"t": "bullets", "items": items})
    else:
        blocks.append({"t": "p", "text": "未发现明显薄弱证据。"})

    if narrative:
        blocks.append({"t": "h2", "text": "四、整体举证策略"})
        blocks.append({"t": "p", "text": narrative})
    return blocks


def _assemble_blocks(data: dict, report_type: str, narrative: str | None) -> list[dict]:
    blocks: list[dict] = _meta_blocks(data, report_type)
    if report_type == "directory":
        blocks += _directory_blocks(data)
    elif report_type == "score":
        blocks += _score_blocks(data)
    elif report_type == "missing":
        blocks += _missing_blocks(data, narrative)
    elif report_type == "strategy":
        blocks += _strategy_blocks(data, narrative)
    elif report_type == "full":
        blocks += _directory_blocks(data)
        blocks += _score_blocks(data)
        blocks += _missing_blocks(data, narrative)
        blocks += _strategy_blocks(data, narrative)
    else:
        blocks += _directory_blocks(data)
    blocks.append({"t": "spacer"})
    blocks.append(
        {"t": "p", "text": "*本报告由 LawPilot 智能证据中心自动生成，仅供参卡，不构成正式法律意见。*"}
    )
    return blocks


# ---------------------------------------------------------------------------
# 渲染：Markdown（始终可用）
# ---------------------------------------------------------------------------
def render_markdown(blocks: list[dict]) -> str:
    L: list[str] = []
    for b in blocks:
        t = b.get("t")
        if t == "title":
            L.append(f"# {b['text']}")
            L.append("")
        elif t == "h2":
            L.append(f"## {b['text']}")
            L.append("")
        elif t == "h3":
            L.append(f"### {b['text']}")
            L.append("")
        elif t == "p":
            L.append(b["text"])
            L.append("")
        elif t == "bullets":
            for it in b["items"]:
                L.append(f"- {it}")
            L.append("")
        elif t == "table":
            headers = b["headers"]
            L.append("| " + " | ".join(headers) + " |")
            L.append("| " + " | ".join("---" for _ in headers) + " |")
            for row in b["rows"]:
                L.append("| " + " | ".join(str(c) for c in row) + " |")
            L.append("")
        elif t == "spacer":
            L.append("")
        elif t == "rule":
            L.append("---")
            L.append("")
    return "\n".join(L).strip() + "\n"


# ---------------------------------------------------------------------------
# 渲染：Word (.docx)，零依赖（标准库 zipfile + OOXML）
# ---------------------------------------------------------------------------
def _docx_runs(text: str) -> str:
    """将含 **bold** 的文本拆分为 w:r 片段。"""
    parts = text.split("**")
    out = []
    for i, seg in enumerate(parts):
        if not seg:
            continue
        bold = (i % 2 == 1)
        out.append(
            f'<w:r><w:rPr>{"<w:b/>" if bold else ""}</w:rPr>'
            f'<w:t xml:space="preserve">{_escape_xml(seg)}</w:t></w:r>'
        )
    return "".join(out) if out else '<w:r><w:t xml:space="preserve"></w:t></w:r>'


def _docx_para(text: str, style: str | None = None) -> str:
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{ppr}{_docx_runs(text)}</w:p>"


def _docx_table(block: dict) -> str:
    headers = block["headers"]
    rows = block["rows"]
    n = len(headers)
    total = 9000
    col_w = total // max(n, 1)
    grid = "".join(f'<w:gridCol w:w="{col_w}"/>' for _ in range(n))
    borders = (
        '<w:tblBorders>'
        '<w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        "</w:tblBorders>"
    )
    tblpr = (
        f'<w:tblPr><w:tblW w:w="{total}" w:type="dxa"/>{borders}'
        f'<w:tblLook w:val="04A0"/></w:tblPr>'
    )

    def cell(content: str, bold: bool) -> str:
        rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
        return (
            f'<w:tc><w:tcPr><w:tcW w:w="{col_w}" w:type="dxa"/></w:tcPr>'
            f"<w:p><w:r>{rpr}<w:t xml:space=\"preserve\">{_escape_xml(str(content))}</w:t></w:r></w:p></w:tc>"
        )

    header_row = (
        "<w:tr><w:tblPrEx><w:tblBorders>" + borders + "</w:tblBorders></w:tblPrEx>"
        + "".join(cell(h, True) for h in headers)
        + "</w:tr>"
    )
    body_rows = "".join(
        "<w:tr>" + "".join(cell(c, False) for c in row) + "</w:tr>" for row in rows
    )
    return f"<w:tbl>{tblpr}<w:tblGrid>{grid}</w:tblGrid>{header_row}{body_rows}</w:tbl>"


def render_docx(blocks: list[dict], title: str) -> bytes:
    body = []
    for b in blocks:
        t = b.get("t")
        if t == "title":
            body.append(_docx_para(b["text"], "Title"))
        elif t == "h2":
            body.append(_docx_para(b["text"], "Heading1"))
        elif t == "h3":
            body.append(_docx_para(b["text"], "Heading2"))
        elif t == "p":
            body.append(_docx_para(b["text"]))
        elif t == "bullets":
            for it in b["items"]:
                body.append(_docx_para("• " + str(it)))
        elif t == "table":
            body.append(_docx_table(b))
        elif t == "spacer":
            body.append('<w:p><w:r><w:t xml:space="preserve"> </w:t></w:r></w:p>')
        elif t == "rule":
            body.append(
                '<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" '
                'w:space="1" w:color="auto"/></w:pBdr></w:pPr></w:p>'
            )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>" + "".join(body) +
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        'w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
        "</w:body></w:document>"
    )

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
        '<w:rPr><w:rFonts w:eastAsia="SimSun"/><w:sz w:val="21"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/>'
        '<w:pPr><w:jc w:val="center"/><w:spacing w:before="240" w:after="120"/></w:pPr>'
        '<w:rPr><w:rFonts w:eastAsia="SimSun"/><w:b/><w:sz w:val="36"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>'
        '<w:next w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/></w:pPr>'
        '<w:rPr><w:rFonts w:eastAsia="SimSun"/><w:b/><w:sz w:val="28"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/>'
        '<w:next w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="200" w:after="100"/></w:pPr>'
        '<w:rPr><w:rFonts w:eastAsia="SimSun"/><w:b/><w:sz w:val="24"/></w:rPr></w:style>'
        "</w:styles>"
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    core = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{_escape_xml(title)}</dc:title>"
        "<dc:creator>LawPilot</dc:creator>"
        f"<dcterms:created xsi:type=\"dcterms:W3CDTF\">{now}</dcterms:created>"
        f"<dcterms:modified xsi:type=\"dcterms:W3CDTF\">{now}</dcterms:modified>"
        "</cp:coreProperties>"
    )
    app = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
        "<Application>LawPilot</Application></Properties>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document_xml)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        z.writestr("word/styles.xml", styles)
        z.writestr("docProps/core.xml", core)
        z.writestr("docProps/app.xml", app)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 渲染：PDF（reportlab + 中文字体，可选）
# ---------------------------------------------------------------------------
_CJK_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    r"/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def _find_cjk_font() -> str | None:
    for p in _CJK_FONT_CANDIDATES:
        if __import__("os").path.isfile(p):
            return p
    return None


def render_pdf(blocks: list[dict], title: str) -> bytes | None:
    """生成中文 PDF；无 reportlab 或无中文字体时返回 None（调用方回退 docx）。"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except Exception:
        return None

    font_path = _find_cjk_font()
    if font_path is None:
        return None
    try:
        font_name = "CJK"
        pdfmetrics.registerFont(TTFont(font_name, font_path))
    except Exception:
        return None

    def rl_text(text: str) -> str:
        s = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        # 成对替换 **x** → <b>x</b>
        parts = s.split("**")
        out = []
        for i, seg in enumerate(parts):
            if i % 2 == 1:
                out.append(f"<b>{seg}</b>")
            else:
                out.append(seg)
        return "".join(out)

    styles = {
        "title": ParagraphStyle(
            "title", fontName=font_name, fontSize=18, leading=24,
            alignment=TA_CENTER, spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "h2", fontName=font_name, fontSize=13, leading=18, spaceBefore=10, spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "h3", fontName=font_name, fontSize=11, leading=16, spaceBefore=6, spaceAfter=4,
        ),
        "p": ParagraphStyle(
            "p", fontName=font_name, fontSize=9.5, leading=14, spaceAfter=4,
        ),
        "bullet": ParagraphStyle(
            "bullet", fontName=font_name, fontSize=9.5, leading=14,
            leftIndent=14, spaceAfter=2, bulletIndent=4,
        ),
    }

    story: list[Any] = []
    for b in blocks:
        t = b.get("t")
        if t == "title":
            story.append(Paragraph(rl_text(b["text"]), styles["title"]))
        elif t == "h2":
            story.append(Paragraph(rl_text(b["text"]), styles["h2"]))
        elif t == "h3":
            story.append(Paragraph(rl_text(b["text"]), styles["h3"]))
        elif t == "p":
            story.append(Paragraph(rl_text(b["text"]), styles["p"]))
        elif t == "bullets":
            for it in b["items"]:
                story.append(Paragraph("• " + rl_text(str(it)), styles["bullet"]))
        elif t == "table":
            headers = [Paragraph(rl_text(str(h)), styles["p"]) for h in b["headers"]]
            rows = [
                [Paragraph(rl_text(str(c)), styles["p"]) for c in row]
                for row in b["rows"]
            ]
            data = [headers] + rows
            tbl = Table(data, repeatRows=1, hAlign="LEFT")
            tbl.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ]
                )
            )
            story.append(tbl)
        elif t == "spacer":
            story.append(Spacer(1, 8))
        elif t == "rule":
            story.append(Spacer(1, 4))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=48, rightMargin=48, topMargin=48, bottomMargin=48,
        title=title,
    )
    try:
        doc.build(story)
    except Exception:
        return None
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 报告服务（查询）
# ---------------------------------------------------------------------------
class EvidenceReportService:
    """证据报告查询。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_report(
        self, case_id: UUID | None, report_type: str
    ) -> EvidenceReport | None:
        stmt = (
            select(EvidenceReport)
            .where(
                EvidenceReport.case_id == case_id,
                EvidenceReport.report_type == report_type,
            )
            .order_by(EvidenceReport.created_at.desc())
            .limit(1)
        )
        return (await self.db.scalars(stmt)).first()

    async def list_reports(self, case_id: UUID | None) -> list[EvidenceReport]:
        stmt = (
            select(EvidenceReport)
            .where(EvidenceReport.case_id == case_id)
            .order_by(EvidenceReport.created_at.desc())
        )
        return list((await self.db.scalars(stmt)).all())

    async def get_by_id(self, report_id: UUID) -> EvidenceReport | None:
        return await self.db.get(EvidenceReport, report_id)

    async def list_for_user(self, current: User) -> list[EvidenceReport]:
        """返回当前用户的全部报告（含未关联案件的临时报告），按生成时间倒序。

        超管可见全部；普通用户仅见自己创建的（``created_by``）。
        """
        conds = []
        if not current.is_superuser:
            conds.append(EvidenceReport.created_by == current.id)
        stmt = (
            select(EvidenceReport)
            .where(*conds)
            .order_by(EvidenceReport.created_at.desc())
        )
        return list((await self.db.scalars(stmt)).all())


# ---------------------------------------------------------------------------
# 生成编排
# ---------------------------------------------------------------------------
async def generate_evidence_report(
    *,
    current: User,
    db: AsyncSession,
    mgr: AIManager,
    case_id: UUID | None = None,
    evidence_ids: list[UUID] | None = None,
    report_type: str = "directory",
    regenerate: bool = False,
    user_id: UUID | None = None,
) -> tuple[EvidenceReport, bool]:
    """生成（或取回）一份证据报告。

    返回 ``(report, generated)``：``generated=True`` 表示本次新生成；``False`` 表示
    命中已存储的同类型报告且未要求 regenerate。
    """
    if report_type not in ("directory", "score", "missing", "strategy", "full"):
        report_type = "directory"

    # 缓存命中（仅案件级报告支持缓存）
    if case_id is not None and not regenerate:
        cached = await EvidenceReportService(db).get_report(case_id, report_type)
        if cached is not None:
            return cached, False

    data = await _load_report_data(
        current, case_id=case_id, evidence_ids=evidence_ids, db=db
    )

    # AI 叙事（仅 missing/strategy/full；且已有分析数据时才尝试）
    narrative: str | None = None
    model_id: UUID | None = None
    analysis_map = data["analysis_map"]
    if report_type in ("missing", "strategy", "full") and (
        analysis_map or data["evidences"]
    ):
        narrative, model_id = await _build_narrative(data, mgr, user_id)

    blocks = _assemble_blocks(data, report_type, narrative)
    markdown = render_markdown(blocks)
    title = REPORT_TITLE.get(report_type, "证据报告")

    now = datetime.now(timezone.utc)
    avg = None
    strengths = [a.proof_strength for a in analysis_map.values() if a.proof_strength]
    if strengths:
        avg = round(sum(strengths) / len(strengths), 1)
    content_json = {
        "report_type": report_type,
        "title": title,
        "case_id": str(case_id) if case_id else None,
        "evidence_count": len(data["evidences"]),
        "analyzed_count": len(analysis_map),
        "avg_proof_strength": avg,
        "ai_assisted": bool(narrative),
        "generated_at": _fmt_dt(now),
        "markdown": markdown,
        "blocks": blocks,
    }

    # 同 case + 同类型先删后插，保证只保留最新一条
    if case_id is not None:
        await db.execute(
            delete(EvidenceReport).where(
                EvidenceReport.case_id == case_id,
                EvidenceReport.report_type == report_type,
            )
        )

    report = EvidenceReport(
        case_id=case_id,
        title=title,
        report_type=EvidenceReportTypeEnum(report_type),
        content=content_json,
        format="markdown",
        created_by=user_id,
    )
    db.add(report)
    await db.flush()
    return report, True
