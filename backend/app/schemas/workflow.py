"""工作流状态响应模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.enums import WorkflowStageEnum


class WorkflowOut(BaseModel):
    """Agent 工作流当前状态。"""

    stage: WorkflowStageEnum
    collected_fields: dict | None
    missing_fields: list[str] | None
    next_question: str | None
    is_complete: bool
    updated_at: datetime

    model_config = {"from_attributes": True}
