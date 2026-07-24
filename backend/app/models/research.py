"""Legal Research Center 数据模型（法律研究中心模块）。

需求给出 6 张物理表：legal_documents / judicial_interpretations / department_rules /
local_regulations / guidelines / policies。但 UI 资源分类有 9 类（法律 / 行政法规 /
司法解释 / 指导性案例 / 典型案例 / 部门规章 / 地方性法规 / 办事指南 / 政策文件）。

映射策略（不新增表，尊重 6 表需求）：
- ``legal_documents`` 用 ``category`` 细分覆盖 4 类：法律 / 行政法规 / 指导性案例 / 典型案例
- 其余 5 张表各自覆盖 1 类：司法解释 / 部门规章 / 地方性法规 / 办事指南 / 政策文件

检索能力（与 legal_cases / laws 一致，沿用 PG 原生，本环境无 ElasticSearch）：
1. ``search_vector``：``tsvector``(STORED) + GIN —— BM25 词法检索（实际命中走 bigram
   ILIKE，见 research_repo，保证中文召回）；该列保留以便未来对接 ES / pg_search。
2. ``embedding``：pgvector 语义向量（BGE-M3，维度与 Law/legal_cases 一致）。
3. 上层 ResearchService 做 Hybrid(RRF) + Reranker 融合。

AI 字段（summary_one_line / core_points / scope / common_misconceptions /
ai_explanation / ai_summary）默认 NULL，由 ResearchService 在详情/批量时惰性生成
（无 LLM key 时优雅降级为 None），纯只读、不改动表结构。
"""
from __future__ import annotations

import enum
import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    Computed,
    Date,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.models.base import Base, TimestampMixin, UUIDMixin
from pgvector.sqlalchemy import Vector


class ResearchDocType(str, enum.Enum):
    """6 张物理表各自对应的 doc_type（资源大类）。"""

    LEGAL_DOCUMENT = "legal_document"
    JUDICIAL_INTERPRETATION = "judicial_interpretation"
    DEPARTMENT_RULE = "department_rule"
    LOCAL_REGULATION = "local_regulation"
    GUIDELINE = "guideline"
    POLICY = "policy"


# 9 个 UI 分类 → 展示标签（与前端 constants 对齐）
RESEARCH_CATEGORY_LABELS: dict[str, str] = {
    "法律": "法律",
    "行政法规": "行政法规",
    "司法解释": "司法解释",
    "指导性案例": "指导性案例",
    "典型案例": "典型案例",
    "部门规章": "部门规章",
    "地方性法规": "地方性法规",
    "办事指南": "办事指南",
    "政策文件": "政策文件",
}

# 法律层级取值（高级检索过滤用）
LEGAL_LEVEL_LABELS: dict[str, str] = {
    "法律": "法律",
    "行政法规": "行政法规",
    "司法解释": "司法解释",
    "部门规章": "部门规章",
    "地方性法规": "地方性法规",
    "指导性案例": "指导性案例",
    "典型案例": "典型案例",
    "办事指南": "办事指南",
    "政策文件": "政策文件",
}


def _research_table_args(tablename: str) -> tuple:
    """为某张研究表生成统一的 GIN 索引（全文检索 + 关键词 JSONB）。

    其余列（title / doc_number / category / 日期 / is_current / source / level /
    region / issuing_authority）已在列定义上用 ``index=True`` 建索引，避免重复。
    """
    return (
        Index(f"ix_{tablename}_search_vector", "search_vector", postgresql_using="gin"),
        Index(f"ix_{tablename}_keywords", "keywords", postgresql_using="gin"),
    )


