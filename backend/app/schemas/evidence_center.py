"""智能证据中心（Evidence Intelligence Center）Pydantic 模型。

Step2：上传相关模型；Step3：OCR & AI 分析模型；Step4：证据链（关系 / 时间线 /
图谱）；Step5：报告生成（目录 / 评分 / 缺失分析 / 策略 / 综合）。
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import (
    EvidenceFileCategoryEnum,
    EvidenceFileStatusEnum,
    EvidenceRelationTypeEnum,
    EvidenceReportTypeEnum,
)


class EvidenceFileOut(BaseModel):
    """证据文件响应（含 AI 解析字段，未分析时为 None）。"""

    id: UUID
    case_id: UUID | None = None
    user_id: UUID | None = None
    name: str
    category: EvidenceFileCategoryEnum
    status: EvidenceFileStatusEnum
    file_url: str | None = None
    file_type: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    ocr_text: str | None = None
    meta: dict | None = None
    formed_at: datetime | None = None
    source: str | None = None
    tags: list | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class EvidenceUploadItem(BaseModel):
    """单文件上传结果（批量上传时逐条返回）。"""

    file: EvidenceFileOut
    stored: bool
    note: str | None = None


class EvidenceUploadResponse(BaseModel):
    """批量上传响应汇总。"""

    items: list[EvidenceUploadItem]
    total: int
    succeeded: int


# ---------------------------------------------------------------------------
# Step3：OCR & AI 分析
# ---------------------------------------------------------------------------
class EvidenceAnalysisOut(BaseModel):
    """AI 证据分析结果响应。"""

    id: UUID
    evidence_id: UUID
    summary: str | None = None
    proof_point: str | None = None
    proof_strength: int | None = None
    risk: str | None = None
    suggestion: str | None = None
    dimensions: dict | None = None
    model_used: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class EvidenceAnalyzeRequest(BaseModel):
    """批量分析请求。"""

    evidence_ids: list[UUID]
    force_reparse: bool = False


class EvidenceAnalyzeItem(BaseModel):
    """单条证据分析结果（批量分析时逐条返回）。"""

    evidence_id: UUID
    ok: bool
    ai_available: bool = False
    ocr_kind: str | None = None
    text_len: int = 0
    proof_strength: int | None = None
    status: str | None = None
    latency_ms: int = 0
    note: str | None = None


class EvidenceAnalyzeResponse(BaseModel):
    """批量分析响应汇总。"""

    items: list[EvidenceAnalyzeItem]
    total: int
    succeeded: int


class EvidenceDetailOut(EvidenceFileOut):
    """证据详情（附带分析结果，未分析时 analysis 为 None）。"""

    analysis: EvidenceAnalysisOut | None = None


# ---------------------------------------------------------------------------
# Step4：证据链（关系 / 时间线 / 图谱）
# ---------------------------------------------------------------------------
class EvidenceRelationCreate(BaseModel):
    """手动建立证据关系请求。"""

    source_id: UUID
    target_id: UUID
    relation_type: EvidenceRelationTypeEnum
    note: str | None = None


class EvidenceRelationOut(BaseModel):
    """证据关系响应（图谱边）。"""

    id: UUID
    source_id: UUID
    target_id: UUID
    relation_type: EvidenceRelationTypeEnum
    note: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class EvidenceChainBuildRequest(BaseModel):
    """构建证据链请求：AI 推断关系 +（有案件时）重建时间线。"""

    case_id: UUID | None = None
    evidence_ids: list[UUID] | None = None
    infer_relations: bool = True
    build_timeline: bool = True


class EvidenceChainBuildResponse(BaseModel):
    """构建证据链结果汇总。"""

    evidence_count: int
    relations_created: int
    timeline_nodes: int
    ai_available: bool = False
    note: str | None = None


class EvidenceTimelineNodeOut(BaseModel):
    """时间线节点响应。"""

    id: UUID
    case_id: UUID | None = None
    event: str
    event_time: datetime | None = None
    description: str | None = None
    order_index: int = 0
    evidence_ids: list | None = None

    model_config = {"from_attributes": True}


class EvidenceGraphNode(BaseModel):
    """图谱节点：证据 + 关键分析信息（前端渲染用）。"""

    id: UUID
    name: str
    category: EvidenceFileCategoryEnum
    status: EvidenceFileStatusEnum
    event_time: datetime | None = None
    proof_strength: int | None = None
    proof_point: str | None = None
    summary: str | None = None


class EvidenceGraphOut(BaseModel):
    """Evidence Graph：节点 + 边 + 时间线。"""

    nodes: list[EvidenceGraphNode]
    edges: list[EvidenceRelationOut]
    timeline: list[EvidenceTimelineNodeOut]


# ---------------------------------------------------------------------------
# Step5：报告生成
# ---------------------------------------------------------------------------
class EvidenceReportGenerateRequest(BaseModel):
    """生成报告请求：可指定案件（case_id）或显式证据集合（evidence_ids）。"""

    case_id: UUID | None = None
    evidence_ids: list[UUID] | None = None
    report_type: EvidenceReportTypeEnum = EvidenceReportTypeEnum.DIRECTORY
    regenerate: bool = False


class EvidenceReportOut(BaseModel):
    """证据报告响应。

    ``content`` 为结构化 JSON，含 ``markdown``（报告正文）与 ``blocks``（导出渲染用）。
    """

    id: UUID
    case_id: UUID | None = None
    title: str
    report_type: EvidenceReportTypeEnum
    content: dict | None = None
    format: str | None = None
    file_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
