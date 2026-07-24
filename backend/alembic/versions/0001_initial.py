"""initial schema

修订标识: 0001_initial
创建时间: 2026-07-20

说明：本初始迁移作为「单一可信来源」引导——直接依据 app.models 中定义的
SQLAlchemy 元数据创建全部表（users / cases / messages / documents / evidence /
roadmaps / roadmap_steps / legal_reference / workflow / tasks / history / knowledge），
并为 legal_reference、knowledge 的向量列建立 ivfflat 余弦索引。
后续结构变更请使用 `alembic revision --autogenerate -m "..."` 生成增量迁移。
"""
from collections.abc import Sequence

from alembic import op

# 使用 pgvector 向量类型
from pgvector.sqlalchemy import Vector  # noqa: F401

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) 确保向量扩展存在
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2) 依据 ORM 元数据创建全部表（单一可信来源 = app/models）
    from app.core.database import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    # 3) 为向量列建立 ivfflat 余弦相似度索引（提升检索性能）
    op.create_index(
        "ix_legal_reference_embedding",
        "legal_reference",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"lists": 100},
    )
    op.create_index(
        "ix_knowledge_embedding",
        "knowledge",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"lists": 100},
    )


def downgrade() -> None:
    # 1) 删除向量索引
    op.drop_index("ix_knowledge_embedding", table_name="knowledge")
    op.drop_index("ix_legal_reference_embedding", table_name="legal_reference")

    # 2) 删除全部表（说明：枚举字段采用 String 存储，不创建原生 PG 枚举类型，
    #    因此无需额外的 DROP TYPE 处理）
    from app.core.database import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
