"""任务相关请求/响应模型。"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import PriorityEnum, TaskStatusEnum


class TaskUpdate(BaseModel):
    """任务更新请求。"""

    title: str | None = Field(None, max_length=200)
    description: str | None = None
    due_date: datetime | None = None
    status: TaskStatusEnum | None = None
    priority: PriorityEnum | None = None


class TaskOut(BaseModel):
    """任务输出。"""

    id: UUID
    case_id: UUID
    user_id: UUID | None
    title: str
    description: str | None
    due_date: datetime | None
    status: TaskStatusEnum
    priority: PriorityEnum
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
