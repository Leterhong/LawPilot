"""AI 能力中心（AI Capability Center）数据模型。

7 张新表 + 通过 ``users.is_superuser`` 增量列控制后台访问。
设计原则：**全部新增，绝不修改已有表/列**（见 ai_capability_center_db_design.md）。

- ``providers``         Provider 注册（多家 OpenAI Compatible 等）
- ``ai_models``        模型实例（参数 / 能力 / 高级配置）
- ``routing_rules``    每个 AI 功能 → 指定模型 + fallback + 策略
- ``prompt_templates`` Prompt 模板（按功能 key）
- ``prompt_versions``  Prompt 版本历史
- ``model_usage``      Token / 费用 / 调用 / 失败率（按天聚合）
- ``model_logs``       每次调用明细（日志中心）
- ``model_health``     定时探测各能力状态（健康检测）
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin

# ---------------------------------------------------------------------------
# 常量：Provider 类型 / 路由功能 / 路由策略 / 能力键
# ---------------------------------------------------------------------------
PROVIDER_TYPES = [
    "openai_compatible",
    "openai",
    "anthropic",
    "gemini",
    "azure",
    "openrouter",
    "siliconflow",
    "bailian",
    "volcano",
    "zhipu",
    "moonshot",
    "deepseek",
    "ollama",
    "lmstudio",
    "vllm",
    "xinference",
    "custom",
]

# LawPilot 全部 AI 功能（路由规则 feature 枚举）
AI_FEATURES = [
    "legal_analysis",       # 法律分析
    "law_explain",          # 法条解释
    "case_summary",         # 案例总结
    "case_search",          # 案例搜索
    "case_overview",        # 案件总结
    "contract_review",      # 合同审查
    "ocr_analysis",         # OCR 分析
    "image_understanding",  # 图片理解
    "document_generation",  # 文书生成
    "prompt_optimize",      # Prompt 优化
    "workflow_planning",    # Workflow 规划
    "agent_reasoning",      # Agent 推理
    "embedding",            # Embedding
    "reranker",             # Reranker
    "web_search",           # 联网搜索
    "chat",                 # 聊天
    "timeline_generation",  # 时间线生成
    "evidence_analysis",    # 证据分析
]

ROUTING_STRATEGIES = [
    "lowest_cost",
    "fastest",
    "highest_quality",
    "balanced",
    "custom",
]

# 能力键（对应 capabilities JSONB 与测试连接探测项）
CAPABILITY_KEYS = [
    "chat",
    "embedding",
    "vision",
    "streaming",
    "json_mode",
    "function_calling",
    "web_search",
    "reasoning",
]


def _default_capabilities() -> dict:
    return {
        "chat": True,
        "embedding": False,
        "vision": False,
        "streaming": True,
        "json_mode": True,
        "function_calling": True,
        "web_search": False,
        "reasoning": False,
    }


def _default_advanced() -> dict:
    return {
        "auto_retry": 3,
        "max_concurrency": 4,
        "rate_limit_rpm": 0,
        "rate_limit_tpm": 0,
    }


# ---------------------------------------------------------------------------
# 1) providers
# ---------------------------------------------------------------------------
class Provider(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "providers"

    name: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, comment="显示名（硅基流动 / OpenRouter…）"
    )
    type: Mapped[str] = mapped_column(
        String(48), nullable=False, comment="Provider 类型，决定 AIManager 客户端构建方式"
    )
    base_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="OpenAI Compatible 端点"
    )
    api_key: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="加密存储的 API Key"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="是否启用"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# 2) ai_models
# ---------------------------------------------------------------------------
class AIModel(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ai_models"

    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="显示名")
    provider_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联 Provider（可空＝独立自定义模型）",
    )
    provider_type: Mapped[str | None] = mapped_column(
        String(48), nullable=True, comment="冗余缓存，避免每次调用 join"
    )

    api_key: Mapped[str | None] = mapped_column(Text, nullable=True, comment="加密存储，可覆盖 Provider 的 key")
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="可覆盖 Provider 的 base_url")
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="实际发给 API 的模型 ID")
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vision_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reranker_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="向量维度，默认 1024")

    temperature: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    top_p: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    timeout: Mapped[int] = mapped_column(Integer, default=60, nullable=False, comment="秒")
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="全局默认（至多一个）")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    capabilities: Mapped[dict] = mapped_column(
        JSONB, default=_default_capabilities, nullable=False, comment="能力开关"
    )
    advanced: Mapped[dict] = mapped_column(
        JSONB, default=_default_advanced, nullable=False, comment="高级配置（重试/并发/限流）"
    )


# ---------------------------------------------------------------------------
# 3) routing_rules
# ---------------------------------------------------------------------------
class RoutingRule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "routing_rules"

    feature: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="AI 功能 key（见 AI_FEATURES）"
    )
    model_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_models.id", ondelete="CASCADE"), nullable=False
    )
    fallback_model_ids: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, comment="有序 fallback 链（UUID 列表）"
    )
    strategy: Mapped[str] = mapped_column(
        String(24), default="balanced", nullable=False, comment="lowest_cost/fastest/highest_quality/balanced/custom"
    )
    auto_route: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="true=按策略+任务类型自动选模型"
    )
    prompt_template_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="关联 prompt_templates.key；空=内置默认"
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="拖拽排序用")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ---------------------------------------------------------------------------
# 4) prompt_templates
# ---------------------------------------------------------------------------
class PromptTemplate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "prompt_templates"

    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="功能 key")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="显示名")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="模板体，支持 {{variable}} 占位")
    variables: Mapped[list | None] = mapped_column(JSONB, nullable=True, comment="变量定义列表")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True, comment="可选：固定绑定某模型"
    )


# ---------------------------------------------------------------------------
# 5) prompt_versions
# ---------------------------------------------------------------------------
class PromptVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "prompt_versions"

    template_id: Mapped[UUID] = mapped_column(
        ForeignKey("prompt_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="变更说明")
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        # UNIQUE (template_id, version) —— 在迁移里以 Index 形式保证
        # （此处不在 ORM 层重复声明，避免与 alembic 生成冲突）
    )


# ---------------------------------------------------------------------------
# 6) model_usage（按天聚合）
# ---------------------------------------------------------------------------
class ModelUsage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "model_usage"

    date: Mapped[date] = mapped_column(nullable=False)
    model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai_models.id", ondelete="CASCADE"), nullable=True
    )
    provider_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="系统调用为 NULL"
    )
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(14, 6), default=Decimal("0"), nullable=False)
    cost_currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


# ---------------------------------------------------------------------------
# 7) model_logs（每次调用明细）
# ---------------------------------------------------------------------------
class ModelLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "model_logs"

    model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    feature: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    endpoint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    capability: Mapped[str | None] = mapped_column(String(32), nullable=True)
    request_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(14, 6), default=Decimal("0"), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="success", nullable=False)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )


# ---------------------------------------------------------------------------
# 8) model_health（定时探测）
# ---------------------------------------------------------------------------
class ModelHealth(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "model_health"

    model_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_models.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL"), nullable=True
    )
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chat_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    vision_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    embedding_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    streaming_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    json_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    function_calling_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    web_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="healthy/degraded/down")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
