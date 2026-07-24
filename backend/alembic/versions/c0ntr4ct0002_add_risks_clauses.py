"""add_contract_risks_clauses

修订标识: c0ntr4ct0002
前序修订: c0ntr4ct0001

仅新增 **contract_risks** 与 **contract_clauses** 两张子表（合同智能中心 Step3
AI 分析落地）。严格裁剪，不触碰任何已有表/列；外键均 CASCADE 到 contracts。
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c0ntr4ct0002'
down_revision: str | None = 'c0ntr4ct0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'contract_risks',
        sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
        sa.Column('contract_id', sa.Uuid(), nullable=False, comment='关联合同（级联删除）'),
        sa.Column('clause_ref', sa.String(length=32), nullable=True, comment='条款引用，如『第8条』'),
        sa.Column('clause_text', sa.Text(), nullable=True, comment='风险条款原文'),
        sa.Column('category', sa.String(length=32), nullable=False, comment='风险分类，见 CONTRACT_RISK_CATEGORIES'),
        sa.Column('risk_level', sa.String(length=16), nullable=False, server_default=sa.text("'medium'"), comment='low/medium/high'),
        sa.Column('score', sa.Integer(), nullable=False, server_default=sa.text('0'), comment='该条款风险分 0-100'),
        sa.Column('reason', sa.Text(), nullable=True, comment='风险原因'),
        sa.Column('suggestion', sa.Text(), nullable=True, comment='修改建议'),
        sa.Column('suggested_text', sa.Text(), nullable=True, comment='推荐修改版本'),
        sa.Column('king_clause', sa.Boolean(), nullable=False, server_default=sa.text('false'), comment='是否霸王条款'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
        sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_contract_risks_contract_id', 'contract_risks', ['contract_id'])
    op.create_index('ix_contract_risks_category', 'contract_risks', ['category'])
    op.create_index('ix_contract_risks_risk_level', 'contract_risks', ['risk_level'])

    op.create_table(
        'contract_clauses',
        sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
        sa.Column('contract_id', sa.Uuid(), nullable=False, comment='关联合同（级联删除）'),
        sa.Column('clause_no', sa.String(length=32), nullable=True, comment='条款号，如『第8条』/『8.2』'),
        sa.Column('section', sa.String(length=64), nullable=True, comment='章节标题'),
        sa.Column('clause_text', sa.Text(), nullable=True, comment='条款原文'),
        sa.Column('category', sa.String(length=32), nullable=True, comment='关联风险分类（若已识别）'),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default=sa.text('0'), comment='条款顺序'),
        sa.Column('explanation', sa.Text(), nullable=True, comment='这一条是什么意思'),
        sa.Column('risk_level', sa.String(length=16), nullable=True, comment='low/medium/high'),
        sa.Column('risk_note', sa.Text(), nullable=True, comment='有什么风险'),
        sa.Column('suggested_version', sa.Text(), nullable=True, comment='推荐修改版本'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
        sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_contract_clauses_contract_id', 'contract_clauses', ['contract_id'])
    op.create_index('ix_contract_clauses_order', 'contract_clauses', ['contract_id', 'order_index'])


def downgrade() -> None:
    op.drop_index('ix_contract_clauses_order', table_name='contract_clauses')
    op.drop_index('ix_contract_clauses_contract_id', table_name='contract_clauses')
    op.drop_table('contract_clauses')
    op.drop_index('ix_contract_risks_risk_level', table_name='contract_risks')
    op.drop_index('ix_contract_risks_category', table_name='contract_risks')
    op.drop_index('ix_contract_risks_contract_id', table_name='contract_risks')
    op.drop_table('contract_risks')
