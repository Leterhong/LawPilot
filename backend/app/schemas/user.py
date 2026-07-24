"""用户相关请求/响应模型。"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    """注册请求。"""

    email: str = Field(..., max_length=255, description="登录邮箱")
    password: str = Field(..., min_length=8, max_length=128, description="密码（≥8位）")
    display_name: str | None = Field(None, max_length=64, description="昵称")


class UserUpdate(BaseModel):
    """资料更新请求（仅可改字段）。"""

    display_name: str | None = Field(None, max_length=64)
    avatar_url: str | None = Field(None, max_length=512)


class UserOut(BaseModel):
    """用户对外输出（不含密码）。"""

    id: UUID
    email: str
    display_name: str | None
    avatar_url: str | None
    is_active: bool
    is_verified: bool
    is_superuser: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}
