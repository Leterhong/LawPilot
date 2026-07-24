"""Agent 对话相关请求/响应模型。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.case import CaseOut
from app.schemas.message import MessageOut
from app.schemas.workflow import WorkflowOut


class ChatRequest(BaseModel):
    """发送一条对话消息（用户侧）。"""

    content: str = Field(..., min_length=1, description="用户消息内容")


class ChatResponse(BaseModel):
    """一轮对话的返回。"""

    assistant_message: MessageOut
    case: CaseOut
    workflow: WorkflowOut
    report_generated: bool = Field(..., description="本轮是否触发了报告生成")
    suggested_evidence: list[str] = Field(default_factory=list, description="建议准备的证据清单")
    available_documents: list[dict] = Field(
        default_factory=list, description="可自动生成的文书类型 [{type, label}]"
    )


class AgentStateResponse(BaseModel):
    """拉取案件对话状态的返回。"""

    case: CaseOut
    workflow: WorkflowOut
    messages: list[MessageOut]
