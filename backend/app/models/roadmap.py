"""办理路线图模型（roadmaps / roadmap_steps 表）。

每个案件对应一份 Roadmap（建议只保留一份进行中）。Roadmap 由若干有序步骤
组成（如 Day1 保存证据 → Day2 发催告函 → 等待 → 投诉 → 法院），
步骤可在办理过程中被标记为完成/跳过，驱动首页「下一步」与 Agent 提醒。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import StepStatusEnum


class Roadmap(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "roadmaps"

    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        index=True,
        unique=True,
        nullable=False,
        comment="所属案件（一个案件一份 Roadmap）",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="路线图标题")
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="是否为当前生效路线图"
    )

    case = relationship("Case", back_populates="roadmaps")
    steps = relationship(
        "RoadmapStep",
        back_populates="roadmap",
        cascade="all, delete-orphan",
        order_by="RoadmapStep.order",
    )


class RoadmapStep(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "roadmap_steps"
    __table_args__ = (
        Index("ix_roadmap_steps_roadmap_order", "roadmap_id", "order"),
    )

    roadmap_id: Mapped[str] = mapped_column(
        ForeignKey("roadmaps.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="所属路线图",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="步骤标题")
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="步骤说明"
    )
    order: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="排序序号（从 1 开始）"
    )
    # 相对案件创建日的建议偏移天数（用于自动排期/提醒）
    due_offset_days: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="建议在第 N 天执行"
    )
    status: Mapped[StepStatusEnum] = mapped_column(
        Enum(StepStatusEnum, values_callable=lambda e: [x.value for x in e], native_enum=False), default=StepStatusEnum.PENDING, nullable=False, comment="步骤状态"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="完成时间"
    )

    roadmap = relationship("Roadmap", back_populates="steps")
