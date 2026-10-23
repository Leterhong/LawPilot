"""任务模型（tasks 表）。

从 Roadmap 派生的具体待办，或用户/Agent 手动创建的提醒。驱动「下一步怎么办」
以及首页的待办提醒。与案件关联，可设置到期日与优先级。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import PriorityEnum, TaskStatusEnum


class Task(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_case_status", "case_id", "status"),
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
        comment="归属用户",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="任务标题")
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="任务说明"
    )
    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="到期时间"
    )
    status: Mapped[TaskStatusEnum] = mapped_column(
        Enum(TaskStatusEnum, values_callable=lambda e: [x.value for x in e], native_enum=False), default=TaskStatusEnum.TODO, index=True, nullable=False,
        comment="任务状态",
    )
    priority: Mapped[PriorityEnum] = mapped_column(
        Enum(PriorityEnum, values_callable=lambda e: [x.value for x in e], native_enum=False), default=PriorityEnum.MEDIUM, nullable=False, comment="优先级"
    )

    case = relationship("Case", back_populates="tasks")
