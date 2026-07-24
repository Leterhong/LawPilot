"""案例搜索真实数据灌库（Legal Case Search 模块）。

数据来源：``sample_data/legal_cases.jsonl``（以最高人民法院指导案例为主，真实、公开，
来源标注为「最高人民法院指导案例」）。

通过 :func:`app.services.case_sync_service.upsert_cases_from_jsonl` 幂等入库，按
``case_number`` 去重。

注意：早期版本曾灌入 8 条「真实风格」的合成文书（来源=中国裁判文书网），并非真实文书。
本脚本在入库真实指导案例前，先清除这些合成数据，避免虚构文书污染检索结果。

运行：cd backend && python scripts/seed_legal_cases.py
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.models.legal_case import LegalCase
from app.services.case_sync_service import upsert_cases_from_jsonl

SAMPLE = Path(__file__).resolve().parent.parent / "sample_data" / "legal_cases.jsonl"

# 早期合成示例的标识，入库前清除，避免虚构文书留存。
SYNTHETIC_SOURCE = "中国裁判文书网"


async def main() -> None:
    async with AsyncSessionLocal() as session:
        # 1) 清除历史合成示例（真实指导案例的来源为「最高人民法院指导案例」，不受影响）
        removed = (
            await session.execute(
                select(LegalCase.id).where(LegalCase.source == SYNTHETIC_SOURCE)
            )
        ).scalars().all()
        if removed:
            await session.execute(
                delete(LegalCase).where(LegalCase.source == SYNTHETIC_SOURCE)
            )
            await session.commit()
            print(f"cleared {len(removed)} synthetic demo case(s).")

        # 2) 幂等入库真实指导案例
        added, updated = await upsert_cases_from_jsonl(session, SAMPLE)
        print(
            f"case seed done: added={added}, updated={updated} "
            f"(from {SAMPLE.name})."
        )


if __name__ == "__main__":
    asyncio.run(main())
