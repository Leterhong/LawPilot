"""知识库模型（knowledge 表）— 非结构化/半结构化知识。

与 legal_reference（强结构化条文）互补，存放办事指南、政策解读、流程说明、
常见问答等可检索知识。embedding 用于语义检索，tags 支持关键词过滤。
"""
from __future__ import annotations

from sqlalchemy import (
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import LegalSourceEnum
from pgvector.sqlalchemy import Vector


class Knowledge(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "knowledge"

    category: Mapped[LegalSourceEnum] = mapped_column(
        String(32), index=True, nullable=False, comment="知识类别"
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False, comment="标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="正文内容")
    source_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="来源链接"
    )
    tags: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True, comment="标签列表（关键词过滤）"
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dim), nullable=True, comment="知识语义向量"
    )

    __table_args__ = (
        # 为 tags 内联 GIN 索引，支持 JSON 数组包含查询
    )
