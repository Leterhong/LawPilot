"""Alembic 环境（异步兼容）。

使用 psycopg2 同步引擎执行迁移 DDL（与异步应用引擎解耦，迁移更稳定）。
目标元数据来自 app.models 中注册的全部 ORM 表。
"""
from __future__ import annotations

import sqlalchemy
from alembic import context
from logging.config import fileConfig

# ---------------------------------------------------------------
# 导入应用配置与模型（确保表注册到 Base.metadata）
# ---------------------------------------------------------------
from app.core.config import settings
from app.core.database import Base
from app import models  # noqa: F401  (注册所有表)

config = context.config

# 日志配置
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:  # noqa: BLE001
        pass

target_metadata = Base.metadata


def _sync_url() -> str:
    """将异步连接串转换为同步驱动连接串（供 Alembic 执行 DDL）。"""
    return settings.database_url.replace(
        "postgresql+asyncpg", "postgresql+psycopg2"
    )


def run_migrations_offline() -> None:
    """离线模式：仅生成 SQL 脚本，不连接数据库。"""
    url = _sync_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: sqlalchemy.Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库并执行迁移。"""
    connectable = sqlalchemy.create_engine(_sync_url(), pool_pre_ping=True)
    with connectable.connect() as connection:
        do_run_migrations(connection)
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
