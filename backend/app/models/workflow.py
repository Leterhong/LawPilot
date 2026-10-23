"""Agent 工作流状态模型（workflow 表）。

作为 Agent 的状态机持久化点。每个案件对应一条 workflow 记录，保存当前阶段、
已收集的关键事实、尚缺字段、下一步要问的问题。Agent 每轮推理后更新此处，
实现「持续追问 → 收集证据 → 生成报告」的可恢复流程。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin
from app.models.enums import WorkflowStageEnum


class Workflow(UUIDMixin, Base):
    __tablename__ = "workflow"
    __table_args__ = (
        Index("ix_workflow_case_stage", "case_id", "stage"),
    )

    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        index=True,
        unique=True,
        nullable=False,
        comment="所属案件（一一对应）",
    )
    stage: Mapped[WorkflowStageEnum] = mapped_column(
        Enum(WorkflowStageEnum, values_callable=lambda e: [x.value for x in e], native_enum=False), default=WorkflowStageEnum.IDENTIFY, nullable=False, comment="当前阶段"
    )
    # 已收集的事实字段（结构化，如 {has_contract: true, deposit: 3000}）
    collected_fields: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="已收集事实"
    )
    # 还缺哪些字段（Agent 据此决定追问）
    missing_fields: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True, comment="待收集字段列表"
    )
    # 下一步要向用户提出的问题（含可选项）
    next_question: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="下一轮追问内容"
    )
    is_complete: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否已完成证据收集、可出报告"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False, comment="状态更新时间",
    )

    case = relationship("Case", back_populates="workflow")
