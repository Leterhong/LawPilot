"""为 law / legal_cases 补算语义向量（embedding）。

仅当已配置真实 Embedding 密钥（AI 能力中心或 settings.embedding_api_key）时可用。
未配置时直接退出并提示，不写入任何数据（避免生成全零向量污染语义检索）。

运行：cd backend && python scripts/backfill_embeddings.py [--only law|cases]
"""
from __future__ import annotations

import asyncio
import argparse

from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.models.law import Law
from app.models.legal_case import LegalCase
from app.services.rag.embedder import EmbeddingService

_BATCH = 32


async def backfill(session, model, model_cls, text_of) -> int:
    svc = EmbeddingService(db=session, feature="embedding")
    if not await svc.available_async():
        print(f"[{model_cls.__tablename__}] 未配置真实 Embedding 密钥，跳过。")
        return 0
    rows = (
        await session.execute(select(model_cls).where(model_cls.embedding.is_(None)))
    ).scalars().all()
    total = len(rows)
    print(f"[{model_cls.__tablename__}] 需补算 {total} 条。")
    done = 0
    for i in range(0, total, _BATCH):
        chunk = rows[i : i + _BATCH]
        texts = [text_of(r) for r in chunk]
        try:
            vecs = await svc.embed_batch(texts)
        except Exception as e:  # 网络 / 配额错误，停止以免半截写入
            print(f"[{model_cls.__tablename__}] 编码失败：{e}")
            break
        for r, v in zip(chunk, vecs):
            r.embedding = v
        await session.commit()
        done += len(chunk)
        print(f"  ...{min(i + _BATCH, total)}/{total}")
    return done


def _law_text(r: Law) -> str:
    return " ".join(
        x for x in (r.law_name, r.chapter, r.section, r.article, r.content) if x
    )


def _case_text(r: LegalCase) -> str:
    return " ".join(
        x
        for x in (r.title, r.cause_of_action, r.facts, r.court_reasoning, r.judgement)
        if x
    )


async def main(only: str | None) -> None:
    async with AsyncSessionLocal() as session:
        if only in (None, "law"):
            await backfill(session, Law, Law, _law_text)
        if only in (None, "cases"):
            await backfill(session, LegalCase, LegalCase, _case_text)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["law", "cases"], default=None)
    args = ap.parse_args()
    asyncio.run(main(args.only))
