"""法律搜索引擎数据模型（law 表）— Law Search 模块核心。

与 legal_reference（案件分析用的 RAG 检索库）解耦：
- legal_reference 服务于「AI 案件分析」的向量检索；
- law 表服务于面向最终用户的「法律搜索引擎」，强调法条层级
  （法律 / 章 / 节 / 条）、BM25 全文检索、pgvector 语义检索与混合排序。

检索能力由三层支撑：
1. ``search_vector``：PostgreSQL ``tsvector`` 生成列（STORED），配合 GIN
   索引实现 BM25 词法检索；
2. ``embedding``：pgvector 语义向量，支持向量近邻检索；
3. 上层 LawSearchService 将两者做 Hybrid Search + Reranker 融合（第四步实现）。

本模型不依赖任何已有业务表，新增模块完全独立。
"""
from __future__ import annotations

import enum

from sqlalchemy import (
    JSON,
    Computed,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.models.base import Base, TimestampMixin, UUIDMixin
from pgvector.sqlalchemy import Vector


class LawStatusEnum(str, enum.Enum):
    """法条现状状态。"""

    EFFECTIVE = "effective"  # 现行有效
    AMENDED = "amended"      # 已被修改（部分条文调整）
    REPEALED = "repealed"    # 已废止
    PENDING = "pending"      # 尚未施行


class Law(UUIDMixin, TimestampMixin, Base):
    """单条法律条文（可被搜索、展示、推荐的最小单元）。"""

    __tablename__ = "law"

    law_name: Mapped[str] = mapped_column(
        String(300),
        index=True,
        nullable=False,
        comment="法律名称，如「中华人民共和国民法典」",
    )
    chapter: Mapped[str | None] = mapped_column(
        String(200),
        index=True,
        nullable=True,
        comment="章，如「第二编 物权」",
    )
    section: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="节，如「第十章 一般规定」",
    )
    article: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
        nullable=True,
        comment="条款编号，如「第577条」",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="法条正文",
    )
    keywords: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="关键词标签数组（用于精确过滤、分类与高亮）",
    )
    effective_date: Mapped[str | None] = mapped_column(
        String(32),
        index=True,
        nullable=True,
        comment="生效日期，格式 YYYY-MM-DD",
    )
    status: Mapped[LawStatusEnum] = mapped_column(
        String(32),
        index=True,
        nullable=False,
        default=LawStatusEnum.EFFECTIVE,
        comment="现状：现行有效 / 已修改 / 已废止 / 尚未施行",
    )
    source: Mapped[str | None] = mapped_column(
        String(300),
        index=True,
        nullable=True,
        comment="来源（发布机关 / 出处，如「全国人民代表大会常务委员会」）",
    )
    # 语义向量（与 legal_reference 同维度，便于统一检索）
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dim),
        nullable=True,
        comment="法条语义向量",
    )
    # BM25 全文检索向量（STORED 生成列，配合下方 GIN 索引）
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            text(
                "to_tsvector('simple', "
                "coalesce(law_name,'') || ' ' || coalesce(chapter,'') || ' ' || "
                "coalesce(section,'') || ' ' || coalesce(article,'') || ' ' || "
                "coalesce(content,'') || ' ' || coalesce(source,''))"
            ),
            persisted=True,
        ),
        nullable=True,
        comment="全文检索向量（BM25 词法检索）",
    )

    __table_args__ = (
        # GIN 索引加速全文检索（@@ 匹配 / ts_rank 排序）
        Index("ix_law_search_vector", search_vector, postgresql_using="gin"),
        # 法律名 + 条款号唯一性，避免同一法条重复入库
        Index(
            "uq_law_name_article",
            "law_name",
            "article",
            unique=True,
            postgresql_where=text("article IS NOT NULL"),
        ),
    )
