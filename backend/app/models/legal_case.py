"""案例搜索数据模型（legal_cases 表）— Legal Case Search 模块核心。

与 Law Search（law 表）、案件中心（case_center 表）完全独立，新增模块不改动任何
已有业务表。

检索能力由三层支撑（与 law 表一致，保证技术栈统一、可真实运行）：
1. ``search_vector``：PostgreSQL ``tsvector`` 生成列（STORED），配合 GIN 索引
   实现 BM25 词法检索（本环境无 ElasticSearch，沿用 PG 原生全文检索）；
2. ``embedding``：pgvector 语义向量（BGE-M3，维度与 Law/legal_reference 一致），
   支持向量近邻检索；
3. 上层 LegalCaseSearchService 将两者做 Hybrid Search + Reranker 融合（第二步/第四步实现）。

``legal_case_favorites`` 记录用户对案例的收藏（支持前端收藏案例），按
(user_id, case_id) 唯一，删除案例时级联清理。
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    Date,
    Computed,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import CourtLevelEnum, LegalCaseTypeEnum
from pgvector.sqlalchemy import Vector


class LegalCase(UUIDMixin, TimestampMixin, Base):
    """一条可检索的真实案例（裁判文书）。"""

    __tablename__ = "legal_cases"

    title: Mapped[str] = mapped_column(
        String(400),
        index=True,
        nullable=False,
        comment="案件标题",
    )
    case_number: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
        nullable=True,
        comment="案号，如(2023)京0105民初12345号",
    )
    court: Mapped[str | None] = mapped_column(
        String(200),
        index=True,
        nullable=True,
        comment="审理法院全称",
    )
    province: Mapped[str | None] = mapped_column(
        String(50),
        index=True,
        nullable=True,
        comment="省份，用于地区筛选",
    )
    city: Mapped[str | None] = mapped_column(
        String(50),
        index=True,
        nullable=True,
        comment="城市，用于地区筛选",
    )
    trial_date: Mapped[date | None] = mapped_column(
        Date,
        index=True,
        nullable=True,
        comment="审判日期，用于近一年/近五年筛选",
    )
    case_type: Mapped[LegalCaseTypeEnum] = mapped_column(
        String(32),
        index=True,
        nullable=False,
        default=LegalCaseTypeEnum.CIVIL,
        comment="案件类型：民事/劳动/合同/消费/其他",
    )
    court_level: Mapped[CourtLevelEnum | None] = mapped_column(
        String(32),
        index=True,
        nullable=True,
        comment="法院级别：基层/中级/高级/最高",
    )
    cause_of_action: Mapped[str | None] = mapped_column(
        String(200),
        index=True,
        nullable=True,
        comment="案由，如房屋租赁合同纠纷",
    )
    plaintiff: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="原告",
    )
    defendant: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="被告",
    )
    facts: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="案件事实",
    )
    court_reasoning: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="法院观点 / 裁判理由",
    )
    judgement: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="裁判结果",
    )
    winner: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="胜诉方（详情页展示）",
    )
    compensation: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="赔偿金额（详情页展示）",
    )
    keywords: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="关键词标签数组（精确过滤、分类与高亮）",
    )
    related_laws: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="关联法律条文引用数组",
    )
    source: Mapped[str | None] = mapped_column(
        String(300),
        index=True,
        nullable=True,
        comment="来源，如中国裁判文书网",
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dim),
        nullable=True,
        comment="案例语义向量（BGE-M3）",
    )
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            text(
                "to_tsvector('simple', "
                "coalesce(title,'') || ' ' || coalesce(court,'') || ' ' || "
                "coalesce(cause_of_action,'') || ' ' || coalesce(plaintiff,'') || ' ' || "
                "coalesce(defendant,'') || ' ' || coalesce(facts,'') || ' ' || "
                "coalesce(court_reasoning,'') || ' ' || coalesce(judgement,'')"
            ),
            persisted=True,
        ),
        nullable=True,
        comment="全文检索向量（BM25 词法检索）",
    )

    favorites: Mapped[list["LegalCaseFavorite"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_legal_cases_title", "title"),
        Index("ix_legal_cases_case_number", "case_number"),
        Index("ix_legal_cases_court", "court"),
        Index("ix_legal_cases_province", "province"),
        Index("ix_legal_cases_city", "city"),
        Index("ix_legal_cases_trial_date", "trial_date"),
        Index("ix_legal_cases_case_type", "case_type"),
        Index("ix_legal_cases_court_level", "court_level"),
        Index("ix_legal_cases_cause_of_action", "cause_of_action"),
        Index("ix_legal_cases_source", "source"),
        Index(
            "ix_legal_cases_search_vector",
            search_vector,
            postgresql_using="gin",
        ),
        Index("ix_legal_cases_keywords", keywords, postgresql_using="gin"),
    )


class LegalCaseFavorite(UUIDMixin, TimestampMixin, Base):
    """用户对案例的收藏（支持前端收藏案例）。"""

    __tablename__ = "legal_case_favorites"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="收藏用户",
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("legal_cases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="被收藏的案例",
    )

    user: Mapped["User"] = relationship("User", lazy="joined")
    case: Mapped[LegalCase] = relationship(back_populates="favorites")

    __table_args__ = (
        Index("uq_legal_case_favorite", "user_id", "case_id", unique=True),
    )
