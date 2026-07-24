"""Roadmap 相关请求/响应模型。"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import StepStatusEnum


class RoadmapStepOut(BaseModel):
    """Roadmap 步骤输出。"""

    id: UUID
    roadmap_id: UUID
    title: str
    description: str | None
    order: int
    due_offset_days: int | None
    status: StepStatusEnum
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RoadmapStepUpdate(BaseModel):
    """步骤状态更新请求。"""

    status: StepStatusEnum


class RoadmapOut(BaseModel):
    """Roadmap 完整输出（含步骤列表）。"""

    id: UUID
    case_id: UUID
    title: str
    is_active: bool
    steps: list[RoadmapStepOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
