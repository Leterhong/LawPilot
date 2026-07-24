"""通用响应模型。

提供分页包装 ``Page``，统一列表接口的返回结构。
"""
from __future__ import annotations

from typing import Generic, List, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """分页响应包装。"""

    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def create(
        cls, items: List[T], total: int, page: int, page_size: int
    ) -> "Page[T]":
        pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items, total=total, page=page, page_size=page_size, pages=pages
        )
