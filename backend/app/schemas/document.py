"""文书相关请求/响应模型。"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import DocStatusEnum, DocTypeEnum


class DocumentGenerate(BaseModel):
    """生成文书请求。"""

    doc_type: DocTypeEnum = Field(..., description="文书类型")
    extra: dict | None = Field(None, description="覆盖字段，如对方姓名、金额、日期")


class DocumentOut(BaseModel):
    """文书输出。"""

    id: UUID
    case_id: UUID | None
    user_id: UUID | None
    doc_type: DocTypeEnum
    title: str
    content: str
    status: DocStatusEnum
    created_at: datetime

    model_config = {"from_attributes": True}
