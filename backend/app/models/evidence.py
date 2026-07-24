"""证据模型（evidence 表）。

记录案件所需的证据项：既包含用户上传的文件（OCR 识别文本），也包含系统
提示但用户尚未提供的「待补证据」。ai_note 说明该项证据对案件的作用。
"""
from __future__ import annotations

from sqlalchemy import (
    Enum,
    Boolean,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import EvidenceCategoryEnum


class Evidence(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evidence"
    __table_args__ = (
        Index("ix_evidence_case_cat", "case_id", "category"),
    )

    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="所属案件",
    )
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
        comment="上传人",
    )
    category: Mapped[EvidenceCategoryEnum] = mapped_column(
        Enum(EvidenceCategoryEnum, values_callable=lambda e: [x.value for x in e], native_enum=False), index=True, nullable=False, comment="证据类别"
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="证据名称")
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="证据说明"
    )
    file_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="文件存储路径（上传类证据）"
    )
    file_type: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="文件扩展名"
    )
    ocr_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="OCR 识别出的文本"
    )
    is_uploaded: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否已实际提供"
    )
    # AI 对该证据的评估（为什么需要 / 证明什么）
    ai_note: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="AI 对证据作用的分析"
    )

    case = relationship("Case", back_populates="evidence")
