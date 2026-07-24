"""add_ai_capability_center

修订标识: b33c546c6868
前序修订: 40d255680eb5

仅新增 8 张 AI 能力中心表 + users.is_superuser 增量列。
严格裁剪自动生成中的既有表漂移（Enum/索引/注释），不影响任何已有模块。
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b33c546c6868'
down_revision: str | None = '40d255680eb5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('providers',
    sa.Column('name', sa.String(length=128), nullable=False, comment='显示名（硅基流动 / OpenRouter…）'),
    sa.Column('type', sa.String(length=48), nullable=False, comment='Provider 类型，决定 AIManager 客户端构建方式'),
    sa.Column('base_url', sa.String(length=512), nullable=True, comment='OpenAI Compatible 端点'),
    sa.Column('api_key', sa.Text(), nullable=True, comment='加密存储的 API Key'),
    sa.Column('enabled', sa.Boolean(), nullable=False, comment='是否启用'),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('ai_models',
    sa.Column('name', sa.String(length=128), nullable=False, comment='显示名'),
    sa.Column('provider_id', sa.Uuid(), nullable=True, comment='关联 Provider（可空＝独立自定义模型）'),
    sa.Column('provider_type', sa.String(length=48), nullable=True, comment='冗余缓存，避免每次调用 join'),
    sa.Column('api_key', sa.Text(), nullable=True, comment='加密存储，可覆盖 Provider 的 key'),
    sa.Column('base_url', sa.String(length=512), nullable=True, comment='可覆盖 Provider 的 base_url'),
    sa.Column('model_name', sa.String(length=128), nullable=False, comment='实际发给 API 的模型 ID'),
    sa.Column('embedding_model', sa.String(length=128), nullable=True),
    sa.Column('vision_model', sa.String(length=128), nullable=True),
    sa.Column('reranker_model', sa.String(length=128), nullable=True),
    sa.Column('embedding_dim', sa.Integer(), nullable=True, comment='向量维度，默认 1024'),
    sa.Column('temperature', sa.Float(), nullable=False),
    sa.Column('top_p', sa.Float(), nullable=False),
    sa.Column('timeout', sa.Integer(), nullable=False, comment='秒'),
    sa.Column('max_tokens', sa.Integer(), nullable=True),
    sa.Column('is_default', sa.Boolean(), nullable=False, comment='全局默认（至多一个）'),
    sa.Column('is_enabled', sa.Boolean(), nullable=False),
    sa.Column('capabilities', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='能力开关'),
    sa.Column('advanced', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='高级配置（重试/并发/限流）'),
    sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
    sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('model_health',
    sa.Column('model_id', sa.Uuid(), nullable=False),
    sa.Column('provider_id', sa.Uuid(), nullable=True),
    sa.Column('last_checked', sa.DateTime(timezone=True), nullable=True),
    sa.Column('chat_ok', sa.Boolean(), nullable=True),
    sa.Column('vision_ok', sa.Boolean(), nullable=True),
    sa.Column('embedding_ok', sa.Boolean(), nullable=True),
    sa.Column('streaming_ok', sa.Boolean(), nullable=True),
    sa.Column('json_ok', sa.Boolean(), nullable=True),
    sa.Column('function_calling_ok', sa.Boolean(), nullable=True),
    sa.Column('web_ok', sa.Boolean(), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=True, comment='healthy/degraded/down'),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('error_text', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
    sa.ForeignKeyConstraint(['model_id'], ['ai_models.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_model_health_model_id'), 'model_health', ['model_id'], unique=False)
    op.create_table('model_logs',
    sa.Column('model_id', sa.Uuid(), nullable=True),
    sa.Column('provider_id', sa.Uuid(), nullable=True),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('feature', sa.String(length=64), nullable=True),
    sa.Column('endpoint', sa.String(length=128), nullable=True),
    sa.Column('capability', sa.String(length=32), nullable=True),
    sa.Column('request_text', sa.Text(), nullable=True),
    sa.Column('response_text', sa.Text(), nullable=True),
    sa.Column('tokens_in', sa.Integer(), nullable=False),
    sa.Column('tokens_out', sa.Integer(), nullable=False),
    sa.Column('cost', sa.Numeric(precision=14, scale=6), nullable=False),
    sa.Column('latency_ms', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('error_text', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
    sa.ForeignKeyConstraint(['model_id'], ['ai_models.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_model_logs_created_at'), 'model_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_model_logs_feature'), 'model_logs', ['feature'], unique=False)
    op.create_index(op.f('ix_model_logs_model_id'), 'model_logs', ['model_id'], unique=False)
    op.create_index(op.f('ix_model_logs_user_id'), 'model_logs', ['user_id'], unique=False)
    op.create_table('model_usage',
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('model_id', sa.Uuid(), nullable=True),
    sa.Column('provider_id', sa.Uuid(), nullable=True),
    sa.Column('user_id', sa.Uuid(), nullable=True, comment='系统调用为 NULL'),
    sa.Column('tokens_in', sa.Integer(), nullable=False),
    sa.Column('tokens_out', sa.Integer(), nullable=False),
    sa.Column('cost', sa.Numeric(precision=14, scale=6), nullable=False),
    sa.Column('cost_currency', sa.String(length=8), nullable=False),
    sa.Column('calls', sa.Integer(), nullable=False),
    sa.Column('failures', sa.Integer(), nullable=False),
    sa.Column('avg_latency_ms', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
    sa.ForeignKeyConstraint(['model_id'], ['ai_models.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('prompt_templates',
    sa.Column('key', sa.String(length=64), nullable=False, comment='功能 key'),
    sa.Column('name', sa.String(length=128), nullable=False, comment='显示名'),
    sa.Column('content', sa.Text(), nullable=False, comment='模板体，支持 {{variable}} 占位'),
    sa.Column('variables', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='变量定义列表'),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('current_version', sa.Integer(), nullable=False),
    sa.Column('model_id', sa.Uuid(), nullable=True, comment='可选：固定绑定某模型'),
    sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
    sa.ForeignKeyConstraint(['model_id'], ['ai_models.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key')
    )
    op.create_table('routing_rules',
    sa.Column('feature', sa.String(length=64), nullable=False, comment='AI 功能 key（见 AI_FEATURES）'),
    sa.Column('model_id', sa.Uuid(), nullable=False),
    sa.Column('fallback_model_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='有序 fallback 链（UUID 列表）'),
    sa.Column('strategy', sa.String(length=24), nullable=False, comment='lowest_cost/fastest/highest_quality/balanced/custom'),
    sa.Column('auto_route', sa.Boolean(), nullable=False, comment='true=按策略+任务类型自动选模型'),
    sa.Column('prompt_template_key', sa.String(length=64), nullable=True, comment='关联 prompt_templates.key；空=内置默认'),
    sa.Column('priority', sa.Integer(), nullable=False, comment='拖拽排序用'),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
    sa.ForeignKeyConstraint(['model_id'], ['ai_models.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('feature')
    )
    op.create_table('prompt_versions',
    sa.Column('template_id', sa.Uuid(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('variables', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('note', sa.String(length=255), nullable=True, comment='变更说明'),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False, comment='全局唯一主键'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间（UTC）'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间（UTC）'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['template_id'], ['prompt_templates.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prompt_versions_template_id'), 'prompt_versions', ['template_id'], unique=False)
    op.add_column('users', sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default=sa.text('false'), comment='是否超级管理员（AI 能力中心后台访问权限）'))


def downgrade() -> None:
    op.drop_column('users', 'is_superuser')
    op.drop_index(op.f('ix_prompt_versions_template_id'), table_name='prompt_versions')
    op.drop_table('prompt_versions')
    op.drop_table('routing_rules')
    op.drop_table('prompt_templates')
    op.drop_table('model_usage')
    op.drop_index(op.f('ix_model_logs_user_id'), table_name='model_logs')
    op.drop_index(op.f('ix_model_logs_model_id'), table_name='model_logs')
    op.drop_index(op.f('ix_model_logs_feature'), table_name='model_logs')
    op.drop_index(op.f('ix_model_logs_created_at'), table_name='model_logs')
    op.drop_table('model_logs')
    op.drop_index(op.f('ix_model_health_model_id'), table_name='model_health')
    op.drop_table('model_health')
    op.drop_table('ai_models')
    op.drop_table('providers')
