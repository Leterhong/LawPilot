"""案件时间线模型（history 表）。

记录案件全生命周期关键事件，构成「时间线」视图：创建、消息、加证据、
生成报告、生成文书、状态变更、任务完成、系统提醒。便于用户回看维权全过程。
"""
from __future__ import annotations

from sqlalchemy import (
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import EventTypeEnum


class History(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "history"
    __table_args__ = (
        Index("ix_history_case_created", "case_id", "created_at"),
    )

    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="所属案件",
    )
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
        comment="触发用户（系统事件为空）",
    )
    event_type: Mapped[EventTypeEnum] = mapped_column(
        Enum(EventTypeEnum, values_callable=lambda e: [x.value for x in e], native_enum=False), index=True, nullable=False, comment="事件类型"
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="事件标题")
    detail: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="事件详情"
    )

    case = relationship("Case", back_populates="histories")