class ResearchDocMixin:
    """六张表共享的列定义（不作为独立表，仅作混入）。"""

    title: Mapped[str] = mapped_column(
        String(400), index=True, nullable=False, comment="标题"
    )
    doc_number: Mapped[str | None] = mapped_column(
        String(120), index=True, nullable=True, comment="发文字号，如 法释〔2023〕1号"
    )
    category: Mapped[str] = mapped_column(
        String(40), index=True, nullable=False, comment="UI 分类（9 类之一）"
    )
    full_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="全文"
    )
    summary_one_line: Mapped[str | None] = mapped_column(
        String(300), nullable=True, comment="一句话总结（AI）"
    )
    core_points: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True, comment="核心观点（AI）"
    )
    scope: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="适用范围（AI）"
    )
    common_misconceptions: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True, comment="常见误区（AI）"
    )
    publish_date: Mapped[date | None] = mapped_column(
        Date, index=True, nullable=True, comment="发布时间"
    )
    effective_date: Mapped[date | None] = mapped_column(
        Date, index=True, nullable=True, comment="实施时间"
    )
    expiry_date: Mapped[date | None] = mapped_column(
        Date, index=True, nullable=True, comment="失效时间（未失效为 NULL）"
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, index=True, default=True, nullable=False, comment="是否现行有效"
    )
    source: Mapped[str | None] = mapped_column(
        String(300), index=True, nullable=True, comment="来源，如 中国政府网 / 最高人民法院"
    )
    level: Mapped[str | None] = mapped_column(
        String(40), index=True, nullable=True, comment="法律层级"
    )
    region: Mapped[str | None] = mapped_column(
        String(80), index=True, nullable=True, comment="地区（地方规定 / 部门规则适用）"
    )
    issuing_authority: Mapped[str | None] = mapped_column(
        String(200), index=True, nullable=True, comment="发文机关"
    )
    keywords: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True, comment="关键词标签数组"
    )
    related_law_ids: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True, comment="关联法条引用数组"
    )
    related_case_ids: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True, comment="关联案例引用数组"
    )
    related_interpretation_ids: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True, comment="关联司法解释引用数组"
    )
    ai_explanation: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="AI 通俗解释"
    )
    ai_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="AI 总结"
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dim),
        nullable=True,
        comment="语义向量（BGE-M3）",
    )
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            text(
                "to_tsvector('simple', "
                "coalesce(title,'') || ' ' || coalesce(doc_number,'') || ' ' || "
                "coalesce(full_text,'') || ' ' || coalesce(source,'') || ' ' || "
                "coalesce(issuing_authority,'')"
            ),
            persisted=True,
        ),
        nullable=True,
        comment="全文检索向量（BM25 词法检索）",
    )


class LegalDocument(UUIDMixin, TimestampMixin, ResearchDocMixin, Base):
    """法律法规文档（覆盖：法律 / 行政法规 / 指导性案例 / 典型案例）。"""

    __tablename__ = "legal_documents"
    __table_args__ = _research_table_args(__tablename__)

    doc_type: str = ResearchDocType.LEGAL_DOCUMENT.value


class JudicialInterpretation(UUIDMixin, TimestampMixin, ResearchDocMixin, Base):
    """司法解释。"""

    __tablename__ = "judicial_interpretations"
    __table_args__ = _research_table_args(__tablename__)

    doc_type: str = ResearchDocType.JUDICIAL_INTERPRETATION.value


class DepartmentRule(UUIDMixin, TimestampMixin, ResearchDocMixin, Base):
    """部门规章。"""

    __tablename__ = "department_rules"
    __table_args__ = _research_table_args(__tablename__)

    doc_type: str = ResearchDocType.DEPARTMENT_RULE.value


class LocalRegulation(UUIDMixin, TimestampMixin, ResearchDocMixin, Base):
    """地方性法规（地方规定）。"""

    __tablename__ = "local_regulations"
    __table_args__ = _research_table_args(__tablename__)

    doc_type: str = ResearchDocType.LOCAL_REGULATION.value


class Guideline(UUIDMixin, TimestampMixin, ResearchDocMixin, Base):
    """办事指南。"""

    __tablename__ = "guidelines"
    __table_args__ = _research_table_args(__tablename__)

    doc_type: str = ResearchDocType.GUIDELINE.value


class Policy(UUIDMixin, TimestampMixin, ResearchDocMixin, Base):
    """政策文件。"""

    __tablename__ = "policies"
    __table_args__ = _research_table_args(__tablename__)

    doc_type: str = ResearchDocType.POLICY.value


# 供 repository 遍历：(模型类, doc_type, 分类标签)
RESEARCH_TABLES = [
    (LegalDocument, ResearchDocType.LEGAL_DOCUMENT.value, "法律"),
    (JudicialInterpretation, ResearchDocType.JUDICIAL_INTERPRETATION.value, "司法解释"),
    (DepartmentRule, ResearchDocType.DEPARTMENT_RULE.value, "部门规章"),
    (LocalRegulation, ResearchDocType.LOCAL_REGULATION.value, "地方性法规"),
    (Guideline, ResearchDocType.GUIDELINE.value, "办事指南"),
    (Policy, ResearchDocType.POLICY.value, "政策文件"),
]
