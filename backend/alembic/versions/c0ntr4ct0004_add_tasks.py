"""add contract_tasks table

Step6（提醒中心）落地：新增 contract_tasks 表，用于存放合同相关的提醒与签署前
检查项（到期 / 付款 / 续签 / 签署检查等）。

仅 create_table，零 ALTER 任何已有表；外键引用 contracts（CASCADE）/ users（SET NULL）
符合「不修改已有业务」原则。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c0ntr4ct0004"
down_revision: str | None = "c0ntr4ct0003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "contract_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("contract_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=16), server_default=sa.text("'reminder'"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("remind_before_days", sa.Integer(), server_default=sa.text("7"), nullable=False),
        sa.Column("done", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("priority", sa.String(length=16), server_default=sa.text("'normal'"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["contract_id"], ["contracts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contract_tasks_id", "contract_tasks", ["id"], unique=False)
    op.create_index("ix_contract_tasks_contract_id", "contract_tasks", ["contract_id"], unique=False)
    op.create_index("ix_contract_tasks_type", "contract_tasks", ["type"], unique=False)
    op.create_index("ix_contract_tasks_category", "contract_tasks", ["category"], unique=False)
    op.create_index("ix_contract_tasks_done", "contract_tasks", ["done"], unique=False)
    op.create_index("ix_contract_tasks_due_done", "contract_tasks", ["due_date", "done"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_contract_tasks_due_done", table_name="contract_tasks")
    op.drop_index("ix_contract_tasks_done", table_name="contract_tasks")
    op.drop_index("ix_contract_tasks_category", table_name="contract_tasks")
    op.drop_index("ix_contract_tasks_type", table_name="contract_tasks")
    op.drop_index("ix_contract_tasks_contract_id", table_name="contract_tasks")
    op.drop_index("ix_contract_tasks_id", table_name="contract_tasks")
    op.drop_table("contract_tasks")
