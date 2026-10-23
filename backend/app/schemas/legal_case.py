"""案例搜索相关请求/响应模型（Legal Case Search 模块）。

与 Law Search 的 schemas/law.py 解耦：本模块面向「真实裁判文书」的检索与详情，
聚焦案件层级（标题/法院/案由/当事人/事实/裁判理由/结果）、高亮、相关法律关联与
AI 相似度总结（第四步填充）。
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.law import LawOut


class LegalCaseOut(BaseModel):
    """案例基础输出（对应 legal_cases 表）。"""

    id: UUID
    title: str
    case_number: str | None = None
    court: str | None = None
    province: str | None = None
    city: str | None = None
    trial_date: date | None = None
    case_type: str
    court_level: str | None = None
    cause_of_action: str | None = None
    plaintiff: str | None = None
    defendant: str | None = None
    winner: str | None = None
    compensation: str | None = None
    keywords: list[str] | None = None
    related_laws: list[str] | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


class LegalCaseSearchItem(LegalCaseOut):
    """搜索结果单元：在 LegalCaseOut 基础上追加高亮摘要与得分。"""

    snippet: str | None = Field(None, description="正文高亮摘要（含 <mark> 标签）")
    score: float | None = Field(None, description="相关度得分（Hybrid 后填充）")
    highlight: dict[str, str] | None = Field(
        None, description="各字段高亮片段，前端可直接渲染"
    )


class LegalCaseSearchResult(BaseModel):
    """搜索聚合结果。"""

    query: str
    total: int = 0
    items: list[LegalCaseSearchItem] = Field(default_factory=list)
    parsed: dict | None = Field(
        None, description="查询解析结果（识别出的关键词等）"
    )
    filters: dict | None = Field(None, description="实际生效的过滤条件回显")


class LegalCaseAiSummary(BaseModel):
    """AI 对本案例与用户情形的相似度总结（第四步填充，先留空）。"""

    similar_points: str | None = Field(None, description="相似点")
    different_points: str | None = Field(None, description="不同点")
    reference_value: str | None = Field(None, description="参考价值：高/中/低")
    raw: str | None = Field(None, description="AI 原始完整输出")


class LegalCaseDetail(LegalCaseOut):
    """案例详情：完整事实/裁判理由/结果 + 关联法条 + AI 总结。"""

    facts: str | None = None
    court_reasoning: str | None = None
    judgement: str | None = None
    # 覆盖基类（基类 related_laws 为原始引用字符串数组），此处解析为可链法条
    related_laws: list[LawOut] = Field(
        default_factory=list, description="关联到法律库的真实法条（可链 /laws/{id}）"
    )
    related_law_citations: list[str] | None = Field(
        None, description="案例原始存储的法条引用字符串（如「民法典第577条」）"
    )
    ai_summary: LegalCaseAiSummary | None = Field(
        None, description="AI 相似度总结（第四步生成，先留空）"
    )


class FacetItem(BaseModel):
    """过滤面选项（值 + 中文标签）。"""

    value: str
    label: str


class CaseFilterFacets(BaseModel):
    """/filter 返回的过滤面（供前端构建下拉）。"""

    provinces: list[str] = Field(default_factory=list, description="省份列表")
    cities: list[str] = Field(default_factory=list, description="城市列表")
    court_levels: list[FacetItem] = Field(
        default_factory=list, description="法院级别选项"
    )
    case_types: list[FacetItem] = Field(
        default_factory=list, description="案件类型选项"
    )
    time_ranges: list[FacetItem] = Field(
        default_factory=list, description="时间范围选项"
    )


class SimilarCaseRequest(BaseModel):
    """查找类似案例请求：可传用户案件 id 让后端自动提取关键词，或直接传查询文本。"""

    case_id: UUID | None = Field(
        None, description="用户案件中心中的案件 id（后端自动提取关键词检索）"
    )
    query: str | None = Field(
        None, description="直接传入的查询文本；与 case_id 二选一，case_id 优先"
    )
    limit: int = Field(10, ge=1, le=20, description="返回条数（默认 10）")
