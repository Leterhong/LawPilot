"""知识入库服务（Ingestion）。

将外部法律条文 / 知识条目切分、向量化后写入数据库，供混合检索使用。
设计为可被 CLI 脚本、后台任务或管理接口复用的纯函数集合。

约定：
- legal_reference：默认整条入库（条文本身已较短）；过长可开启 chunk。
- knowledge：默认切块入库（知识正文通常较长），以获得更精准的片段检索。
- 所有写入即时 commit（批处理结束后统一提交一次）。
"""
from __future__ import annotations

from typing import List

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import LegalSourceEnum
from app.models.knowledge import Knowledge
from app.models.legal_reference import LegalReference
from app.services.rag.chunker import chunk_text
from app.services.rag.embedder import EmbeddingService

logger = logging.getLogger(__name__)

# 当 Embedding 服务不可用（无密钥 / 无网络）时降级为零向量，
# 保证知识库仍能灌入，检索退化为关键词匹配（混合检索器会融合关键词结果）。
_embedding_unavailable = False


async def _safe_embed(svc: "EmbeddingService", text: str) -> List[float]:
    """向量化文本；服务不可用时降级为零向量并仅告警一次。"""
    global _embedding_unavailable
    if _embedding_unavailable:
        return [0.0] * (settings.embedding_dim or 1024)
    try:
        return await svc.embed_doc(text)
    except Exception as exc:  # noqa: BLE001
        if not _embedding_unavailable:
            logger.warning(
                "Embedding 服务不可用（%s），知识库将以零向量灌入，检索降级为关键词匹配；"
                "请配置正确的 EMBEDDING_API_KEY 后重新运行本脚本刷新向量。",
                type(exc).__name__,
            )
        _embedding_unavailable = True
        return [0.0] * (settings.embedding_dim or 1024)


async def ingest_legal_references(
    session: AsyncSession, items: List[dict], chunk: bool = False
) -> int:
    """批量入库法律条文。

    :param items: 每条形如
        {source, title, article?, content, explanation?, jurisdiction?,
         effective_date?, extra?}
        source 必须为 LegalSourceEnum 的合法取值。
    :param chunk: content 过长是否切块后分别入库（默认整条入库）。
    :return: 实际写入记录数
    """
    svc = EmbeddingService()
    count = 0
    for it in items:
        source = LegalSourceEnum(it["source"])
        content = it["content"]
        pieces = chunk_text(content) if chunk else [content]
        for idx, piece in enumerate(pieces):
            title = it["title"] + (f"（{idx + 1}）" if len(pieces) > 1 else "")
            vec = await _safe_embed(svc, piece)
            session.add(
                LegalReference(
                    source=source,
                    title=title,
                    article=it.get("article"),
                    content=piece,
                    explanation=it.get("explanation"),
                    jurisdiction=it.get("jurisdiction"),
                    effective_date=it.get("effective_date"),
                    extra=it.get("extra"),
                    embedding=vec,
                )
            )
            count += 1
    await session.commit()
    return count


async def ingest_knowledge(
    session: AsyncSession, items: List[dict], chunk: bool = True
) -> int:
    """批量入库知识条目（办事指南 / 政策解读 / 流程说明 / 常见问答）。

    :param items: 每条形如
        {category, title, content, source_url?, tags?}
        category 必须为 LegalSourceEnum 的合法取值。
    :param chunk: 是否切块后入库（默认 True）。
    :return: 实际写入记录数
    """
    svc = EmbeddingService()
    count = 0
    for it in items:
        category = LegalSourceEnum(it["category"])
        content = it["content"]
        pieces = chunk_text(content) if chunk else [content]
        for idx, piece in enumerate(pieces):
            title = it["title"] + (f"（{idx + 1}）" if len(pieces) > 1 else "")
            vec = await _safe_embed(svc, piece)
            session.add(
                Knowledge(
                    category=category,
                    title=title,
                    content=piece,
                    source_url=it.get("source_url"),
                    tags=it.get("tags"),
                    embedding=vec,
                )
            )
            count += 1
    await session.commit()
    return count
