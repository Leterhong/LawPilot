"""案件模型（cases 表）。

LawPilot 的核心聚合根：一个案件串联消息、证据、文书、Roadmap、任务、时间线。
案件报告的关键字段（结论/权益/对方问题/风险/推荐部门）直接沉淀在案件上，
便于列表展示与历史回看，而不必每次重算。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import CaseStatusEnum, CaseTypeEnum


class Case(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "cases"
    __table_args__ = (
        Index("ix_cases_user_status", "user_id", "status"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="所属用户",
    )
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="案件标题（用户可见）"
    )
    case_type: Mapped[CaseTypeEnum] = mapped_column(
        Enum(CaseTypeEnum, values_callable=lambda e: [x.value for x in e], native_enum=False), index=True, nullable=False, comment="案件类型"
    )
    status: Mapped[CaseStatusEnum] = mapped_column(
        Enum(CaseStatusEnum, values_callable=lambda e: [x.value for x in e], native_enum=False),
        default=CaseStatusEnum.INTAKE,
        index=True,
        nullable=False,
        comment="案件状态",
    )
    # 用户输入的原始遭遇描述
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="用户初始描述"
    )
    # —— 案件报告沉淀字段（由 Agent 在证据充足后写入）——
    summary: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="AI 案情摘要"
    )
    conclusion: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="一句话结论"
    )
    rights_analysis: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="我的权益分析"
    )
    counterparty_issues: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="对方可能存在的问题"
    )
    risk_analysis: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="风险分析（证据完整度/复杂度/程序建议等）"
    )
    recommended_departments: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="推荐办理部门及理由"
    )
    current_stage: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="当前所处工作流阶段"
    )
    # —— 结构化案件报告（Agent 证据充足后生成）——
    report: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="结构化案件报告（11 章节）"
    )
    legal_references: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="报告引用的法律条文（RAG 检索结果）"
    )
    report_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="报告生成时间"
    )
    # —— 关系 ——
    user = relationship("User", back_populates="cases")
    messages = relationship(
        "Message",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="Message.sequence",
    )
    evidence = relationship(
        "Evidence", back_populates="case", cascade="all, delete-orphan"
    )
    documents = relationship(
        "Document", back_populates="case", cascade="all, delete-orphan"
    )
    roadmaps = relationship(
        "Roadmap", back_populates="case", cascade="all, delete-orphan"
    )
    tasks = relationship(
        "Task", back_populates="case", cascade="all, delete-orphan"
    )
    histories = relationship(
        "History", back_populates="case", cascade="all, delete-orphan",
        order_by="History.created_at",
    )
    workflow = relationship(
        "Workflow",
        back_populates="case",
        cascade="all, delete-orphan",
        uselist=False,
    )
