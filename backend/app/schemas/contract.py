"""合同智能中心（Contract Intelligence Center）请求/响应 Schema。

Step2 仅涉及上传 / 列表 / 详情；分析相关字段（summary / risk_* 等）在此预先
定义好响应结构，后续步骤填充后自动可见，无需改 Schema。
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContractOut(BaseModel):
    """合同列表 / 上传响应（不含大体积全文）。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None = None
    title: str | None = None
    contract_type: str | None = None
    status: str
    file_type: str | None = None
    file_size: int | None = None
    language: str = "zh"
    page_count: int | None = None
    # 分析摘要（Step3 填充，Step2 为 None）
    summary: str | None = None
    risk_score: int = 0
    risk_level: str = "low"
    analyzed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ContractRiskOut(BaseModel):
    """单条风险（Risk Dashboard 数据源）。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contract_id: UUID
    clause_ref: str | None = None
    clause_text: str | None = None
    category: str
    risk_level: str = "medium"
    score: int = 0
    reason: str | None = None
    suggestion: str | None = None
    suggested_text: str | None = None
    king_clause: bool = False
    created_at: datetime


class ContractClauseOut(BaseModel):
    """单条款（Clause Analyzer 点击对象）。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contract_id: UUID
    clause_no: str | None = None
    section: str | None = None
    clause_text: str | None = None
    category: str | None = None
    order_index: int = 0
    explanation: str | None = None
    risk_level: str | None = None
    risk_note: str | None = None
    suggested_version: str | None = None
    created_at: datetime


class ContractDetailOut(ContractOut):
    """合同详情（含全文、AI 分析明细与子表 risks / clauses）。"""

    full_text: str | None = None
    ocr_text: str | None = None
    law_involved: list[dict] | None = None
    risk_clauses: list[dict] | None = None
    king_clauses: list[dict] | None = None
    payment_risk: dict | None = None
    breach_risk: dict | None = None
    liability_risk: dict | None = None
    analysis_meta: dict | None = None
    token_usage: dict | None = None
    checklist: list[dict] | None = None
    # Step3 子表
    risks: list[ContractRiskOut] = Field(default_factory=list)
    clauses: list[ContractClauseOut] = Field(default_factory=list)


class ContractUploadResponse(BaseModel):
    """上传成功响应：返回合同记录 + 解析元信息。"""

    model_config = ConfigDict(from_attributes=True)

    contract: ContractOut
    parsed: bool = Field(description="是否成功提取到文本/OCR")
    text_length: int = Field(default=0, description="提取文本字符数")
    ocr_used: bool = Field(default=False, description="是否使用了 OCR（图片）")


class ContractReportOut(BaseModel):
    """合同审查报告（Markdown 正文 + 结构化内容）。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contract_id: UUID
    report_type: str
    title: str | None = None
    content: str | None = None
    content_json: dict | None = None
    format: str = "markdown"
    generated_by: UUID | None = None
    model_id: UUID | None = None
    file_path: str | None = None
    created_at: datetime
    updated_at: datetime


class ContractListQuery(BaseModel):
    """列表筛选参数（也可直接走 Query，这里仅作文档/复用）。"""

    contract_type: str | None = None
    status: str | None = None
    page: int = 1
    page_size: int = 20


class ContractTaskOut(BaseModel):
    """合同提醒 / 待办（含关联合同标题，便于提醒中心聚合展示）。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contract_id: UUID
    type: str = "reminder"
    title: str
    category: str | None = None
    due_date: date | None = None
    remind_before_days: int = 7
    done: bool = False
    priority: str = "normal"
    note: str | None = None
    contract_title: str | None = None
    created_at: datetime
    updated_at: datetime


class ContractTaskCreate(BaseModel):
    """创建提醒 / 待办。"""

    type: str = "reminder"
    title: str
    category: str | None = None
    due_date: date | None = None
    remind_before_days: int = 7
    done: bool = False
    priority: str = "normal"
    note: str | None = None


class ContractTaskUpdate(BaseModel):
    """更新提醒 / 待办（部分字段）。"""

    type: str | None = None
    title: str | None = None
    category: str | None = None
    due_date: date | None = None
    remind_before_days: int | None = None
    done: bool | None = None
    priority: str | None = None
    note: str | None = None
