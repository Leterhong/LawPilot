"""ORM 基础构件。

- :data:`Base`：统一从 core.database 导入，保证与引擎、会话共用同一声明基类。
- :class:`UUIDMixin`：UUID 主键（全局唯一，适合分布式/导出场景）。
- :class:`TimestampMixin`：创建/更新时间，由数据库服务端默认时间保证一致性。

各业务模型通过多重继承以上 Mixin 获得统一的 id 与时间戳字段。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UUIDMixin:
    """UUID 主键混入。"""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        comment="全局唯一主键",
    )


class TimestampMixin:
    """创建/更新时间戳混入。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间（UTC）",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间（UTC）",
    )


__all__ = ["Base", "UUIDMixin", "TimestampMixin"]
