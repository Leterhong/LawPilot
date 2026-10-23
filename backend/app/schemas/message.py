"""消息相关请求/响应模型。"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import MessageTypeEnum, RoleEnum


class MessageCreate(BaseModel):
    """发送消息请求。"""

    content: str = Field(..., min_length=1, description="消息内容")
    role: RoleEnum = RoleEnum.USER
    message_type: MessageTypeEnum = MessageTypeEnum.TEXT
    metadata_json: dict | None = Field(None, description="引用来源/关联证据等元数据")


class MessageOut(BaseModel):
    """消息输出。"""

    id: UUID
    case_id: UUID
    role: RoleEnum
    message_type: MessageTypeEnum
    content: str
    sequence: int
    metadata_json: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
