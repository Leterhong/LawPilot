"""Agent 对话路由。

提供案件内的多轮对话能力：
- ``POST /cases/{case_id}/chat``：发送一条用户消息，由 Agent 引擎处理
  （追问收集证据 / 生成报告），返回 assistant 回复、案件状态、工作流与报告标记。
- ``GET /cases/{case_id}/agent/state``：拉取对话状态（含首问初始化与历史消息），
  供前端进入对话页时渲染。

两个端点均通过 ``get_owned_case`` 校验归属。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, get_owned_case
from app.models.case import Case
from app.models.message import Message
from app.models.user import User
from app.schemas.agent import AgentStateResponse, ChatRequest, ChatResponse
from app.services.agent.engine import AgentEngine
from app.services.agent.knowledge_base import DOC_TYPES, EVIDENCE_CHECKLIST
from app.services.agent.report import DOC_TYPE_LABELS

router = APIRouter(prefix="/cases", tags=["agent"])


@router.post("/{case_id}/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    case: Case = Depends(get_owned_case),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """处理一轮用户对话，返回 Agent 回复与最新状态。"""
    engine = AgentEngine(db)
    turn = await engine.respond(case, body.content, current)

    ctype = case.case_type
    suggested = EVIDENCE_CHECKLIST.get(ctype, [])
    docs = [
        {"type": t.value, "label": DOC_TYPE_LABELS.get(t, t.value)}
        for t in DOC_TYPES.get(ctype, [])
    ]
    return ChatResponse(
        assistant_message=turn.assistant_message,
        case=turn.case,
        workflow=turn.workflow,
        report_generated=turn.report_generated,
        suggested_evidence=suggested,
        available_documents=docs,
    )


@router.get("/{case_id}/agent/state", response_model=AgentStateResponse)
async def agent_state(
    case: Case = Depends(get_owned_case),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentStateResponse:
    """拉取对话状态（首问在此初始化），供前端渲染对话页。"""
    engine = AgentEngine(db)
    wf, _ = await engine.get_state(case)
    messages = await engine.messages.list(order_by=Message.sequence, case_id=case.id)
    return AgentStateResponse(case=case, workflow=wf, messages=list(messages))
