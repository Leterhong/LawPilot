"""案件报告生成器（Phase 6 核心产出）。

当 Agent 判定证据收集充足后调用，产出结构化「案件报告」并落库。报告严格遵循
产品定义的 11 个章节，且「涉及法律」章节强制走 RAG（Phase 5 混合检索），
保证引用可溯源、不凭空编造。

章节：案件类型 / 一句话结论 / 涉及法律(RAG) / 我的权益 / 对方可能存在的问题 /
建议准备证据 / 下一步怎么办(Roadmap) / 去哪里 / 自动生成文书 / 风险分析 /
免责声明。

两段式生成（v1.1 升级）
----------------------
1. **确定性底座**：案由模板 + RAG 法条，任何时候都成立；
2. **个性化增强**：把逐条追问收集到的事实连同法条一起交给模型，生成与个案
   强相关的结论/权益/对方问题/风险/取证建议，见 ``llm_report`` 模块。

模型未配置、超时或输出不合规时自动回退到第 1 段，报告不会降级为空白；
``report["meta"]`` 会记录本次实际使用的生成来源，便于评测与答辩时举证。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.enums import DocTypeEnum, EventTypeEnum
from app.models.evidence import Evidence
from app.models.workflow import Workflow
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
from app.services.agent.llm_report import generate_personalized_analysis, summarize_facts
from app.services.agent.prompts import DISCLAIMER
from app.services.legal_service import LegalService
from app.services.llm.client import LLMClient
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
    case: Case, session: AsyncSession, workflow: Optional[Workflow] = None
) -> Tuple[dict, List[dict]]:
    """构建报告并写回案件与关联资源。返回 (报告字典, 引用列表)。

    :param workflow: Agent 工作流（含 ``collected_fields``）。传入后即可启用
        个性化分析；缺省时行为与升级前一致（纯模板 + RAG）。
    """
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

    # 2) 个性化分析（LLM 增强，失败自动回退模板）
    analysis = await generate_personalized_analysis(
        case, workflow, citations, LLMClient(db=session, feature="agent_report")
    )
    facts = summarize_facts(case, workflow)

    # 3) 证据（已上传 + 建议清单）
    evidence_repo = EvidenceRepository(session)
    uploaded: List[Evidence] = await evidence_repo.list(case_id=case.id)
    uploaded_titles = [e.title for e in uploaded]
    checklist = EVIDENCE_CHECKLIST.get(ctype, [])
    evidence_block = {
        "uploaded": uploaded_titles,
        "checklist": checklist,
    }

    # 4) 下一步（Roadmap）
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

    # 5) 去哪里
    where_to_go = DEPARTMENTS.get(ctype, [])

    # 6) 自动生成文书
    docs = [
        {"type": t.value, "label": DOC_TYPE_LABELS.get(t, t.value)}
        for t in DOC_TYPES.get(ctype, [])
    ]

    # 7) 风险分析
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
        "suggestion": (
            analysis.sections["risk_suggestion"]
            if analysis.is_llm
            else "尽快补充上述证据清单中的材料，留意诉讼时效与举证期限。"
        ),
    }

    # 8) 组装报告（LLM 可用时以个性化内容覆盖模板段落）
    sec = analysis.sections
    report: dict[str, Any] = {
        "case_type": label,
        "conclusion": sec.get("conclusion") or CONCLUSION.get(ctype, ""),
        "facts": facts,
        "legal": legal_block,
        "rights": sec.get("rights") or RIGHTS.get(ctype, ""),
        "counterparty_issues": sec.get("counterparty_issues") or COUNTERPARTY.get(ctype, ""),
        "evidence": evidence_block,
        "next_steps": next_steps,
        "where_to_go": where_to_go,
        "documents": docs,
        "risk": risk_block,
        "disclaimer": DISCLAIMER,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        # 生成来源与引用轨迹：用于前端标注、评测统计与答辩举证
        "meta": {
            "analysis_source": analysis.source,
            "fallback_reason": analysis.reason,
            "cited_articles": analysis.cited,
            "fact_count": len(facts),
            "citation_count": len(citations),
        },
    }
    if analysis.is_llm and sec.get("evidence_advice"):
        report["evidence"]["advice"] = sec["evidence_advice"]

    # 9) 落库：结构化报告 + 各沉淀字段 + 状态
    case.report = report
    case.legal_references = citations
    case.summary = report["conclusion"]
    case.conclusion = report["conclusion"]
    case.rights_analysis = report["rights"]
    case.counterparty_issues = report["counterparty_issues"]
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
        detail=(
            f"{label} · 涉及法律 {len(citations)} 条 · "
            f"{'AI 个性化分析' if analysis.is_llm else '规则模板生成'}"
        ),
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
