"""案件报告生成器（Phase 6 核心产出）。

当 Agent 判定证据收集充足后调用，产出结构化「案件报告」并落库。报告严格遵循
产品定义的 11 个章节，且「涉及法律」章节强制走 RAG（Phase 5 混合检索），
保证引用可溯源、不凭空编造。

章节：案件类型 / 一句话结论 / 涉及法律(RAG) / 我的权益 / 对方可能存在的问题 /
建议准备证据 / 下一步怎么办(Roadmap) / 去哪里 / 自动生成文书 / 风险分析 /
免责声明。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.enums import DocTypeEnum, EventTypeEnum, StepStatusEnum
from app.models.evidence import Evidence
from app.repositories.case_repo import EvidenceRepository
from app.repositories.task_repo import HistoryRepository
from app.schemas.legal import LegalSearchQuery
from app.services.agent.knowledge_base import (
    CASE_TYPE_LABELS,
    CONCLUSION,
    COUNTERPARTY,
    DEPARTMENTS,
    DOC_TYPES,
    EVIDENCE_CHECKLIST,
    RIGHTS,
    RISK_NOTES,
    build_legal_query,
)
from app.services.agent.prompts import DISCLAIMER
from app.services.legal_service import LegalService
from app.services.roadmap_service import RoadmapService

# 文书类型中文标签
DOC_TYPE_LABELS: dict[DocTypeEnum, str] = {
    DocTypeEnum.DUNNING_LETTER: "催告函",
    DocTypeEnum.LAWYER_LETTER: "律师函",
    DocTypeEnum.COMPLAINT: "投诉书",
    DocTypeEnum.ARBITRATION: "仲裁申请书",
    DocTypeEnum.LAWSUIT: "民事起诉状",
    DocTypeEnum.DEFENSE: "答辩状",
    DocTypeEnum.EVIDENCE_LIST: "证据目录",
}


async def build_and_persist_report(
    case: Case, session: AsyncSession
) -> Tuple[dict, List[dict]]:
    """构建报告并写回案件与关联资源。返回 (报告字典, 引用列表)。"""
    ctype = case.case_type
    label = CASE_TYPE_LABELS.get(ctype, "纠纷")

    # 1) 涉及法律（强制 RAG）
    legal_query = build_legal_query(case)
    svc = LegalService(session)
    query = LegalSearchQuery(q=legal_query, limit=8, use_rerank=True)
    _results, citations, _used_hybrid, _used_rerank = await svc.hybrid_search(query)
    legal_md = _format_legal_markdown(citations)
    legal_block = {
        "query": legal_query,
        "markdown": legal_md,
        "citations": citations,
        "note": "以上条文由知识库混合检索返回，请以官方发布版本为准。",
    }

    # 2) 证据（已上传 + 建议清单）
    evidence_repo = EvidenceRepository(session)
    uploaded: List[Evidence] = await evidence_repo.list(case_id=case.id)
    uploaded_titles = [e.title for e in uploaded]
    evidence_block = {
        "uploaded": uploaded_titles,
        "checklist": EVIDENCE_CHECKLIST.get(ctype, []),
    }

    # 3) 下一步（Roadmap）
    roadmap = await RoadmapService(session).generate(case)
    next_steps = [
        {
            "order": s.order,
            "title": s.title,
            "description": s.description,
            "due_offset_days": s.due_offset_days,
            "status": s.status.value,
        }
        for s in (roadmap.steps or [])
    ]

    # 4) 去哪里
    where_to_go = DEPARTMENTS.get(ctype, [])

    # 5) 自动生成文书
    docs = [
        {"type": t.value, "label": DOC_TYPE_LABELS.get(t, t.value)}
        for t in DOC_TYPES.get(ctype, [])
    ]

    # 6) 风险分析
    risk_block = {
        "evidence_completeness": (
            f"已上传 {len(uploaded_titles)} 项证据" if uploaded_titles else "尚未上传任何证据"
        ),
        "complexity": (
            "事实较清晰，按路线图推进即可"
            if len(uploaded_titles) >= 2
            else "证据尚不充分，建议优先固定并补充关键材料"
        ),
        "limitation": RISK_NOTES.get(ctype, "请尽早固定证据，注意诉讼时效。"),
        "suggestion": "尽快补充上述证据清单中的材料，留意诉讼时效与举证期限。",
    }

    # 7) 组装报告
    report: dict[str, Any] = {
        "case_type": label,
        "conclusion": CONCLUSION.get(ctype, ""),
        "legal": legal_block,
        "rights": RIGHTS.get(ctype, ""),
        "counterparty_issues": COUNTERPARTY.get(ctype, ""),
        "evidence": evidence_block,
        "next_steps": next_steps,
        "where_to_go": where_to_go,
        "documents": docs,
        "risk": risk_block,
        "disclaimer": DISCLAIMER,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # 8) 落库：结构化报告 + 各沉淀字段 + 状态
    case.report = report
    case.legal_references = citations
    case.summary = CONCLUSION.get(ctype, "")
    case.conclusion = CONCLUSION.get(ctype, "")
    case.rights_analysis = RIGHTS.get(ctype, "")
    case.counterparty_issues = COUNTERPARTY.get(ctype, "")
    case.risk_analysis = risk_block
    case.recommended_departments = where_to_go
    case.report_generated_at = datetime.now(timezone.utc)
    session.add(case)
    await session.commit()
    await session.refresh(case)

    # 时间线：报告生成事件
    history = HistoryRepository(session)
    await history.create(
        case_id=case.id,
        user_id=case.user_id,
        event_type=EventTypeEnum.REPORT_GENERATED,
        title="生成案件报告",
        detail=f"{label} · 涉及法律 {len(citations)} 条",
    )

    return report, citations


def _format_legal_markdown(citations: List[dict]) -> str:
    """把引用列表渲染为 Markdown 列表（取前 5 条）。"""
    if not citations:
        return "（暂未检索到高度相关的法律条文，建议补充案情后重试，或咨询专业律师。）"
    lines = []
    for c in citations[:5]:
        label = c.get("label") or c.get("title") or "法律条文"
        snippet = c.get("snippet") or ""
        lines.append(f"- **{label}**：{snippet}")
    return "\n".join(lines)
