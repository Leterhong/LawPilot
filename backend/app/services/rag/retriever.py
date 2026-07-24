"""混合检索器（Hybrid Retriever）。

将「向量语义检索」与「关键词检索」融合，形成兼顾语义与字面匹配的结果。

流水线：
1. 向量检索：对 legal_reference / knowledge 两表做 pgvector 余弦相似度检索，
   仅对 embedding 非空记录生效。
2. 关键词检索：对 title / content / article 做 ILIKE 模糊匹配（大小写不敏感）。
3. 融合：采用互逆排名融合（Reciprocal Rank Fusion, RRF），将多路排序结果
   合并为单一得分，无需各路得分量纲一致。
4. 重排：可选调用 RerankerService 做精排（远程或词法降级）。

容错：当 Embedding 服务不可用时，自动退化为纯关键词检索，并标记
``used_hybrid=False``，保证基本可用性。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import or_, select

from app.core.config import settings
from app.models.enums import LegalSourceEnum
from app.models.knowledge import Knowledge
from app.models.legal_reference import LegalReference
from app.services.rag.embedder import EmbeddingService
from app.services.rag.reranker import RerankerService
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class RetrievedChunk:
    """检索结果的最小单元，可追溯来源表与原文。"""

    id: UUID
    source_table: str  # "legal_reference" | "knowledge"
    source: LegalSourceEnum
    title: str
    content: str
    article: Optional[str] = None
    score: float = 0.0  # 融合/重排后的最终得分（0-1 区间附近）
    vector_score: Optional[float] = None  # 余弦相似度（1 - 距离）
    keyword_score: Optional[float] = None  # 关键词命中标记（命中=1.0）
    citation: str = ""

    def to_snippet(self, length: int = 160) -> str:
        """截断为正文摘要，用于报告与前端展示。"""
        text = self.content or ""
        return text if len(text) <= length else text[:length] + "…"


def _cite_from_ref(ref: LegalReference) -> str:
    """由法律条文构造引用标签，如「《民法典》 第577条」。"""
    parts: List[str] = []
    if ref.title:
        parts.append(ref.title)
    if ref.article:
        parts.append(ref.article)
    if ref.source == LegalSourceEnum.LOCAL_REGULATION and ref.jurisdiction:
        parts.append(f"（{ref.jurisdiction}）")
    return " ".join(parts) or "法律条文"


def _cite_from_knowledge(k: Knowledge) -> str:
    return k.title or "知识条目"


class HybridRetriever:
    """混合检索器。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.embedder = EmbeddingService(db=self.session, feature="embedding")
        self.reranker = RerankerService()

    async def search(
        self,
        query: str,
        *,
        source: Optional[LegalSourceEnum] = None,
        top_k: Optional[int] = None,
        use_rerank: bool = True,
    ) -> Tuple[List[RetrievedChunk], bool, bool]:
        """执行混合检索。

        :param query: 用户查询
        :param source: 限定法律渊源（可选）
        :param top_k: 返回条数（默认 settings.rerank_top_k）
        :param use_rerank: 是否进行重排
        :return: (有序结果列表, 是否启用向量检索, 是否启用重排)
        """
        top_k = top_k or settings.rerank_top_k
        used_hybrid = False

        # 1) 向量检索（需要先取得查询向量）
        qvec: Optional[List[float]] = None
        try:
            qvec = await self.embedder.embed_query(query)
            used_hybrid = True
        except Exception:
            qvec = None  # 嵌入失败 → 退化为纯关键词检索

        ref_vec: List[RetrievedChunk] = []
        know_vec: List[RetrievedChunk] = []
        if qvec is not None:
            ref_vec = await self._vector_search_legal(
                qvec, source, settings.vector_similarity_top_k
            )
            know_vec = await self._vector_search_knowledge(
                qvec, source, settings.vector_similarity_top_k
            )

        # 2) 关键词检索（始终执行，作为兜底与融合输入）
        ref_kw = await self._keyword_search_legal(query, source, settings.keyword_top_k)
        know_kw = await self._keyword_search_knowledge(
            query, source, settings.keyword_top_k
        )

        # 3) RRF 融合
        fused = self._rrf_fuse([ref_vec, know_vec, ref_kw, know_kw], k=60)

        # 4) 重排
        used_rerank = False
        if use_rerank and self.reranker.enabled and fused:
            fused = await self.reranker.rerank(query, fused)
            used_rerank = True

        return fused[:top_k], used_hybrid, used_rerank

    # ------------------------- 向量检索 -------------------------
    async def _vector_search_legal(
        self, qvec: List[float], source: Optional[LegalSourceEnum], limit: int
    ) -> List[RetrievedChunk]:
        sim = (1 - LegalReference.embedding.cosine_distance(qvec)).label("sim")
        stmt = select(LegalReference, sim).where(LegalReference.embedding.isnot(None))
        if source is not None:
            stmt = stmt.where(LegalReference.source == source)
        stmt = stmt.order_by(sim.desc()).limit(limit)
        rows = await self.session.execute(stmt)
        out: List[RetrievedChunk] = []
        for ref, sim_val in rows.all():
            out.append(
                RetrievedChunk(
                    id=ref.id,
                    source_table="legal_reference",
                    source=ref.source,
                    title=ref.title,
                    content=ref.content,
                    article=ref.article,
                    vector_score=float(sim_val) if sim_val is not None else None,
                    citation=_cite_from_ref(ref),
                )
            )
        return out

    async def _vector_search_knowledge(
        self, qvec: List[float], source: Optional[LegalSourceEnum], limit: int
    ) -> List[RetrievedChunk]:
        sim = (1 - Knowledge.embedding.cosine_distance(qvec)).label("sim")
        stmt = select(Knowledge, sim).where(Knowledge.embedding.isnot(None))
        if source is not None:
            stmt = stmt.where(Knowledge.category == source)
        stmt = stmt.order_by(sim.desc()).limit(limit)
        rows = await self.session.execute(stmt)
        out: List[RetrievedChunk] = []
        for k, sim_val in rows.all():
            out.append(
                RetrievedChunk(
                    id=k.id,
                    source_table="knowledge",
                    source=k.category,
                    title=k.title,
                    content=k.content,
                    article=None,
                    vector_score=float(sim_val) if sim_val is not None else None,
                    citation=_cite_from_knowledge(k),
                )
            )
        return out

    # ------------------------- 关键词检索 -------------------------
    async def _keyword_search_legal(
        self, query: str, source: Optional[LegalSourceEnum], limit: int
    ) -> List[RetrievedChunk]:
        pattern = f"%{query}%"
        stmt = select(LegalReference).where(
            or_(
                LegalReference.title.ilike(pattern),
                LegalReference.content.ilike(pattern),
                LegalReference.article.ilike(pattern),
            )
        )
        if source is not None:
            stmt = stmt.where(LegalReference.source == source)
        stmt = stmt.order_by(LegalReference.source).limit(limit)
        rows = await self.session.execute(stmt)
        out: List[RetrievedChunk] = []
        for ref in rows.scalars().all():
            out.append(
                RetrievedChunk(
                    id=ref.id,
                    source_table="legal_reference",
                    source=ref.source,
                    title=ref.title,
                    content=ref.content,
                    article=ref.article,
                    keyword_score=1.0,
                    citation=_cite_from_ref(ref),
                )
            )
        return out

    async def _keyword_search_knowledge(
        self, query: str, source: Optional[LegalSourceEnum], limit: int
    ) -> List[RetrievedChunk]:
        pattern = f"%{query}%"
        stmt = select(Knowledge).where(
            or_(
                Knowledge.title.ilike(pattern),
                Knowledge.content.ilike(pattern),
            )
        )
        if source is not None:
            stmt = stmt.where(Knowledge.category == source)
        stmt = stmt.limit(limit)
        rows = await self.session.execute(stmt)
        out: List[RetrievedChunk] = []
        for k in rows.scalars().all():
            out.append(
                RetrievedChunk(
                    id=k.id,
                    source_table="knowledge",
                    source=k.category,
                    title=k.title,
                    content=k.content,
                    article=None,
                    keyword_score=1.0,
                    citation=_cite_from_knowledge(k),
                )
            )
        return out

    # ------------------------- 融合 -------------------------
    @staticmethod
    def _rrf_fuse(
        lists: List[List[RetrievedChunk]], k: int = 60
    ) -> List[RetrievedChunk]:
        """互逆排名融合（RRF）。

        score = Σ 1/(k + rank_i)。相同 (表, id) 的候选得分累加，
        并保留两路中最优的向量/关键词分。
        """
        fused: dict[tuple, RetrievedChunk] = {}
        for lst in lists:
            for rank, chunk in enumerate(lst, start=1):
                key = (chunk.source_table, chunk.id)
                rrf = 1.0 / (k + rank)
                existing = fused.get(key)
                if existing is None:
                    chunk.score = rrf
                    fused[key] = chunk
                else:
                    existing.score += rrf
                    if chunk.vector_score is not None:
                        existing.vector_score = (
                            chunk.vector_score
                            if existing.vector_score is None
                            else max(existing.vector_score, chunk.vector_score)
                        )
                    if chunk.keyword_score is not None:
                        existing.keyword_score = (
                            chunk.keyword_score
                            if existing.keyword_score is None
                            else max(existing.keyword_score, chunk.keyword_score)
                        )
        result = list(fused.values())
        result.sort(key=lambda c: c.score, reverse=True)
        return result
