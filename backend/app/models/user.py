"""用户模型（users 表）。

平台账户，一个用户拥有多个案件（cases）。密码以哈希存储，绝不保存明文。
"""
from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False, comment="登录邮箱"
    )
    phone: Mapped[str | None] = mapped_column(
        String(32), unique=True, index=True, nullable=True, comment="手机号"
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="bcrypt 哈希后的密码"
    )
    display_name: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="昵称"
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="头像地址"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="是否启用"
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否已验证"
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否超级管理员（AI 能力中心后台访问权限）"
    )
    # 预留：用户偏好（如默认城市，用于推荐管辖部门）
    preferences: Mapped[dict | None] = mapped_column(
        Text, nullable=True, comment="用户偏好 JSON（Phase 3+ 使用）"
    )

    # 一个用户拥有多个案件
    cases = relationship(
        "Case", back_populates="user", cascade="all, delete-orphan"
    )
