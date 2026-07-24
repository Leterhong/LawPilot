"""add legal_cases tables (Legal Case Search 模块)

仅新建独立的 ``legal_cases`` 与 ``legal_case_favorites`` 两张表，不改动任何已有
业务表，确保不影响 Phase 1/2/3 功能。

BM25 全文检索由 STORED 生成列 ``search_vector``（tsvector）+ GIN 索引支撑；
语义检索由 pgvector 列 ``embedding`` 支撑；关键词过滤由 JSONB + GIN 索引支撑。
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


revision: str = 'd2c3e4f5a6b7'
down_revision: str | None = 'c1a2b3c4d5e6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op_create_legal_cases()
    op_create_legal_case_favorites()


def downgrade() -> None:
    op.drop_table('legal_case_favorites')
    op.drop_table('legal_cases')


def op_create_legal_cases() -> None:
    op.create_table(
        'legal_cases',
        sa.Column('title', sa.String(length=400), nullable=False,
                  comment='案件标题'),
        sa.Column('case_number', sa.String(length=100), nullable=True,
                  comment='案号'),
        sa.Column('court', sa.String(length=200), nullable=True,
                  comment='审理法院全称'),
        sa.Column('province', sa.String(length=50), nullable=True,
                  comment='省份'),
        sa.Column('city', sa.String(length=50), nullable=True, comment='城市'),
        sa.Column('trial_date', sa.Date(), nullable=True,
                  comment='审判日期'),
        sa.Column('case_type', sa.String(length=32), nullable=False,
                  comment='案件类型：civil/labor/contract/consumer/other'),
        sa.Column('court_level', sa.String(length=32), nullable=True,
                  comment='法院级别：basic/intermediate/advanced/supreme'),
        sa.Column('cause_of_action', sa.String(length=200), nullable=True,
                  comment='案由'),
        sa.Column('plaintiff', sa.String(length=200), nullable=True,
                  comment='原告'),
        sa.Column('defendant', sa.String(length=200), nullable=True,
                  comment='被告'),
        sa.Column('facts', sa.Text(), nullable=True, comment='案件事实'),
        sa.Column('court_reasoning', sa.Text(), nullable=True,
                  comment='法院观点 / 裁判理由'),
        sa.Column('judgement', sa.Text(), nullable=True, comment='裁判结果'),
        sa.Column('winner', sa.String(length=100), nullable=True,
                  comment='胜诉方'),
        sa.Column('compensation', sa.String(length=100), nullable=True,
                  comment='赔偿金额'),
        sa.Column('keywords', postgresql.JSONB(), nullable=True,
                  comment='关键词标签数组'),
        sa.Column('related_laws', postgresql.JSONB(), nullable=True,
                  comment='关联法律条文引用数组'),
        sa.Column('source', sa.String(length=300), nullable=True,
                  comment='来源'),
        sa.Column('embedding', Vector(dim=1024), nullable=True,
                  comment='案例语义向量（BGE-M3）'),
        sa.Column(
            'search_vector',
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('simple', "
                "coalesce(title,'') || ' ' || coalesce(court,'') || ' ' || "
                "coalesce(cause_of_action,'') || ' ' || coalesce(plaintiff,'') || ' ' || "
                "coalesce(defendant,'') || ' ' || coalesce(facts,'') || ' ' || "
                "coalesce(court_reasoning,'') || ' ' || coalesce(judgement,'')"
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
    op.create_index(op.f('ix_legal_cases_title'), 'legal_cases', ['title'],
                    unique=False)
    op.create_index(op.f('ix_legal_cases_case_number'), 'legal_cases',
                    ['case_number'], unique=False)
    op.create_index(op.f('ix_legal_cases_court'), 'legal_cases', ['court'],
                    unique=False)
    op.create_index(op.f('ix_legal_cases_province'), 'legal_cases',
                    ['province'], unique=False)
    op.create_index(op.f('ix_legal_cases_city'), 'legal_cases', ['city'],
                    unique=False)
    op.create_index(op.f('ix_legal_cases_trial_date'), 'legal_cases',
                    ['trial_date'], unique=False)
    op.create_index(op.f('ix_legal_cases_case_type'), 'legal_cases',
                    ['case_type'], unique=False)
    op.create_index(op.f('ix_legal_cases_court_level'), 'legal_cases',
                    ['court_level'], unique=False)
    op.create_index(op.f('ix_legal_cases_cause_of_action'), 'legal_cases',
                    ['cause_of_action'], unique=False)
    op.create_index(op.f('ix_legal_cases_source'), 'legal_cases',
                    ['source'], unique=False)
    op.create_index('ix_legal_cases_search_vector', 'legal_cases',
                    ['search_vector'], unique=False, postgresql_using='gin')
    op.create_index('ix_legal_cases_keywords', 'legal_cases', ['keywords'],
                    unique=False, postgresql_using='gin')


def op_create_legal_case_favorites() -> None:
    op.create_table(
        'legal_case_favorites',
        sa.Column('user_id', sa.Uuid(), nullable=False, comment='收藏用户'),
        sa.Column('case_id', sa.Uuid(), nullable=False,
                  comment='被收藏的案例'),
        sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False,
                  comment='创建时间（UTC）'),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False,
                  comment='更新时间（UTC）'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['case_id'], ['legal_cases.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_legal_case_favorites_user_id'),
                    'legal_case_favorites', ['user_id'], unique=False)
    op.create_index(op.f('ix_legal_case_favorites_case_id'),
                    'legal_case_favorites', ['case_id'], unique=False)
    op.create_index('uq_legal_case_favorite', 'legal_case_favorites',
                    ['user_id', 'case_id'], unique=True)
