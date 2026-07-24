"""案件中心模型（Case Center 模块，Phase 3）。

独立于 Phase 1/2 的 ``cases`` 聚合根，本模块以「用户视角的办事中心」组织数据：
- ``case_center``：案件卡片（名称/类型/状态/优先级/负责人/收藏/标签/颜色/封面/排序）
- ``case_analysis``：AI 分析结果（摘要/风险/建议状态/下一步/时间线）
- ``case_evidence``：证据清单
- ``case_documents``：文书
- ``case_tasks``：待办任务
- ``case_timeline``：时间线事件
- ``case_notes``：备注

命名上基础表使用 ``case_center``（避免与已有 ``cases`` 冲突），其余子表沿用
产品规范中的名称（case_analysis / case_evidence / case_documents / case_tasks /
case_timeline / case_notes）。所有写操作均通过外键级联，删除案件卡片时子资源一并清除。
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
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import (
    CaseCenterStatusEnum,
    CaseTypeEnum,
    DocStatusEnum,
    DocTypeEnum,
    EvidenceCategoryEnum,
    PriorityEnum,
    TaskStatusEnum,
)


class CaseCenter(UUIDMixin, TimestampMixin, Base):
    """案件中心卡片（case_center 表）。"""

    __tablename__ = "case_center"
    __table_args__ = (
        Index("ix_case_center_user_status", "user_id", "status"),
        Index("ix_case_center_user_position", "user_id", "position"),
    )

    # 归属账户（创建人，默认当前用户）
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="所属用户（账户级归属）",
    )
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="案件名称（用户可见）"
    )
    case_type: Mapped[CaseTypeEnum] = mapped_column(
        Enum(CaseTypeEnum, values_callable=lambda e: [x.value for x in e], native_enum=False),
        index=True,
        nullable=False,
        comment="案件类型",
    )
    status: Mapped[CaseCenterStatusEnum] = mapped_column(
        Enum(CaseCenterStatusEnum, values_callable=lambda e: [x.value for x in e], native_enum=False),
        default=CaseCenterStatusEnum.PENDING,
        index=True,
        nullable=False,
        comment="案件状态（8 档）",
    )
    priority: Mapped[PriorityEnum] = mapped_column(
        Enum(PriorityEnum, values_callable=lambda e: [x.value for x in e], native_enum=False),
        default=PriorityEnum.MEDIUM,
        nullable=False,
        comment="优先级",
    )
    # 负责人展示名（默认当前用户昵称，可改）
    owner: Mapped[str | None] = mapped_column(
        String(120), nullable=True, comment="负责人（展示名，默认当前用户）"
    )
    # 收藏 / 星标（列表页快速筛选）
    starred: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否星标"
    )
    favorite: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否收藏"
    )
    # 标签（自由标签，用于筛选）
    tags: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="标签列表（字符串数组）"
    )
    # 颜色标签（卡片配色）
    color: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="颜色标签（如 #4F46E5）"
    )
    # 封面图
    cover_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="封面图地址"
    )
    # 拖拽排序序号（越小越靠前）
    position: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="排序序号（拖拽排序）"
    )
    # 初始描述
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="案件初始描述"
    )

    # —— 关系（级联删除）——
    analyses = relationship(
        "CaseAnalysis", back_populates="case", cascade="all, delete-orphan",
        order_by="CaseAnalysis.created_at.desc()",
    )
    evidences = relationship(
        "CaseEvidence", back_populates="case", cascade="all, delete-orphan",
        order_by="CaseEvidence.created_at",
    )
    documents = relationship(
        "CaseDocument", back_populates="case", cascade="all, delete-orphan",
        order_by="CaseDocument.created_at.desc()",
    )
    tasks = relationship(
        "CaseTask", back_populates="case", cascade="all, delete-orphan",
        order_by="CaseTask.position",
    )
    timelines = relationship(
        "CaseTimeline", back_populates="case", cascade="all, delete-orphan",
        order_by="CaseTimeline.occurred_at",
    )
    notes = relationship(
        "CaseNote", back_populates="case", cascade="all, delete-orphan",
        order_by="CaseNote.created_at.desc()",
    )


class CaseAnalysis(UUIDMixin, TimestampMixin, Base):
    """AI 案件分析（case_analysis 表）。每次分析追加一条，概览取最新一条。"""

    __tablename__ = "case_analysis"
    __table_args__ = (
        Index("ix_case_analysis_case", "case_id", "created_at"),
    )

    case_id: Mapped[str] = mapped_column(
        ForeignKey("case_center.id", ondelete="CASCADE"),
        index=True, nullable=False, comment="所属案件卡片",
    )
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True, nullable=True, comment="触发分析的用户",
    )
    # 分析类型（initial=初诊 / deep=深度）
    analysis_type: Mapped[str] = mapped_column(
        String(32), default="initial", nullable=False, comment="分析类型"
    )
    summary: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="AI 案情摘要"
    )
    risk: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="AI 风险分析（文字）"
    )
    risk_level: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="风险等级（low/medium/high）"
    )
    # AI 建议的案件状态（供前端一键采纳）
    suggested_status: Mapped[CaseCenterStatusEnum | None] = mapped_column(
        Enum(CaseCenterStatusEnum, values_callable=lambda e: [x.value for x in e], native_enum=False),
        nullable=True, comment="AI 建议状态",
    )
    # 下一步行动（字符串数组）
    next_steps: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="下一步行动清单"
    )
    # 原始结构化输出（保留完整 AI 结果）
    raw: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="原始分析结果（完整 JSON）"
    )

    case = relationship("CaseCenter", back_populates="analyses")


class CaseEvidence(UUIDMixin, TimestampMixin, Base):
    """证据清单（case_evidence 表）。"""

    __tablename__ = "case_evidence"
    __table_args__ = (
        Index("ix_case_evidence_case_cat", "case_id", "category"),
    )

    case_id: Mapped[str] = mapped_column(
        ForeignKey("case_center.id", ondelete="CASCADE"),
        index=True, nullable=False, comment="所属案件卡片",
    )
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True, nullable=True, comment="上传人",
    )
    category: Mapped[EvidenceCategoryEnum] = mapped_column(
        Enum(EvidenceCategoryEnum, values_callable=lambda e: [x.value for x in e], native_enum=False),
        index=True, nullable=False, comment="证据类别",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="证据名称")
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="证据说明"
    )
    file_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="文件存储路径"
    )
    file_type: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="文件扩展名"
    )
    ocr_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="OCR 识别文本"
    )
    is_uploaded: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否已实际提供"
    )
    ai_note: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="AI 对证据作用的分析"
    )

    case = relationship("CaseCenter", back_populates="evidences")


class CaseDocument(UUIDMixin, TimestampMixin, Base):
    """文书（case_documents 表）。"""

    __tablename__ = "case_documents"
    __table_args__ = (
        Index("ix_case_documents_case_type", "case_id", "doc_type"),
    )

    case_id: Mapped[str] = mapped_column(
        ForeignKey("case_center.id", ondelete="CASCADE"),
        index=True, nullable=False, comment="所属案件卡片",
    )
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True, nullable=True, comment="生成人",
    )
    doc_type: Mapped[DocTypeEnum] = mapped_column(
        Enum(DocTypeEnum, values_callable=lambda e: [x.value for x in e], native_enum=False),
        index=True, nullable=False, comment="文书类型",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="文书标题")
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="文书正文（Markdown）"
    )
    status: Mapped[DocStatusEnum] = mapped_column(
        Enum(DocStatusEnum, values_callable=lambda e: [x.value for x in e], native_enum=False),
        default=DocStatusEnum.DRAFT, nullable=False, comment="文书状态",
    )
    file_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="导出文件路径"
    )

    case = relationship("CaseCenter", back_populates="documents")


class CaseTask(UUIDMixin, TimestampMixin, Base):
    """待办任务（case_tasks 表）。"""

    __tablename__ = "case_tasks"
    __table_args__ = (
        Index("ix_case_tasks_case_status", "case_id", "status"),
    )

    case_id: Mapped[str] = mapped_column(
        ForeignKey("case_center.id", ondelete="CASCADE"),
        index=True, nullable=False, comment="所属案件卡片",
    )
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True, nullable=True, comment="归属用户",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="任务标题")
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="任务说明"
    )
    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="到期时间"
    )
    status: Mapped[TaskStatusEnum] = mapped_column(
        Enum(TaskStatusEnum, values_callable=lambda e: [x.value for x in e], native_enum=False),
        default=TaskStatusEnum.TODO, index=True, nullable=False, comment="任务状态",
    )
    priority: Mapped[PriorityEnum] = mapped_column(
        Enum(PriorityEnum, values_callable=lambda e: [x.value for x in e], native_enum=False),
        default=PriorityEnum.MEDIUM, nullable=False, comment="优先级",
    )
    position: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="排序序号"
    )

    case = relationship("CaseCenter", back_populates="tasks")


class CaseTimeline(UUIDMixin, TimestampMixin, Base):
    """时间线事件（case_timeline 表）。"""

    __tablename__ = "case_timeline"
    __table_args__ = (
        Index("ix_case_timeline_case_occurred", "case_id", "occurred_at"),
    )

    case_id: Mapped[str] = mapped_column(
        ForeignKey("case_center.id", ondelete="CASCADE"),
        index=True, nullable=False, comment="所属案件卡片",
    )
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True, nullable=True, comment="触发用户（系统事件为空）",
    )
    event_type: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False, comment="事件类型"
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="事件标题")
    detail: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="事件详情"
    )
    # 事件实际发生时间（允许自定义，区别于创建时间）
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False, comment="事件发生时间",
    )

    case = relationship("CaseCenter", back_populates="timelines")


class CaseNote(UUIDMixin, TimestampMixin, Base):
    """备注（case_notes 表）。"""

    __tablename__ = "case_notes"

    case_id: Mapped[str] = mapped_column(
        ForeignKey("case_center.id", ondelete="CASCADE"),
        index=True, nullable=False, comment="所属案件卡片",
    )
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True, nullable=True, comment="记录人",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="备注内容")

    case = relationship("CaseCenter", back_populates="notes")


__all__ = [
    "CaseCenter",
    "CaseAnalysis",
    "CaseEvidence",
    "CaseDocument",
    "CaseTask",
    "CaseTimeline",
    "CaseNote",
]
