"""add law table (Law Search 模块)

仅新建独立的 ``law`` 表，不改动任何已有业务表，确保不影响 Phase 1 功能。
BM25 全文检索由 STORED 生成列 ``search_vector``（tsvector）+ GIN 索引支撑；
语义检索由 pgvector 列 ``embedding`` 支撑。
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


revision: str = 'b90ce42b8e48'
down_revision: str | None = '0001_initial'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'law',
        sa.Column('law_name', sa.String(length=300), nullable=False,
                  comment='法律名称，如「中华人民共和国民法典」'),
        sa.Column('chapter', sa.String(length=200), nullable=True,
                  comment='章，如「第二编 物权」'),
        sa.Column('section', sa.String(length=200), nullable=True,
                  comment='节，如「第十章 一般规定」'),
        sa.Column('article', sa.String(length=100), nullable=True,
                  comment='条款编号，如「第577条」'),
        sa.Column('content', sa.Text(), nullable=False, comment='法条正文'),
        sa.Column('keywords', sa.JSON(), nullable=True,
                  comment='关键词标签数组（用于精确过滤、分类与高亮）'),
        sa.Column('effective_date', sa.String(length=32), nullable=True,
                  comment='生效日期，格式 YYYY-MM-DD'),
        sa.Column('status', sa.String(length=32), nullable=False,
                  comment='现状：effective / amended / repealed / pending'),
        sa.Column('source', sa.String(length=300), nullable=True,
                  comment='来源（发布机关 / 出处）'),
        sa.Column('embedding', Vector(dim=1024), nullable=True,
                  comment='法条语义向量'),
        sa.Column(
            'search_vector',
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('simple', "
                "coalesce(law_name,'') || ' ' || coalesce(chapter,'') || ' ' || "
                "coalesce(section,'') || ' ' || coalesce(article,'') || ' ' || "
                "coalesce(content,'') || ' ' || coalesce(source,'')"
                ")",
                persisted=True,
            ),
            nullable=True,
            comment='全文检索向量（BM25 词法检索）',
        ),
        sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False,
                  comment='创建时间（UTC）'),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False,
                  comment='更新时间（UTC）'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_law_article'), 'law', ['article'], unique=False)
    op.create_index(op.f('ix_law_chapter'), 'law', ['chapter'], unique=False)
    op.create_index(op.f('ix_law_effective_date'), 'law',
                    ['effective_date'], unique=False)
    op.create_index(op.f('ix_law_law_name'), 'law', ['law_name'], unique=False)
    op.create_index('ix_law_search_vector', 'law', ['search_vector'],
                    unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_law_source'), 'law', ['source'], unique=False)
    op.create_index(op.f('ix_law_status'), 'law', ['status'], unique=False)
    op.create_index('uq_law_name_article', 'law', ['law_name', 'article'],
                    unique=True, postgresql_where=sa.text('article IS NOT NULL'))


def downgrade() -> None:
    op.drop_index('uq_law_name_article', table_name='law',
                  postgresql_where=sa.text('article IS NOT NULL'))
    op.drop_index(op.f('ix_law_status'), table_name='law')
    op.drop_index(op.f('ix_law_source'), table_name='law')
    op.drop_index('ix_law_search_vector', table_name='law',
                  postgresql_using='gin')
    op.drop_index(op.f('ix_law_law_name'), table_name='law')
    op.drop_index(op.f('ix_law_effective_date'), table_name='law')
    op.drop_index(op.f('ix_law_chapter'), table_name='law')
    op.drop_index(op.f('ix_law_article'), table_name='law')
    op.drop_table('law')
