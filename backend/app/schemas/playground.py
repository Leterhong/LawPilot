"""AI Playground 请求/响应 Schema。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 通用
# ---------------------------------------------------------------------------
class PlaygroundFileMeta(BaseModel):
    name: str
    size: int = 0
    type: str | None = None
    storage_key: str | None = None


# ---------------------------------------------------------------------------
# 请求
# ---------------------------------------------------------------------------
class PlaygroundTestRequest(BaseModel):
    model_id: UUID
    system_prompt: str | None = None
    user_prompt: str
    context: str | None = None
    files: list[PlaygroundFileMeta] | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    streaming: bool = False


class PlaygroundCompareRequest(BaseModel):
    model_ids: list[UUID]
    system_prompt: str | None = None
    user_prompt: str
    context: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    judge_model_id: UUID | None = None


class EvalItemIn(BaseModel):
    input: str
    expected: str | None = None
    context: str | None = None


class PlaygroundEvaluateRequest(BaseModel):
    name: str
    model_ids: list[UUID]
    judge_model_id: UUID | None = None
    dataset_id: UUID | None = None
    feature: str | None = None
    prompt_template_key: str | None = None
    config: dict | None = None
    items: list[EvalItemIn] | None = None


class PlaygroundPublishRequest(BaseModel):
    feature: str
    model_id: UUID
    note: str | None = None


# ---------------------------------------------------------------------------
# 响应
# ---------------------------------------------------------------------------
class PlaygroundModelOut(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    name: str
    provider_id: UUID | None = None
    provider_name: str | None = None
    capabilities: dict = Field(default_factory=dict)
    is_enabled: bool = True


class ChatResultOut(BaseModel):
    model_id: UUID | None = None
    model_name: str | None = None
    provider_name: str | None = None
    content: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    cost: float | None = None
    error: str | None = None


class CompareRowOut(BaseModel):
    model_id: UUID | None = None
    model_name: str | None = None
    provider_name: str | None = None
    content: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    cost: float | None = None
    score: float | None = None
    score_detail: dict | None = None
    status: str = "success"
    error: str | None = None


class PlaygroundSessionOut(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    user_id: UUID | None = None
    type: str
    title: str | None = None
    model_ids: list | None = None
    feature: str | None = None
    system_prompt: str | None = None
    user_prompt: str | None = None
    context: str | None = None
    input: dict | None = None
    output: dict | None = None
    score: float | None = None
    score_detail: dict | None = None
    token_usage: dict | None = None
    latency_ms: int = 0
    status: str = "success"
    error_text: str | None = None
    created_at: datetime


class EvaluationTaskOut(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    user_id: UUID | None = None
    name: str
    model_ids: list
    judge_model_id: UUID | None = None
    feature: str | None = None
    status: str = "pending"
    total_items: int = 0
    processed_items: int = 0
    score_summary: dict | None = None
    created_at: datetime


class EvaluationResultOut(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    task_id: UUID
    item_id: UUID | None = None
    model_id: UUID | None = None
    input: str | None = None
    expected: str | None = None
    output: str | None = None
    is_correct: bool | None = None
    is_json_valid: bool | None = None
    has_hallucination: bool | None = None
    score: float | None = None
    metrics: dict | None = None
    latency_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    error_text: str | None = None
    created_at: datetime


class EvaluationDatasetOut(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    user_id: UUID | None = None
    name: str
    category: str | None = None
    description: str | None = None
    is_public: bool = False
    item_count: int = 0
    created_at: datetime


class EvaluationItemOut(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    dataset_id: UUID
    input: str
    expected: str | None = None
    context: str | None = None
    order_index: int = 0


class PromptLibraryOut(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    user_id: UUID | None = None
    name: str
    category: str | None = None
    prompt: str
    variables: list | None = None
    score: float | None = None
    tags: list | None = None
    is_public: bool = False
    created_at: datetime
    updated_at: datetime


class PromptLibraryCreate(BaseModel):
    name: str
    category: str | None = None
    prompt: str
    variables: list | None = None
    tags: list | None = None
    is_public: bool = False


class PromptLibraryUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    prompt: str | None = None
    variables: list | None = None
    tags: list | None = None
    is_public: bool | None = None


class PlaygroundPublishOut(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    feature: str
    from_model_id: UUID | None = None
    to_model_id: UUID | None = None
    routing_rule_id: UUID | None = None
    note: str | None = None
    created_at: datetime


class RoutingRuleSimpleOut(BaseModel):
    feature: str
    model_id: UUID
    model_name: str | None = None
    enabled: bool
