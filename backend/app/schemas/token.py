"""令牌相关模型。"""
from __future__ import annotations

from pydantic import BaseModel


class Token(BaseModel):
    """登录成功后返回的访问令牌。"""

    access_token: str
    token_type: str = "bearer"
