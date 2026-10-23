"""合同智能中心（Contract Intelligence Center）数据模型。

本文件仅定义 **contracts** 主表（Step2 OCR 与文件解析落地所需），其余子表
（contract_versions / contract_clauses / contract_risks / contract_reports /
contract_templates / contract_tasks / contract_chunks）将在后续步骤各自的迁移中新增。

设计原则（与「AI 能力中心」「AI Playground」一致）：
- 复用 ``users`` / ``ai_models``（FK 一律 SET NULL），绝不 ALTER 任何已有表/列。
- ``contracts`` 一次性给出完整字段（含后续 AI 分析列），后续步骤只做 UPDATE，避免反复改表。
- 所有共享常量集中在文件顶部，供 Step2~Step7 复用。
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin

# ---------------------------------------------------------------------------
# 共享常量（Step2~Step7 复用）
# ---------------------------------------------------------------------------

# 合同类型（自动分类 + 模板分类共用）
CONTRACT_TYPES = [
    "rent",          # 租房合同
    "labor",         # 劳动合同
    "sales",         # 买卖合同 / 销售合同
    "service",       # 服务合同 / 服务协议
    "nda",           # 保密协议
    "cooperation",   # 合作协议
    "loan",          # 借款合同
    "purchase",      # 采购合同
    "other",         # 其他
]

# 合同类型中文标签（前端展示用）
CONTRACT_TYPE_LABELS = {
    "rent": "租房合同",
    "labor": "劳动合同",
    "sales": "买卖合同",
    "service": "服务合同",
    "nda": "保密协议",
    "cooperation": "合作协议",
    "loan": "借款合同",
    "purchase": "采购合同",
    "other": "其他",
}

# 风险分类（Risk Dashboard 按此聚合）
CONTRACT_RISK_CATEGORIES = [
    "payment",          # 付款
    "breach",           # 违约
    "confidentiality",  # 保密
    "ip",               # 知识产权
    "termination",      # 解除合同
    "liability",        # 赔偿责任
    "force_majeure",    # 不可抗力
    "dispute",          # 争议解决
]

# 风险等级
CONTRACT_RISK_LEVELS = ["low", "medium", "high"]

# 合同处理状态
CONTRACT_STATUS = ["uploaded", "parsing", "analyzed", "error"]

# 任务类型（contract_tasks.type）
CONTRACT_TASK_TYPES = ["reminder", "checklist"]

# 提醒分类
CONTRACT_REMINDER_CATEGORIES = ["expiry", "payment", "renewal", "sign_check", "other"]

# 报告类型
CONTRACT_REPORT_TYPES = ["review", "summary", "full", "checklist"]

# 合同模块允许的文件类型（独立允许列表，不改全局 allowed_extensions）
CONTRACT_ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg"]


# ---------------------------------------------------------------------------
# contracts —— 合同主记录 + AI 分析结果（Step2 落地）
# ---------------------------------------------------------------------------
class Contract(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "contracts"

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="归属用户；系统/匿名上传为 NULL",
    )
    title: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="合同标题（默认文件名）"
    )
    contract_type: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="AI 自动分类，见 CONTRACT_TYPES"
    )
    status: Mapped[str] = mapped_column(
        String(24), default="uploaded", nullable=False,
        comment="uploaded/parsing/analyzed/error",
    )

    # 文件与原文
    file_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="原文存储路径（upload_dir）"
    )
    storage_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="对象存储 key（若启用对象存储）"
    )
    file_type: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="pdf/docx/txt/md/png/jpg"
    )
    file_size: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="字节"
    )
    full_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="解析后的纯文本全文"
    )
    ocr_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="OCR 原始文本（图片/扫描件）"
    )
    language: Mapped[str] = mapped_column(
        String(8), default="zh", nullable=False
    )
    page_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    # AI 分析结果（Step3 填充，这里预留列，避免后续改表）
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="① 一句话合同摘要")
    law_involved: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="③ 涉及法律 [{law_id, name, article, url?}]"
    )
    risk_score: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="⑤ 风险总分 0-100"
    )
    risk_level: Mapped[str] = mapped_column(
        String(16), default="low", nullable=False, comment="low/medium/high"
    )
    risk_clauses: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="⑤ 高风险条款摘要缓存"
    )
    king_clauses: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="⑥ 霸王条款检测 [{clause, reason, suggestion}]"
    )
    payment_risk: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="⑦ 付款风险 {level, detail, suggestion}"
    )
    breach_risk: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="⑧ 违约风险"
    )
    liability_risk: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="⑨ 赔偿责任"
    )

    # 模型与用量
    model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai_models.id", ondelete="SET NULL"),
        nullable=True, comment="主分析模型（冗余显示）",
    )
    analysis_meta: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="{summary_model, review_model, legal_model, latency_ms}"
    )
    token_usage: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="{in, out, total, cost, currency}"
    )
    analyzed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 检查清单（Checklist 冗余缓存）
    checklist: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="[{item, checked, category}]"
    )

    __table_args__ = (
        Index("ix_contracts_user_id", "user_id"),
        Index("ix_contracts_contract_type", "contract_type"),
        Index("ix_contracts_risk_level", "risk_level"),
        Index("ix_contracts_created_at", "created_at"),
    )


# ---------------------------------------------------------------------------
# contract_risks —— 风险条款明细（Risk Dashboard 数据源，Step3 落地）
# ---------------------------------------------------------------------------
class ContractRisk(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "contract_risks"

    contract_id: Mapped[UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联合同（删除合同级联）",
    )
    clause_ref: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="条款引用，如『第8条』"
    )
    clause_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="风险条款原文"
    )
    category: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="风险分类，见 CONTRACT_RISK_CATEGORIES"
    )
    risk_level: Mapped[str] = mapped_column(
        String(16), default="medium", nullable=False, index=True,
        comment="low/medium/high",
    )
    score: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="该条款风险分 0-100"
    )
    reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="风险原因"
    )
    suggestion: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="修改建议"
    )
    suggested_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="推荐修改版本"
    )
    king_clause: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否霸王条款（⑥）"
    )

    __table_args__ = (
        Index("ix_contract_risks_category", "category"),
        Index("ix_contract_risks_risk_level", "risk_level"),
    )


# ---------------------------------------------------------------------------
# contract_clauses —— 逐条款（Clause Analyzer 点击对象，Step3 落地）
# ---------------------------------------------------------------------------
class ContractClause(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "contract_clauses"

    contract_id: Mapped[UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联合同（删除合同级联）",
    )
    clause_no: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="条款号，如『第8条』/『8.2』"
    )
    section: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="章节标题"
    )
    clause_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="条款原文"
    )
    category: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="关联风险分类（若已识别）"
    )
    order_index: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="条款顺序"
    )
    # Clause Analyzer 的 AI 结果（点击后生成并缓存）
    explanation: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="这一条是什么意思"
    )
    risk_level: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="low/medium/high"
    )
    risk_note: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="有什么风险"
    )
    suggested_version: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="推荐修改版本"
    )

    __table_args__ = (
        Index("ix_contract_clauses_order", "contract_id", "order_index"),
    )


# ---------------------------------------------------------------------------
# contract_reports —— 审查报告（功能：报告生成，Step5 落地）
# ---------------------------------------------------------------------------
class ContractReport(UUIDMixin, TimestampMixin, Base):
    """合同审查报告（Markdown / 结构化 JSON）。

    每次生成（或重新生成）写入一条记录；同一 ``contract_id + report_type`` 仅保留
    最新一条（重新生成时先删旧再插新），避免无限增长。
    """

    __tablename__ = "contract_reports"

    contract_id: Mapped[UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联合同（删除合同级联）",
    )
    report_type: Mapped[str] = mapped_column(
        String(24), default="review", nullable=False, index=True,
        comment="review/summary/full/checklist，见 CONTRACT_REPORT_TYPES",
    )
    title: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="报告标题"
    )
    content: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Markdown 报告正文"
    )
    content_json: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="结构化报告（供前端分块渲染）"
    )
    format: Mapped[str] = mapped_column(
        String(16), default="markdown", nullable=False,
        comment="markdown/pdf/html",
    )
    generated_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, comment="生成人（用户或超管）",
    )
    model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai_models.id", ondelete="SET NULL"),
        nullable=True, comment="生成所用主模型（AI 叙事时）",
    )
    file_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="导出的 PDF/HTML 路径（未来扩展）",
    )

    __table_args__ = (
        Index("ix_contract_reports_ct_rt", "contract_id", "report_type"),
    )


# ---------------------------------------------------------------------------
# contract_tasks —— 提醒 + 签署前检查（功能：提醒中心 / Checklist，Step6 落地）
# ---------------------------------------------------------------------------
class ContractTask(UUIDMixin, TimestampMixin, Base):
    """合同相关的提醒 / 待办。

    - type=reminder：到期 / 付款 / 续签 / 签署检查等带 due_date 的提醒；
    - type=checklist：签署前检查项（可无 due_date）。
    删除合同时级联删除。
    """

    __tablename__ = "contract_tasks"

    contract_id: Mapped[UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联合同（删除合同级联）",
    )
    type: Mapped[str] = mapped_column(
        String(16), default="reminder", nullable=False, index=True,
        comment="reminder / checklist",
    )
    title: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="提醒/待办标题"
    )
    category: Mapped[str | None] = mapped_column(
        String(32), nullable=True, index=True,
        comment="提醒分类，见 CONTRACT_REMINDER_CATEGORIES（reminder 用）",
    )
    due_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="提醒日期（到期/付款/续签）"
    )
    remind_before_days: Mapped[int] = mapped_column(
        Integer, default=7, nullable=False, comment="提前 N 天提醒"
    )
    done: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True, comment="是否已完成"
    )
    priority: Mapped[str] = mapped_column(
        String(16), default="normal", nullable=False, comment="low/normal/high"
    )
    note: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="备注"
    )

    __table_args__ = (
        Index("ix_contract_tasks_due_done", "due_date", "done"),
    )


__all__ = [
    "Contract",
    "ContractRisk",
    "ContractClause",
    "ContractReport",
    "ContractTask",
    "CONTRACT_TYPES",
    "CONTRACT_TYPE_LABELS",
    "CONTRACT_RISK_CATEGORIES",
    "CONTRACT_RISK_LEVELS",
    "CONTRACT_STATUS",
    "CONTRACT_TASK_TYPES",
    "CONTRACT_REMINDER_CATEGORIES",
    "CONTRACT_REPORT_TYPES",
    "CONTRACT_ALLOWED_EXTENSIONS",
]
