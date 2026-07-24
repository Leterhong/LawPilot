"""灌入法律搜索引擎真实法条数据（Law Search 模块）。

数据来源：``sample_data/`` 下所有 ``laws*.jsonl``（主库 ``laws.jsonl`` +
各类补充库 ``laws_supplement*.jsonl``），按文件名排序依次入库。
所有文本均为逐字原文，来自全国人大 / 国务院 / 最高法 / 住建部等权威出处，
不含有任何演示 / 占位 / 虚构解读。

新增法律只需往 ``sample_data/`` 丢一个 ``laws_supplementN.jsonl`` 并重跑本脚本，
:func:`app.services.law_sync_service.upsert_laws_from_jsonl` 按
``(law_name, article)`` 幂等去重，已存在则更新正文/关键词，便于持续补全。

运行：cd backend && python scripts/seed_laws.py
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from app.core.database import AsyncSessionLocal
from app.services.law_sync_service import upsert_laws_from_jsonl

ROOT = Path(__file__).resolve().parent.parent / "sample_data"
# 主库优先，补充库按文件名排序依次入库
FILES = sorted(ROOT.glob("laws*.jsonl"))


async def main() -> None:
    async with AsyncSessionLocal() as session:
        total_added = total_updated = 0
        for path in FILES:
            if not path.exists():
                continue
            added, updated = await upsert_laws_from_jsonl(session, path)
            total_added += added
            total_updated += updated
            print(f"  {path.name}: added={added}, updated={updated}")
        print(
            f"law seed done: added={total_added}, updated={total_updated} "
            f"(from {len(FILES)} files)."
        )


if __name__ == "__main__":
    asyncio.run(main())
