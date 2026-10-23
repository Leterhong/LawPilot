"""AI Playground（AI 模型测试中心）数据模型。

9 张表，全部为**新增**，绝不修改、不删除任何已有表/列。
设计原则（见 ai_playground_db_design.md）：
- 复用 ``ai_models`` / ``routing_rules`` / ``prompt_templates`` / ``users``（FK 一律 SET NULL）。
- 所有测试/评测记录归属 ``user_id``（可空＝匿名/系统）。
- 「应用到生产」是服务层 UPDATE ``routing_rules``（数据操作，不改表结构）。
"""
from __future__ import annotations

from datetime import datetime
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
# 常量
# ---------------------------------------------------------------------------
PLAYGROUND_TYPES = [
    "single",   # 单模型测试
    "compare",  # 多模型对比
    "prompt",   # Prompt 测试
    "evaluate", # 模型评测
    "routing",  # AI 路由测试
]

SESSION_STATUS = ["success", "error", "timeout", "partial"]
EVAL_STATUS = ["pending", "running", "done", "error", "partial"]

# AI 自动评分维度（多模型对比 & 评测共用）
SCORE_DIMS = [
    "accuracy",        # 准确性
    "completeness",    # 完整性
    "professionalism", # 专业性
    "logic",           # 逻辑性
    "format",          # 格式
    "citation",        # 引用质量
]

# Prompt 变量（Prompt 测试）
PROMPT_VARIABLES = ["case", "law", "context", "document"]

# 评测指标
EVAL_METRICS = [
    "accuracy",
    "latency",
    "token_cost",
    "stability",
    "hallucination_rate",
    "json_success_rate",
]


# ---------------------------------------------------------------------------
# 1) playground_sessions —— 测试历史（统一记录）
# ---------------------------------------------------------------------------
class PlaygroundSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "playground_sessions"

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(24), nullable=False, comment="single/compare/prompt/evaluate/routing")
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True, comment="选中模型 id 列表")
    feature: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="关联 routing_rules.feature（routing/评测用）"
    )
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    files: Mapped[list | None] = mapped_column(JSONB, nullable=True, comment="上传文件元信息 [{name,size,type,storage_key}]")
    params: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="{temperature, top_p, max_tokens, streaming}")
    input: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="完整输入快照（可重放）")
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="主结果摘要")
    score: Mapped[float | None] = mapped_column(Float, nullable=True, comment="自动评分总分")
    score_detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="各维度评分")
    token_usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="{in, out, total, cost}")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="success", nullable=False)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# 2) model_comparisons —— 多模型对比逐条结果
# ---------------------------------------------------------------------------
class ModelComparison(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "model_comparisons"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("playground_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True
    )
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="冗余缓存显示名")
    provider_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL"), nullable=True
    )
    provider_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(14, 6), default=Decimal("0"), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="success", nullable=False)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# 3) evaluation_datasets —— 测试集元数据
# ---------------------------------------------------------------------------
class EvaluationDataset(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_datasets"

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="关联 AI_FEATURES")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


# ---------------------------------------------------------------------------
# 4) evaluation_items —— 测试集单题
# ---------------------------------------------------------------------------
class EvaluationItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_items"

    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    input: Mapped[str] = mapped_column(Text, nullable=False)
    expected: Mapped[str | None] = mapped_column(Text, nullable=True, comment="期望答案/参考答案")
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


# ---------------------------------------------------------------------------
# 5) evaluation_tasks —— 评测运行
# ---------------------------------------------------------------------------
class EvaluationTask(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_tasks"

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    dataset_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("evaluation_datasets.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_ids: Mapped[list] = mapped_column(JSONB, nullable=False, comment="被测模型 id 列表")
    judge_model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True, comment="LLM Judge 评分模型"
    )
    feature: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_template_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="{temperature, top_p, max_tokens}")
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    total_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="聚合指标")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# 6) evaluation_results —— 评测逐题结果
# ---------------------------------------------------------------------------
class EvaluationResult(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_results"

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("evaluation_items.id", ondelete="SET NULL"), nullable=True
    )
    model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True
    )
    input: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_json_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_hallucination: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True, comment="judge 评分 0-100")
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(14, 6), default=Decimal("0"), nullable=False)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# 7) prompt_library —— 收藏的优秀 Prompt
# ---------------------------------------------------------------------------
class PromptLibrary(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "prompt_library"

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False, comment="完整 prompt，支持 {{var}}")
    variables: Mapped[list | None] = mapped_column(JSONB, nullable=True, comment="[{name, default, desc}]")
    score: Mapped[float | None] = mapped_column(Float, nullable=True, comment="历史最佳得分")
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


# ---------------------------------------------------------------------------
# 8) model_pricing —— 模型单价（用于「预计成本」，不修改 ai_models）
# ---------------------------------------------------------------------------
class ModelPricing(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "model_pricing"

    model_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_models.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    price_in_per_1k: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0"), nullable=False)
    price_out_per_1k: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0"), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# 9) playground_publishes —— 发布审计（一键应用到生产）
# ---------------------------------------------------------------------------
class PlaygroundPublish(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "playground_publishes"

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("playground_sessions.id", ondelete="SET NULL"), nullable=True
    )
    feature: Mapped[str] = mapped_column(String(64), nullable=False, comment="被改写的 routing feature")
    from_model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True
    )
    to_model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True
    )
    routing_rule_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("routing_rules.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
