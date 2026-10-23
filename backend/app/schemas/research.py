"""法律研究中心（Legal Research Center）请求/响应模型。

与 legal_cases / law 的 schemas 解耦：本模块面向「法规 / 司法解释 / 部门规章 /
地方性法规 / 办事指南 / 政策文件」等研究型文档，聚焦全文、时效、层级、地区、
发文机关、关联文档与 AI 解读。
"""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

# 6 张表对应的文档类型标识（与 models/research.RESEARCH_TABLES 保持一致）
RESEARCH_DOC_TYPES = [
    "legal_document",
    "judicial_interpretation",
    "department_rule",
    "local_regulation",
    "guideline",
    "policy",
]

# UI 九大类 -> 文档类型映射（legal_documents 表用 category 列承载前 4 类）
CATEGORY_LABELS = {
    "法律": "法律",
    "行政法规": "行政法规",
    "指导性案例": "指导性案例",
    "典型案例": "典型案例",
    "司法解释": "司法解释",
    "部门规章": "部门规章",
    "地方性法规": "地方性法规",
    "办事指南": "办事指南",
    "政策文件": "政策文件",
}

DOC_TYPE_LABELS = {
    "legal_document": "法律法规",
    "judicial_interpretation": "司法解释",
    "department_rule": "部门规章",
    "local_regulation": "地方性法规",
    "guideline": "办事指南",
    "policy": "政策文件",
}


def _cat_label(cat: Optional[str]) -> Optional[str]:
    return CATEGORY_LABELS.get(cat, cat) if cat else None


def _doc_type_label(dt: Optional[str]) -> Optional[str]:
    return DOC_TYPE_LABELS.get(dt, dt) if dt else None


class ResearchDocOut(BaseModel):
    """研究文档基础输出（对应 6 张表的公共字段 + doc_type 标识）。"""

    id: UUID
    doc_type: str = Field(..., description="文档类型：对应 6 张表之一")
    title: str
    doc_number: str | None = None
    category: str = Field(..., description="UI 分类（9 类之一）")
    summary_one_line: str | None = None
    core_points: list[str] | None = None
    scope: str | None = None
    common_misconceptions: list[str] | None = None
    publish_date: date | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    is_current: bool = True
    source: str | None = None
    level: str | None = None
    region: str | None = None
    issuing_authority: str | None = None
    keywords: list[str] | None = None
    related_law_ids: list[str] | None = None
    related_case_ids: list[str] | None = None
    related_interpretation_ids: list[str] | None = None

    model_config = {"from_attributes": True}


class ResearchSearchItem(ResearchDocOut):
    """搜索结果单元：在基础输出上追加摘要、得分、高亮与分类标签。"""

    snippet: str | None = Field(None, description="正文高亮摘要（含 <mark> 标签）")
    score: float | None = Field(None, description="相关度得分（重排后填充）")
    highlight: dict[str, str] | None = Field(None, description="各字段高亮片段")
    category_label: str | None = None
    doc_type_label: str | None = None


class ResearchSearchResult(BaseModel):
    """搜索聚合结果。"""

    query: str
    total: int = 0
    items: list[ResearchSearchItem] = Field(default_factory=list)
    parsed: dict | None = Field(None, description="查询解析结果（识别出的关键词/模式等）")
    filters: dict | None = Field(None, description="实际生效的过滤条件回显")
    facets: dict | None = Field(None, description="分类计数（按 UI 分类聚合）")


class RelatedDocRef(BaseModel):
    """关联文档引用（轻量，可链到 /api/research/document/{id}）。"""

    id: UUID
    doc_type: str
    title: str
    category: str
    summary_one_line: str | None = None


class ResearchDocDetail(ResearchDocOut):
    """文档详情：全文 + 关联文档 + AI 通俗解释 / 摘要。"""

    full_text: str | None = None
    related_docs: list[RelatedDocRef] = Field(default_factory=list)
    ai_explanation: str | None = Field(None, description="AI 通俗解释（懒生成 + 缓存）")
    ai_summary: str | None = Field(None, description="AI 摘要（懒生成 + 缓存）")
    category_label: str | None = None
    doc_type_label: str | None = None


class ResearchRecommendResult(BaseModel):
    """相关推荐结果。"""

    query: str = ""
    seed_id: UUID | None = None
    total: int = 0
    items: list[ResearchSearchItem] = Field(default_factory=list)


class ResearchFacetItem(BaseModel):
    """过滤面选项（值 + 中文标签）。"""

    value: str
    label: str
