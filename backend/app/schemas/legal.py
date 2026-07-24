"""法律检索相关请求/响应模型。

在 Phase 3 关键词检索契约（LegalReferenceOut / KnowledgeOut）基础上，
Phase 5（RAG）新增：
- :class:`RetrievedChunkOut`：混合检索融合后的统一结果（含得分与引用标签）
- :class:`LegalSearchResult` 增加 ``results`` 字段与 ``used_hybrid`` /
  ``used_rerank`` 标记，向后兼容保留原 references / knowledge 列表。
"""
from __future__ import annotations

from uuid import UUID
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import LegalSourceEnum


class LegalSearchQuery(BaseModel):
    """法律检索请求。"""

    q: str = Field(..., min_length=1, description="检索关键词")
    source: LegalSourceEnum | None = Field(None, description="限定法律渊源类型")
    limit: int = Field(10, ge=1, le=50)
    offset: int = Field(0, ge=0)
    use_rerank: bool = Field(True, description="是否进行重排精排")


class LegalReferenceOut(BaseModel):
    """法律条文输出。"""

    id: UUID
    source: LegalSourceEnum
    title: str
    article: str | None
    content: str
    explanation: str | None
    jurisdiction: str | None
    effective_date: str | None
    extra: dict | None

    model_config = {"from_attributes": True}


class KnowledgeOut(BaseModel):
    """知识条目输出。"""

    id: UUID
    category: LegalSourceEnum
    title: str
    content: str
    source_url: str | None
    tags: list[str] | None

    model_config = {"from_attributes": True}


class RetrievedChunkOut(BaseModel):
    """混合检索融合后的统一结果单元。"""

    id: UUID
    source_table: str = Field(..., description="来源表：legal_reference | knowledge")
    source: LegalSourceEnum
    title: str
    article: str | None
    content: str
    snippet: str = Field(..., description="正文摘要")
    score: float = Field(..., description="最终排序得分")
    vector_score: float | None = Field(None, description="向量相似度（1-距离）")
    keyword_score: float | None = Field(None, description="关键词命中标记")
    citation: str = Field(..., description="面向用户的可读引用标签")


class LegalSearchResult(BaseModel):
    """法律检索聚合结果。"""

    query: str
    results: list[RetrievedChunkOut] = Field(default_factory=list, description="融合排序后的结果")
    citations: list[dict] = Field(default_factory=list, description="引用来源元数据（供报告生成）")
    references: list[LegalReferenceOut] = Field(default_factory=list, description="原始条文列表（兼容）")
    references_total: int = 0
    knowledge: list[KnowledgeOut] = Field(default_factory=list, description="原始知识列表（兼容）")
    knowledge_total: int = 0
    used_hybrid: bool = Field(True, description="是否启用向量检索")
    used_rerank: bool = Field(False, description="是否启用重排")
