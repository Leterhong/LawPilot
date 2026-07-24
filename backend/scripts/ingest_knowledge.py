#!/usr/bin/env python
"""知识库入库脚本（CLI）。

将 JSONL 数据集分发入库：按每行的 ``type`` 字段，分别写入 legal_reference
（法律条文）或 knowledge（知识条目），并调用 Embedding 服务生成向量。

用法：
    python scripts/ingest_knowledge.py                      # 默认 sample_data/legal_seed.jsonl
    python scripts/ingest_knowledge.py path/to/data.jsonl   # 指定文件

前置条件：
    - 已配置 .env 的 DATABASE_URL 与 EMBEDDING_*（BGE-M3）
    - 数据库已建表（表结构含 pgvector 扩展）
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# 将 backend/ 加入 sys.path，使脚本可直接运行
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.services.rag.ingest import (  # noqa: E402
    ingest_knowledge,
    ingest_legal_references,
)


async def run(path: str) -> None:
    items: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[跳过] 第{line_no}行 JSON 解析失败: {e}")

    refs = [it for it in items if it.get("type") == "legal_reference"]
    know = [it for it in items if it.get("type") == "knowledge"]
    skipped = len(items) - len(refs) - len(know)
    if skipped:
        print(f"[警告] 有 {skipped} 条缺少合法 type（应为 legal_reference/knowledge），已跳过")

    async with AsyncSessionLocal() as session:
        if refs:
            n = await ingest_legal_references(session, refs)
            print(f"[完成] 入库法律条文 {n} 条")
        if know:
            n = await ingest_knowledge(session, know)
            print(f"[完成] 入库知识条目 {n} 条")
    print("[完成] 全部入库完成")


def main() -> None:
    parser = argparse.ArgumentParser(description="LawPilot 知识库入库")
    parser.add_argument(
        "path",
        nargs="?",
        default="sample_data/legal_seed.jsonl",
        help="JSONL 数据路径（默认 sample_data/legal_seed.jsonl）",
    )
    args = parser.parse_args()

    p = Path(args.path)
    if not p.is_absolute():
        p = BACKEND_ROOT / p
    if not p.exists():
        print(f"[错误] 文件不存在: {p}")
        sys.exit(1)

    asyncio.run(run(str(p)))


if __name__ == "__main__":
    main()
