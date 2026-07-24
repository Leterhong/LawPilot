"""add law search history

仅新建独立的 ``law_search_history`` 表，不改动任何已有业务表，确保不影响
Phase 1 功能与第一步的 ``law`` 表。
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '44937a9ecb99'
down_revision: str | None = 'b90ce42b8e48'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'law_search_history',
        sa.Column('user_id', sa.Uuid(), nullable=True,
                  comment='用户ID（匿名搜索为 NULL）'),
        sa.Column('query', sa.String(length=300), nullable=False,
                  comment='查询词'),
        sa.Column('result_count', sa.Integer(), nullable=True,
                  comment='本次搜索命中条数'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False,
                  comment='搜索时间（UTC）'),
        sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'],
                                ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_law_search_history_created_at'),
                    'law_search_history', ['created_at'], unique=False)
    op.create_index(op.f('ix_law_search_history_query'),
                    'law_search_history', ['query'], unique=False)
    op.create_index(op.f('ix_law_search_history_user_id'),
                    'law_search_history', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_law_search_history_user_id'),
                  table_name='law_search_history')
    op.drop_index(op.f('ix_law_search_history_query'),
                  table_name='law_search_history')
    op.drop_index(op.f('ix_law_search_history_created_at'),
                  table_name='law_search_history')
    op.drop_table('law_search_history')
