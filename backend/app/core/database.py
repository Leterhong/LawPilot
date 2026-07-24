"""数据库基础设施。

基于 SQLAlchemy 2.0 异步引擎构建，提供：
- :data:`engine`：异步引擎（连接池）
- :data:`AsyncSessionLocal`：会话工厂
- :class:`Base`：所有 ORM 模型的声明基类
- :func:`get_db`：FastAPI 依赖注入，提供请求级会话
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。

    后续 Phase 2 中的 users、cases、messages 等表均继承此类。
    """


# 创建异步引擎。echo 仅在开发环境打印 SQL，便于调试。
engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    pool_pre_ping=True,
    future=True,
)

# 会话工厂：expire_on_commit=False 避免提交后对象属性过期
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：为每个请求提供一个异步数据库会话。

    使用上下文管理器确保会话始终被关闭，避免连接泄漏。
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """初始化数据库（创建所有表）。

    注意：生产环境应使用 Alembic 迁移而非直接 create_all。
    此函数主要用于本地开发快速建表与测试。

    会先确保 pgvector 扩展存在（向量检索依赖），并导入全部模型模块
    以将表注册到 ``Base.metadata``。
    """
    # 导入模型模块，将全部表注册到 Base.metadata
    from app import models  # noqa: F401
    from sqlalchemy import text

    async with engine.begin() as conn:
        # 确保向量扩展存在（无则创建；已存在则忽略）
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
