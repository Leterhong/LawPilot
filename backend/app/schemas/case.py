"""案件相关请求/响应模型。"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import CaseStatusEnum, CaseTypeEnum


class CaseCreate(BaseModel):
    """创建案件请求。"""

    title: str = Field(..., max_length=200, description="案件标题")
    case_type: CaseTypeEnum = Field(..., description="案件类型")
    description: str | None = Field(None, description="用户初始遭遇描述")


class CaseUpdate(BaseModel):
    """更新案件请求（全可选，部分更新）。"""

    title: str | None = Field(None, max_length=200)
    case_type: CaseTypeEnum | None = None
    status: CaseStatusEnum | None = None
    summary: str | None = None
    conclusion: str | None = None
    rights_analysis: str | None = None
    counterparty_issues: str | None = None
    risk_analysis: dict | None = None
    recommended_departments: dict | None = None
    current_stage: str | None = None
    report: dict | None = None
    legal_references: list | None = None


class CaseOut(BaseModel):
    """案件完整输出。"""

    id: UUID
    user_id: UUID
    title: str
    case_type: CaseTypeEnum
    status: CaseStatusEnum
    description: str | None
    summary: str | None
    conclusion: str | None
    rights_analysis: str | None
    counterparty_issues: str | None
    risk_analysis: dict | None
    recommended_departments: dict | None
    current_stage: str | None
    report: dict | None
    legal_references: list | None
    report_generated_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
