"""案件中心请求/响应模型（Pydantic）。

覆盖：案件卡片 CRUD、AI 分析、证据、文书、任务、时间线、备注。
所有出参均支持 ``from_attributes``，由 ORM 实例直接填充。
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    CaseCenterStatusEnum,
    CaseTypeEnum,
    DocStatusEnum,
    DocTypeEnum,
    EvidenceCategoryEnum,
    PriorityEnum,
    TaskStatusEnum,
)


# ---------------------------
# 案件卡片
# ---------------------------
class CaseCenterCreate(BaseModel):
    """创建案件卡片。"""

    title: str = Field(..., max_length=200, description="案件名称")
    case_type: CaseTypeEnum = Field(..., description="案件类型")
    description: str | None = Field(None, description="案件初始描述")
    status: CaseCenterStatusEnum | None = Field(None, description="案件状态（缺省待处理）")
    priority: PriorityEnum | None = Field(None, description="优先级（缺省中）")
    owner: str | None = Field(None, description="负责人展示名")
    tags: list[str] | None = Field(None, description="标签列表")
    color: str | None = Field(None, description="颜色标签")
    cover_url: str | None = Field(None, description="封面图地址")
    position: int | None = Field(None, description="排序序号")


class CaseCenterUpdate(BaseModel):
    """更新案件卡片（全可选，部分更新）。"""

    title: str | None = Field(None, max_length=200)
    case_type: CaseTypeEnum | None = None
    status: CaseCenterStatusEnum | None = None
    priority: PriorityEnum | None = None
    owner: str | None = None
    starred: bool | None = None
    favorite: bool | None = None
    tags: list[str] | None = None
    color: str | None = None
    cover_url: str | None = None
    position: int | None = None
    description: str | None = None


class CaseCenterOut(BaseModel):
    """案件卡片输出。"""

    id: UUID
    user_id: UUID
    title: str
    case_type: CaseTypeEnum
    status: CaseCenterStatusEnum
    priority: PriorityEnum
    owner: str | None
    starred: bool
    favorite: bool
    tags: list[str] | None
    color: str | None
    cover_url: str | None
    position: int
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------
# AI 分析
# ---------------------------
class CaseAnalysisCreate(BaseModel):
    """提交/触发的分析输入。"""

    analysis_type: str = Field("initial", description="分析类型 initial/deep")
    # 若前端已生成分析结果，可直接提交；否则留空由后端 AI 生成（Step 4）
    summary: str | None = None
    risk: str | None = None
    risk_level: str | None = None
    suggested_status: CaseCenterStatusEnum | None = None
    next_steps: list[str] | None = None
    raw: dict | None = None


class CaseAnalysisOut(BaseModel):
    """分析输出。"""

    id: UUID
    case_id: UUID
    user_id: UUID | None
    analysis_type: str
    summary: str | None
    risk: str | None
    risk_level: str | None
    suggested_status: CaseCenterStatusEnum | None
    next_steps: list[str] | None
    raw: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------
# 证据
# ---------------------------
class CaseEvidenceCreate(BaseModel):
    """新增证据。"""

    category: EvidenceCategoryEnum = Field(..., description="证据类别")
    title: str = Field(..., max_length=200)
    description: str | None = None
    file_path: str | None = None
    file_type: str | None = None
    ocr_text: str | None = None
    is_uploaded: bool = False
    ai_note: str | None = None


class CaseEvidenceUpdate(BaseModel):
    """更新证据（部分）。"""

    category: EvidenceCategoryEnum | None = None
    title: str | None = None
    description: str | None = None
    file_path: str | None = None
    file_type: str | None = None
    ocr_text: str | None = None
    is_uploaded: bool | None = None
    ai_note: str | None = None


class CaseEvidenceOut(BaseModel):
    """证据输出。"""

    id: UUID
    case_id: UUID
    user_id: UUID | None
    category: EvidenceCategoryEnum
    title: str
    description: str | None
    file_path: str | None
    file_type: str | None
    ocr_text: str | None
    is_uploaded: bool
    ai_note: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------
# 文书
# ---------------------------
class CaseDocumentCreate(BaseModel):
    """新增文书。"""

    doc_type: DocTypeEnum = Field(..., description="文书类型")
    title: str = Field(..., max_length=200)
    content: str = Field(..., description="正文（Markdown）")
    status: DocStatusEnum | None = None
    file_path: str | None = None


class CaseDocumentUpdate(BaseModel):
    """更新文书（部分）。"""

    doc_type: DocTypeEnum | None = None
    title: str | None = None
    content: str | None = None
    status: DocStatusEnum | None = None
    file_path: str | None = None


class CaseDocumentOut(BaseModel):
    """文书输出。"""

    id: UUID
    case_id: UUID
    user_id: UUID | None
    doc_type: DocTypeEnum
    title: str
    content: str
    status: DocStatusEnum
    file_path: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------
# 任务
# ---------------------------
class CaseTaskCreate(BaseModel):
    """新增任务。"""

    title: str = Field(..., max_length=200)
    description: str | None = None
    due_date: datetime | None = None
    status: TaskStatusEnum | None = None
    priority: PriorityEnum | None = None
    position: int | None = None


class CaseTaskUpdate(BaseModel):
    """更新任务（部分）。"""

    title: str | None = None
    description: str | None = None
    due_date: datetime | None = None
    status: TaskStatusEnum | None = None
    priority: PriorityEnum | None = None
    position: int | None = None


class CaseTaskOut(BaseModel):
    """任务输出。"""

    id: UUID
    case_id: UUID
    user_id: UUID | None
    title: str
    description: str | None
    due_date: datetime | None
    status: TaskStatusEnum
    priority: PriorityEnum
    position: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------
# 时间线
# ---------------------------
class CaseTimelineCreate(BaseModel):
    """新增时间线事件。"""

    event_type: str = Field(..., max_length=32, description="事件类型")
    title: str = Field(..., max_length=200)
    detail: str | None = None
    occurred_at: datetime | None = Field(None, description="事件发生时间（缺省当前）")


class CaseTimelineUpdate(BaseModel):
    """更新时间线事件（部分）。"""

    event_type: str | None = None
    title: str | None = None
    detail: str | None = None
    occurred_at: datetime | None = None


class CaseTimelineOut(BaseModel):
    """时间线输出。"""

    id: UUID
    case_id: UUID
    user_id: UUID | None
    event_type: str
    title: str
    detail: str | None
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------
# 备注
# ---------------------------
class CaseNoteCreate(BaseModel):
    """新增备注。"""

    content: str = Field(..., description="备注内容")


class CaseNoteUpdate(BaseModel):
    """更新备注。"""

    content: str | None = None


class CaseNoteOut(BaseModel):
    """备注输出。"""

    id: UUID
    case_id: UUID
    user_id: UUID | None
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------
# 详情聚合
# ---------------------------
class CaseCenterDetailOut(BaseModel):
    """案件详情（含全部子资源）。"""

    case: CaseCenterOut
    analyses: list[CaseAnalysisOut]
    evidences: list[CaseEvidenceOut]
    documents: list[CaseDocumentOut]
    tasks: list[CaseTaskOut]
    timelines: list[CaseTimelineOut]
    notes: list[CaseNoteOut]

