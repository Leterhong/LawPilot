"""文书模型（documents 表）。

保存由系统自动生成的各类法律文书模板（催告函、律师函、投诉书、
仲裁申请书、起诉状、答辩状、证据目录）。内容以 Markdown 存储，便于预览与导出。
"""
from __future__ import annotations

from sqlalchemy import (
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import DocStatusEnum, DocTypeEnum


class Document(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_case_type", "case_id", "doc_type"),
    )

    case_id: Mapped[str | None] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
        comment="所属案件（模板库文书可为空）",
    )
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
        comment="生成人",
    )
    doc_type: Mapped[DocTypeEnum] = mapped_column(
        Enum(DocTypeEnum, values_callable=lambda e: [x.value for x in e], native_enum=False), index=True, nullable=False, comment="文书类型"
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="文书标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="文书正文（Markdown）")
    status: Mapped[DocStatusEnum] = mapped_column(
        Enum(DocStatusEnum, values_callable=lambda e: [x.value for x in e], native_enum=False), default=DocStatusEnum.DRAFT, nullable=False, comment="文书状态"
    )

    case = relationship("Case", back_populates="documents")
