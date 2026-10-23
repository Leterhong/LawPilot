"""消息模型（messages 表）。

案件内的多轮对话记录。Agent 的追问、用户的回答、系统事件均落表，
保证完整可回放。metadata 用于存放引用来源、关联证据、快捷回复选项等。
"""
from __future__ import annotations

from sqlalchemy import (
    JSON,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import MessageTypeEnum, RoleEnum


class Message(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_case_seq", "case_id", "sequence"),
    )

    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="所属案件",
    )
    role: Mapped[RoleEnum] = mapped_column(
        Enum(RoleEnum, values_callable=lambda e: [x.value for x in e], native_enum=False), nullable=False, comment="角色：user/assistant/system"
    )
    message_type: Mapped[MessageTypeEnum] = mapped_column(
        Enum(MessageTypeEnum, values_callable=lambda e: [x.value for x in e], native_enum=False), default=MessageTypeEnum.TEXT, nullable=False, comment="消息类型"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息内容")
    sequence: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="同一案件内的递增序号，用于排序"
    )
    # 结构化元数据：引用来源(citations)、关联证据(evidence_ids)、快捷选项(options)等
    metadata_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="扩展元数据"
    )

    case = relationship("Case", back_populates="messages")
