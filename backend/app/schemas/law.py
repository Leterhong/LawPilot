"""法律搜索引擎相关请求/响应模型。

与既有 ``schemas/legal.py``（RAG 检索）解耦：本模块面向最终用户的
「法律搜索引擎」，聚焦法条层级、高亮、详情关联与推荐。
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LawOut(BaseModel):
    """法条基础输出（对应 law 表）。"""

    id: UUID
    law_name: str
    chapter: str | None = None
    section: str | None = None
    article: str | None = None
    content: str
    keywords: list[str] | None = None
    effective_date: str | None = None
    status: str
    source: str | None = None

    model_config = {"from_attributes": True}


class LawSearchItem(LawOut):
    """搜索结果单元：在 LawOut 基础上追加高亮摘要与得分。"""

    snippet: str | None = Field(None, description="正文高亮摘要（含 <mark> 标签）")
    score: float | None = Field(None, description="相关度得分（第四步 Hybrid 后填充）")
    highlight: dict[str, str] | None = Field(
        None, description="各字段高亮片段，前端可直接渲染"
    )


class LawSearchResult(BaseModel):
    """搜索聚合结果。"""

    query: str
    total: int = 0
    items: list[LawSearchItem] = Field(default_factory=list)
    parsed: dict | None = Field(
        None, description="查询解析结果（识别出的法律名 / 条款号 / 关键词）"
    )


class LawDetail(LawOut):
    """法条详情：完整正文 + 关联信息。"""

    ai_explanation: str | None = Field(
        None, description="AI 通俗解释（第四步生成，先留空）"
    )
    prev: LawOut | None = Field(None, description="上一条")
    next: LawOut | None = Field(None, description="下一条")
    related_laws: list[LawOut] = Field(default_factory=list, description="相关法条")
    related_interpretations: list[dict] = Field(
        default_factory=list, description="相关司法解释"
    )
    related_cases: list[dict] = Field(default_factory=list, description="相关案例引用")
    recommendations: list[LawOut] = Field(
        default_factory=list, description="相关推荐"
    )


class LawHistoryOut(BaseModel):
    """搜索历史输出。"""

    id: UUID
    user_id: UUID | None = None
    query: str
    result_count: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
