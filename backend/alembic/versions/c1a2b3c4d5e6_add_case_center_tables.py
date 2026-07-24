"""add case center tables

仅新建 Case Center 模块所需的 7 张表（case_center / case_analysis / case_evidence /
case_documents / case_tasks / case_timeline / case_notes），不改动任何已有业务表，
确保不影响 Phase 1/2 功能与 Law Search 模块。

建表严格以 app/models 元数据为单一可信来源（仅传入这 7 个表），枚举字段沿用
``native_enum=False``（VARCHAR 存储），因此无需 DROP TYPE。
"""
from collections.abc import Sequence

from alembic import op

from app.core.database import Base
from app.models.case_center import (
    CaseAnalysis,
    CaseCenter,
    CaseDocument,
    CaseEvidence,
    CaseNote,
    CaseTask,
    CaseTimeline,
)

revision: str = 'c1a2b3c4d5e6'
down_revision: str | None = '44937a9ecb99'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TABLES = [
    CaseAnalysis.__table__,
    CaseEvidence.__table__,
    CaseDocument.__table__,
    CaseTask.__table__,
    CaseTimeline.__table__,
    CaseNote.__table__,
    CaseCenter.__table__,
]


def upgrade() -> None:
    bind = op.get_bind()
    # 仅创建这 7 张新表（已存在的表会被 create_all 自动跳过）
    Base.metadata.create_all(bind=bind, tables=_NEW_TABLES)


def downgrade() -> None:
    bind = op.get_bind()
    # 删除顺序由 drop_all 依据外键依赖自动处理（先子后父）
    Base.metadata.drop_all(bind=bind, tables=_NEW_TABLES)
