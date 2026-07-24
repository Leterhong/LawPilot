"""证据相关请求/响应模型。"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import EvidenceCategoryEnum


class EvidenceOut(BaseModel):
    """证据输出。"""

    id: UUID
    case_id: UUID
    user_id: UUID | None
    category: EvidenceCategoryEnum
    title: str
    description: str | None
    file_path: str | None
    file_type: str | None
    ocr_text: str | None
    is_uploaded: bool
    ai_note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class EvidencePlannedCreate(BaseModel):
    """添加「规划中但尚未提供」的证据项。"""

    category: EvidenceCategoryEnum
    title: str = Field(..., max_length=200)
    description: str | None = None
    ai_note: str | None = None
