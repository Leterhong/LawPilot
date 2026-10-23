"""法律条文模型（legal_reference 表）— RAG 检索核心。

存放结构化的法律条文（法律/司法解释/行政法规/地方性法规/指导案例/典型案例/
办事指南/政策）。embedding 为 BGE-M3 向量，用于语义检索；配合关键词检索
实现混合检索（Hybrid Search）。原文与解释分离，避免编造。
"""
from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import LegalSourceEnum


class LegalReference(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "legal_reference"

    source: Mapped[LegalSourceEnum] = mapped_column(
        String(32), index=True, nullable=False, comment="法律渊源类型"
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False, comment="法规/案例名称")
    article: Mapped[str | None] = mapped_column(
        String(100), index=True, nullable=True, comment="条款号（如 第577条）"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="条文原文")
    explanation: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="条文解释（AI 或官方释义）"
    )
    jurisdiction: Mapped[str | None] = mapped_column(
        String(100), index=True, nullable=True, comment="适用地域（地方性法规用）"
    )
    effective_date: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="生效日期"
    )
    # 额外结构化信息（发布机关、文号等）
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="扩展元数据")
    # BGE-M3 向量（维度来自配置）
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dim), nullable=True, comment="条文语义向量"
    )
