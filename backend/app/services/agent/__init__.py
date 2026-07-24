"""Agent 流程引擎包。

包含：确定性知识库(knowledge_base)、LLM 决策提示(prompts)、对话引擎(engine)、
案件报告生成(report)。
"""
from __future__ import annotations

from app.services.agent.engine import AgentEngine
from app.services.agent.knowledge_base import (
    CASE_TYPE_LABELS,
    DOC_TYPES,
    EVIDENCE_CHECKLIST,
    Question,
    script_for,
)
from app.services.agent.report import build_and_persist_report

__all__ = [
    "AgentEngine",
    "CASE_TYPE_LABELS",
    "DOC_TYPES",
    "EVIDENCE_CHECKLIST",
    "Question",
    "script_for",
    "build_and_persist_report",
]
