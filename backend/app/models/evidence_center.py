"""Evidence Intelligence Center（智能证据中心）数据库模型。

本模块为独立的「证据中心」提供持久化支撑，与既有 cases / evidence（案件中心）
解耦：
- 既有 ``evidence`` 表服务 Case Center 的「待补证据」清单；
- 本模块 ``evidence_files`` 等表服务独立的「智能证据中心」
  （上传 / 解析 / 分析 / 证据链 / 报告）。

表清单：
- ``evidence_files``       证据文件（上传载体 + OCR 文本 + 结构化元数据 + 向量）
- ``evidence_analysis``    AI 证据解析（证明事项 / 证明力 / 风险 / 建议 / 五维评分）
- ``evidence_relations``   证据间关系（印证 / 矛盾 / 先后等，Evidence Graph 用）
- ``evidence_timeline``    案件证据链时间线节点（事件 + 关联证据）
- ``evidence_reports``     证据报告（目录 / 评分 / 缺失分析 / 策略，支持导出）

所有表继承 ``UUIDMixin`` + ``TimestampMixin``，复用现有 ``Base`` 与连接池，
不改动任何已有功能与表。
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import (
    EvidenceFileCategoryEnum,
    EvidenceFileStatusEnum,
    EvidenceRelationTypeEnum,
    EvidenceReportTypeEnum,
)


def _native_enum(cls: type[enum.Enum]) -> Enum:
    """生成与项目一致的「非原生枚举」列类型（存储字符串值，兼容既有约定）。"""
    return Enum(
        cls,
        values_callable=lambda e: [x.value for x in e],
        native_enum=False,
    )


class EvidenceFile(UUIDMixin, TimestampMixin, Base):
    """证据文件——智能证据中心的核心实体。

    既承载用户上传的文件（``file_url`` 指向对象存储），也保存 AI 解析产物
    （``ocr_text`` / ``metadata`` 结构化提取 / ``embedding`` 语义向量）。
    """

    __tablename__ = "evidence_files"
    __table_args__ = (
        Index("ix_evidence_files_case_cat", "case_id", "category"),
        Index("ix_evidence_files_user", "user_id"),
    )

    case_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("cases.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
        comment="关联案件（可选）",
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
        comment="上传人",
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="证据名称"
    )
    category: Mapped[EvidenceFileCategoryEnum] = mapped_column(
        _native_enum(EvidenceFileCategoryEnum),
        index=True,
        nullable=False,
        comment="证据类型（AI 自动分类）",
    )
    status: Mapped[EvidenceFileStatusEnum] = mapped_column(
        _native_enum(EvidenceFileStatusEnum),
        default=EvidenceFileStatusEnum.UPLOADED,
        index=True,
        nullable=False,
        comment="处理状态",
    )
    file_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, comment="对象存储路径 / URL"
    )
    file_type: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="扩展名 pdf/docx/png/jpg..."
    )
    mime_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="MIME 类型"
    )
    size_bytes: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="文件大小（字节）"
    )
    ocr_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="OCR 识别文本"
    )
    # 结构化提取结果：时间 / 人物 / 金额 / 地点 / 事件 / 关键内容
    # 注意：metadata 是 Declarative 保留属性名，ORM 属性用 meta，库列名仍为 metadata
    meta: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True, comment="结构化元数据（AI 提取）"
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dim),
        nullable=True,
        comment="语义向量（相似证据检索 / RAG）",
    )
    formed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="证据形成时间"
    )
    source: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="证据来源"
    )
    tags: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="用户标签"
    )

    case = relationship("Case")
    analyses = relationship(
        "EvidenceAnalysis",
        back_populates="evidence",
        cascade="all, delete-orphan",
    )


class EvidenceAnalysis(UUIDMixin, TimestampMixin, Base):
    """AI 证据解析结果。

    每条证据对应一条解析：说明证据证明什么、证明力星级、风险与建议，
    以及五维（完整性 / 真实性 / 关联性 / 合法性 / 证明力）评分，便于生成评分报告。
    """

    __tablename__ = "evidence_analysis"
    __table_args__ = (
        Index("ix_evidence_analysis_evidence", "evidence_id", unique=True),
    )

    evidence_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("evidence_files.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属证据",
    )
    summary: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="AI 摘要 / 理解"
    )
    proof_point: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="证明事项"
    )
    proof_strength: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="证明力（1-5 星）"
    )
    risk: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="风险点"
    )
    suggestion: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="补充 / 改进建议"
    )
    # 五维评分：completeness / authenticity / relevance / legality / proof_strength 各 1-5
    dimensions: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="五维评分"
    )
    model_used: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="AI Routing 选择的模型"
    )
    raw: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="模型原始输出（审计）"
    )

    evidence = relationship("EvidenceFile", back_populates="analyses")


class EvidenceRelation(UUIDMixin, TimestampMixin, Base):
    """证据间关系（用于 Evidence Graph / 证据链）。"""

    __tablename__ = "evidence_relations"
    __table_args__ = (
        Index("ix_evidence_relations_source", "source_id"),
        Index("ix_evidence_relations_target", "target_id"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("evidence_files.id", ondelete="CASCADE"),
        nullable=False,
        comment="源证据",
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("evidence_files.id", ondelete="CASCADE"),
        nullable=False,
        comment="目标证据",
    )
    relation_type: Mapped[EvidenceRelationTypeEnum] = mapped_column(
        _native_enum(EvidenceRelationTypeEnum),
        nullable=False,
        comment="关系类型",
    )
    note: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="关系说明"
    )


class EvidenceTimelineNode(UUIDMixin, TimestampMixin, Base):
    """案件证据链时间线节点（Evidence Graph 的事件序列）。"""

    __tablename__ = "evidence_timeline"
    __table_args__ = (
        Index("ix_evidence_timeline_case", "case_id"),
        Index("ix_evidence_timeline_order", "case_id", "order_index"),
    )

    case_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("cases.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
        comment="关联案件",
    )
    event: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="事件名称（如：签订合同）"
    )
    event_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="事件发生时间"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="事件说明"
    )
    order_index: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="排序"
    )
    # 关联证据 id 列表（JSON 数组）
    evidence_ids: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="关联证据 id 列表"
    )


class EvidenceReport(UUIDMixin, TimestampMixin, Base):
    """证据报告（目录 / 评分 / 缺失分析 / 策略）。"""

    __tablename__ = "evidence_reports"
    __table_args__ = (
        Index("ix_evidence_reports_case", "case_id"),
    )

    case_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("cases.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
        comment="关联案件",
    )
    title: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="报告标题"
    )
    report_type: Mapped[EvidenceReportTypeEnum] = mapped_column(
        _native_enum(EvidenceReportTypeEnum),
        index=True,
        nullable=False,
        comment="报告类型",
    )
    content: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="结构化报告内容"
    )
    format: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="导出格式 word/pdf"
    )
    file_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, comment="导出文件对象存储路径"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="生成人",
    )


__all__ = [
    "EvidenceFile",
    "EvidenceAnalysis",
    "EvidenceRelation",
    "EvidenceTimelineNode",
    "EvidenceReport",
]
