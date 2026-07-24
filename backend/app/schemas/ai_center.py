"""AI 能力中心 Pydantic Schema。

约定：
- ``*Create`` / ``*Update`` 接收**明文** API Key（创建时）；响应 ``*Out`` 一律返回
  **脱敏**后的 Key（``sk-12...ab``），明文不暴露。
- 列表/详情接口会回填 ``model_name`` / ``provider_name`` 等关联展示字段。
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.ai_center import (
    AI_FEATURES,
    CAPABILITY_KEYS,
    PROVIDER_TYPES,
    ROUTING_STRATEGIES,
)


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------
class ProviderCreate(BaseModel):
    name: str = Field(..., max_length=128)
    type: str = Field(..., description="见 PROVIDER_TYPES")
    base_url: str | None = Field(None, max_length=512)
    api_key: str | None = Field(None, description="明文 Key，存储时加密")
    enabled: bool = True
    description: str | None = None


class ProviderUpdate(BaseModel):
    name: str | None = Field(None, max_length=128)
    type: str | None = None
    base_url: str | None = Field(None, max_length=512)
    api_key: str | None = Field(None, description="传空字符串表示不修改；传新值覆盖")
    enabled: bool | None = None
    description: str | None = None


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    type: str
    base_url: str | None
    api_key: str | None = Field(None, description="脱敏展示")
    enabled: bool
    description: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# AIModel
# ---------------------------------------------------------------------------
class AIModelCreate(BaseModel):
    name: str = Field(..., max_length=128)
    provider_id: UUID | None = None
    provider_type: str | None = Field(None, description="留空则取 provider.type")
    api_key: str | None = Field(None, description="明文，可覆盖 provider 的 key")
    base_url: str | None = Field(None, max_length=512)
    model_name: str = Field(..., max_length=128)
    embedding_model: str | None = Field(None, max_length=128)
    vision_model: str | None = Field(None, max_length=128)
    reranker_model: str | None = Field(None, max_length=128)
    embedding_dim: int | None = 1024
    temperature: float = 0.2
    top_p: float = 1.0
    timeout: int = 60
    max_tokens: int | None = None
    is_default: bool = False
    is_enabled: bool = True
    capabilities: dict | None = None
    advanced: dict | None = None


class AIModelUpdate(BaseModel):
    name: str | None = Field(None, max_length=128)
    provider_id: UUID | None = None
    provider_type: str | None = None
    api_key: str | None = Field(None, description="传空字符串表示不修改；传新值覆盖")
    base_url: str | None = Field(None, max_length=512)
    model_name: str | None = Field(None, max_length=128)
    embedding_model: str | None = Field(None, max_length=128)
    vision_model: str | None = Field(None, max_length=128)
    reranker_model: str | None = Field(None, max_length=128)
    embedding_dim: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    timeout: int | None = None
    max_tokens: int | None = None
    is_default: bool | None = None
    is_enabled: bool | None = None
    capabilities: dict | None = None
    advanced: dict | None = None


class AIModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    provider_id: UUID | None
    provider_name: str | None = None
    provider_type: str | None
    api_key: str | None = Field(None, description="脱敏展示")
    base_url: str | None
    model_name: str
    embedding_model: str | None
    vision_model: str | None
    reranker_model: str | None
    embedding_dim: int | None
    temperature: float
    top_p: float
    timeout: int
    max_tokens: int | None
    is_default: bool
    is_enabled: bool
    capabilities: dict
    advanced: dict
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
class RoutingRuleCreate(BaseModel):
    feature: str = Field(..., description="见 AI_FEATURES")
    model_id: UUID
    fallback_model_ids: list[UUID] | None = None
    strategy: str = "balanced"
    auto_route: bool = False
    prompt_template_key: str | None = Field(None, max_length=64)
    priority: int = 0
    enabled: bool = True


class RoutingRuleUpdate(BaseModel):
    feature: str | None = None
    model_id: UUID | None = None
    fallback_model_ids: list[UUID] | None = None
    strategy: str | None = None
    auto_route: bool | None = None
    prompt_template_key: str | None = Field(None, max_length=64)
    priority: int | None = None
    enabled: bool | None = None


class RoutingRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    feature: str
    model_id: UUID
    model_name: str | None = None
    fallback_model_ids: list[UUID] | None
    strategy: str
    auto_route: bool
    prompt_template_key: str | None
    priority: int
    enabled: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
class PromptTemplateCreate(BaseModel):
    key: str = Field(..., max_length=64)
    name: str = Field(..., max_length=128)
    content: str
    variables: list[dict] | None = None
    enabled: bool = True
    model_id: UUID | None = None


class PromptTemplateUpdate(BaseModel):
    key: str | None = Field(None, max_length=64)
    name: str | None = Field(None, max_length=128)
    content: str | None = None
    variables: list[dict] | None = None
    enabled: bool | None = None
    model_id: UUID | None = None


class PromptTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    key: str
    name: str
    content: str
    variables: list[dict] | None
    enabled: bool
    current_version: int
    model_id: UUID | None
    model_name: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class PromptVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template_id: UUID
    version: int
    content: str
    variables: list[dict] | None
    note: str | None
    created_by: UUID | None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# 测试连接
# ---------------------------------------------------------------------------
class TestConnectionRequest(BaseModel):
    model_id: UUID | None = Field(None, description="已存在的模型，优先使用其配置")
    provider_type: str | None = Field(None, description="内联配置时使用")
    base_url: str | None = None
    api_key: str | None = Field(None, description="明文")
    model_name: str | None = None
    capability: str = "chat"  # chat / embedding / vision / streaming


class TestConnectionResult(BaseModel):
    status: str  # ok / fail
    capability: str
    latency_ms: int | None = None
    capabilities_detected: list[str] = Field(default_factory=list)
    model: str | None = None
    provider_type: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# 统计 / 日志 / 健康
# ---------------------------------------------------------------------------
class ModelUsageRow(BaseModel):
    date: datetime.date
    model_id: UUID | None
    model_name: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost: Decimal = Decimal("0")
    cost_currency: str = "USD"
    calls: int = 0
    failures: int = 0
    avg_latency_ms: int = 0
    failure_rate: float = 0.0


class StatisticsOut(BaseModel):
    per_day: list[ModelUsageRow] = Field(default_factory=list)
    per_model: list[ModelUsageRow] = Field(default_factory=list)
    totals: dict = Field(default_factory=dict)
    range: dict = Field(default_factory=dict)


class ModelLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    model_id: UUID | None
    model_name: str | None = None
    provider_id: UUID | None
    user_id: UUID | None
    feature: str | None
    endpoint: str | None
    capability: str | None
    tokens_in: int
    tokens_out: int
    cost: Decimal
    latency_ms: int
    status: str
    error_text: str | None
    created_at: datetime.datetime


class ModelHealthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    model_id: UUID
    model_name: str | None = None
    provider_id: UUID | None
    last_checked: datetime.datetime | None
    chat_ok: bool | None
    vision_ok: bool | None
    embedding_ok: bool | None
    streaming_ok: bool | None
    json_ok: bool | None
    function_calling_ok: bool | None
    web_ok: bool | None
    status: str | None
    latency_ms: int | None
    error_text: str | None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# 常量导出（前端可通过 /api/ai/meta 获取）
# ---------------------------------------------------------------------------
class AIMeta(BaseModel):
    provider_types: list[str] = PROVIDER_TYPES
    features: list[str] = AI_FEATURES
    strategies: list[str] = ROUTING_STRATEGIES
    capability_keys: list[str] = CAPABILITY_KEYS
