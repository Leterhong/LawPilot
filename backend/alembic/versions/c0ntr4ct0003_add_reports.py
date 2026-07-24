"""add contract_reports table

Step5（报告生成）落地：新增 contract_reports 表，用于存放合同审查报告
（Markdown 正文 + 结构化 JSON）。

仅 create_table，零 ALTER 任何已有表；外键引用 contracts / users / ai_models
均 CASCADE / SET NULL，符合「不修改已有业务」原则。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c0ntr4ct0003"
down_revision: str | None = "c0ntr4ct0002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "contract_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("contract_id", sa.UUID(), nullable=False),
        sa.Column("report_type", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("generated_by", sa.UUID(), nullable=True),
        sa.Column("model_id", sa.UUID(), nullable=True),
        sa.Column("file_path", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(
            ["contract_id"], ["contracts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["generated_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["model_id"], ["ai_models.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contract_reports_id", "contract_reports", ["id"], unique=False)
    op.create_index("ix_contract_reports_contract_id", "contract_reports", ["contract_id"], unique=False)
    op.create_index("ix_contract_reports_report_type", "contract_reports", ["report_type"], unique=False)
    op.create_index(
        "ix_contract_reports_ct_rt", "contract_reports", ["contract_id", "report_type"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_contract_reports_ct_rt", table_name="contract_reports")
    op.drop_index("ix_contract_reports_report_type", table_name="contract_reports")
    op.drop_index("ix_contract_reports_contract_id", table_name="contract_reports")
    op.drop_index("ix_contract_reports_id", table_name="contract_reports")
    op.drop_table("contract_reports")
