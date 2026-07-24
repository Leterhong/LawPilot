"""add_contracts_table

修订标识: c0ntr4ct0001
前序修订: a1b2c3d4e5f6

仅新增 **contracts** 表（合同智能中心 Step2 落地）。严格裁剪，不触碰任何已有
表/列；复用 users / ai_models（FK 均 SET NULL）。后续子表在各自步骤迁移中新增。
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c0ntr4ct0001'
down_revision: str | None = 'a1b2c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'contracts',
        sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
        sa.Column('user_id', sa.Uuid(), nullable=True, comment='归属用户；系统/匿名上传为 NULL'),
        sa.Column('title', sa.String(length=255), nullable=True, comment='合同标题（默认文件名）'),
        sa.Column('contract_type', sa.String(length=32), nullable=True, comment='AI 自动分类，见 CONTRACT_TYPES'),
        sa.Column('status', sa.String(length=24), nullable=False, server_default=sa.text("'uploaded'"), comment='uploaded/parsing/analyzed/error'),
        sa.Column('file_path', sa.String(length=512), nullable=True, comment='原文存储路径（upload_dir）'),
        sa.Column('storage_key', sa.String(length=255), nullable=True, comment='对象存储 key（若启用对象存储）'),
        sa.Column('file_type', sa.String(length=16), nullable=True, comment='pdf/docx/txt/md/png/jpg'),
        sa.Column('file_size', sa.Integer(), nullable=True, comment='字节'),
        sa.Column('full_text', sa.Text(), nullable=True, comment='解析后的纯文本全文'),
        sa.Column('ocr_text', sa.Text(), nullable=True, comment='OCR 原始文本（图片/扫描件）'),
        sa.Column('language', sa.String(length=8), nullable=False, server_default=sa.text("'zh'")),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True, comment='① 一句话合同摘要'),
        sa.Column('law_involved', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='③ 涉及法律'),
        sa.Column('risk_score', sa.Integer(), nullable=False, server_default=sa.text('0'), comment='⑤ 风险总分 0-100'),
        sa.Column('risk_level', sa.String(length=16), nullable=False, server_default=sa.text("'low'"), comment='low/medium/high'),
        sa.Column('risk_clauses', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='⑤ 高风险条款摘要缓存'),
        sa.Column('king_clauses', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='⑥ 霸王条款检测'),
        sa.Column('payment_risk', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='⑦ 付款风险'),
        sa.Column('breach_risk', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='⑧ 违约风险'),
        sa.Column('liability_risk', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='⑨ 赔偿责任'),
        sa.Column('model_id', sa.Uuid(), nullable=True, comment='主分析模型（冗余显示）'),
        sa.Column('analysis_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='{summary_model, review_model, legal_model, latency_ms}'),
        sa.Column('token_usage', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='{in, out, total, cost, currency}'),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('checklist', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='[{item, checked, category}]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['model_id'], ['ai_models.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_contracts_user_id', 'contracts', ['user_id'])
    op.create_index('ix_contracts_contract_type', 'contracts', ['contract_type'])
    op.create_index('ix_contracts_risk_level', 'contracts', ['risk_level'])
    op.create_index('ix_contracts_created_at', 'contracts', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_contracts_created_at', table_name='contracts')
    op.drop_index('ix_contracts_risk_level', table_name='contracts')
    op.drop_index('ix_contracts_contract_type', table_name='contracts')
    op.drop_index('ix_contracts_user_id', table_name='contracts')
    op.drop_table('contracts')
