"""法律搜索历史模型（law_search_history 表）。

支撑 ``GET /api/laws/history`` 与热门搜索统计。与 ``law`` 表解耦：
记录用户（匿名则为 NULL）的查询词与命中数，便于「最近搜索 / 热门搜索」
展示。删除用户时不级联删除历史（保留聚合价值）。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class LawSearchHistory(UUIDMixin, Base):
    """一条搜索历史记录。"""

    __tablename__ = "law_search_history"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="用户ID（匿名搜索为 NULL）",
    )
    query: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        index=True,
        comment="查询词",
    )
    result_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="本次搜索命中条数",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="搜索时间（UTC）",
    )
