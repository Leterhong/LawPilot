"""add_ai_playground

修订标识: a1b2c3d4e5f6
前序修订: b33c546c6868

仅新增 9 张 AI Playground 表（playground_sessions / model_comparisons /
evaluation_datasets / evaluation_items / evaluation_tasks / evaluation_results /
prompt_library / model_pricing / playground_publishes）。
严格裁剪，不触碰任何已有表/列（复用 ai_models / providers / routing_rules / users）。
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = 'b33c546c6868'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('playground_sessions',
        sa.Column('user_id', sa.Uuid(), nullable=True, comment='匿名/系统为 NULL'),
        sa.Column('type', sa.String(length=24), nullable=False, comment='single/compare/prompt/evaluate/routing'),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('model_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='选中模型 id 列表'),
        sa.Column('feature', sa.String(length=64), nullable=True, comment='关联 routing_rules.feature'),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('user_prompt', sa.Text(), nullable=True),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('files', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='上传文件元信息'),
        sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='{temperature, top_p, max_tokens, streaming}'),
        sa.Column('input', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='完整输入快照'),
        sa.Column('output', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='主结果摘要'),
        sa.Column('score', sa.Float(), nullable=True, comment='自动评分总分'),
        sa.Column('score_detail', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='各维度评分'),
        sa.Column('token_usage', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='{in, out, total, cost}'),
        sa.Column('latency_ms', sa.Integer(), nullable=False, server_default=sa.text('0'), comment='端到端耗时'),
        sa.Column('status', sa.String(length=16), nullable=False, server_default=sa.text("'success'"), comment='success/error/timeout/partial'),
        sa.Column('error_text', sa.Text(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('model_comparisons',
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('model_id', sa.Uuid(), nullable=True),
        sa.Column('model_name', sa.String(length=128), nullable=True, comment='冗余缓存显示名'),
        sa.Column('provider_id', sa.Uuid(), nullable=True),
        sa.Column('provider_name', sa.String(length=128), nullable=True),
        sa.Column('response', sa.Text(), nullable=True),
        sa.Column('tokens_in', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('tokens_out', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('cost', sa.Numeric(precision=14, scale=6), nullable=False, server_default=sa.text('0')),
        sa.Column('latency_ms', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('score_detail', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False, server_default=sa.text("'success'")),
        sa.Column('error_text', sa.Text(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
        sa.ForeignKeyConstraint(['model_id'], ['ai_models.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['session_id'], ['playground_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_model_comparisons_session_id', 'model_comparisons', ['session_id'])
    op.create_table('evaluation_datasets',
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=True, comment='关联 AI_FEATURES'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('item_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('evaluation_items',
        sa.Column('dataset_id', sa.Uuid(), nullable=False),
        sa.Column('input', sa.Text(), nullable=False),
        sa.Column('expected', sa.Text(), nullable=True, comment='期望答案/参考答案'),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
        sa.ForeignKeyConstraint(['dataset_id'], ['evaluation_datasets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_evaluation_items_dataset_id', 'evaluation_items', ['dataset_id'])
    op.create_table('evaluation_tasks',
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('dataset_id', sa.Uuid(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('model_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='被测模型 id 列表'),
        sa.Column('judge_model_id', sa.Uuid(), nullable=True, comment='LLM Judge 评分模型'),
        sa.Column('feature', sa.String(length=64), nullable=True),
        sa.Column('prompt_template_key', sa.String(length=64), nullable=True),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='{temperature, top_p, max_tokens}'),
        sa.Column('status', sa.String(length=16), nullable=False, server_default=sa.text("'pending'"), comment='pending/running/done/error/partial'),
        sa.Column('total_items', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('processed_items', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('score_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='聚合指标'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['dataset_id'], ['evaluation_datasets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['judge_model_id'], ['ai_models.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('evaluation_results',
        sa.Column('task_id', sa.Uuid(), nullable=False),
        sa.Column('item_id', sa.Uuid(), nullable=True),
        sa.Column('model_id', sa.Uuid(), nullable=True),
        sa.Column('input', sa.Text(), nullable=True),
        sa.Column('expected', sa.Text(), nullable=True),
        sa.Column('output', sa.Text(), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=True),
        sa.Column('is_json_valid', sa.Boolean(), nullable=True),
        sa.Column('has_hallucination', sa.Boolean(), nullable=True),
        sa.Column('score', sa.Float(), nullable=True, comment='judge 评分 0-100'),
        sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('tokens_in', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('tokens_out', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('cost', sa.Numeric(precision=14, scale=6), nullable=False, server_default=sa.text('0')),
        sa.Column('error_text', sa.Text(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
        sa.ForeignKeyConstraint(['item_id'], ['evaluation_items.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['model_id'], ['ai_models.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['task_id'], ['evaluation_tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_evaluation_results_task_id', 'evaluation_results', ['task_id'])
    op.create_table('prompt_library',
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=False, comment='完整 prompt，支持 {{var}}'),
        sa.Column('variables', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='[{name, default, desc}]'),
        sa.Column('score', sa.Float(), nullable=True, comment='历史最佳得分'),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('model_pricing',
        sa.Column('model_id', sa.Uuid(), nullable=False),
        sa.Column('price_in_per_1k', sa.Numeric(precision=10, scale=6), nullable=False, server_default=sa.text('0'), comment='输入单价（每 1k token）'),
        sa.Column('price_out_per_1k', sa.Numeric(precision=10, scale=6), nullable=False, server_default=sa.text('0'), comment='输出单价（每 1k token）'),
        sa.Column('currency', sa.String(length=8), nullable=False, server_default=sa.text("'USD'")),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
        sa.ForeignKeyConstraint(['model_id'], ['ai_models.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('model_id')
    )
    op.create_table('playground_publishes',
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('session_id', sa.Uuid(), nullable=True),
        sa.Column('feature', sa.String(length=64), nullable=False, comment='被改写的 routing feature'),
        sa.Column('from_model_id', sa.Uuid(), nullable=True),
        sa.Column('to_model_id', sa.Uuid(), nullable=True),
        sa.Column('routing_rule_id', sa.Uuid(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
        sa.ForeignKeyConstraint(['from_model_id'], ['ai_models.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['routing_rule_id'], ['routing_rules.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['session_id'], ['playground_sessions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['to_model_id'], ['ai_models.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('playground_publishes')
    op.drop_table('model_pricing')
    op.drop_table('prompt_library')
    op.drop_index('ix_evaluation_results_task_id', table_name='evaluation_results')
    op.drop_table('evaluation_results')
    op.drop_table('evaluation_tasks')
    op.drop_index('ix_evaluation_items_dataset_id', table_name='evaluation_items')
    op.drop_table('evaluation_items')
    op.drop_table('evaluation_datasets')
    op.drop_index('ix_model_comparisons_session_id', table_name='model_comparisons')
    op.drop_table('model_comparisons')
    op.drop_table('playground_sessions')
