"""时间线事件相关响应模型。"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import EventTypeEnum


class HistoryOut(BaseModel):
    """时间线事件输出。"""

    id: UUID
    case_id: UUID
    user_id: UUID | None
    event_type: EventTypeEnum
    title: str
    detail: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
