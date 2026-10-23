"""法律检索服务。

Phase 3 提供关键词/类型检索（keyword_search）；Phase 5 新增混合检索
（hybrid_search），整合 pgvector 语义检索 + 关键词检索 + Rerank + 引用来源。

对外契约保持一致：search() 仍返回 (refs, refs_total, know, know_total)，
便于未接入向量库时降级；新增 hybrid_search() 返回融合排序结果与引用元数据。
"""
from __future__ import annotations

from app.repositories.legal_repo import KnowledgeRepository, LegalReferenceRepository
from app.schemas.legal import LegalSearchQuery, RetrievedChunkOut
from app.services.rag.citations import build_citations
from app.services.rag.retriever import HybridRetriever


class LegalService:
    def __init__(self, session) -> None:
        self.refs = LegalReferenceRepository(session)
        self.knowledge = KnowledgeRepository(session)

    async def search(self, query: LegalSearchQuery):
        """关键词/类型检索（Phase 3，兼容接口）。"""
        refs, refs_total = await self.refs.search(
            query.q, query.source, query.limit, query.offset
        )
        know, know_total = await self.knowledge.search(
            query.q, query.source, query.limit, query.offset
        )
        return refs, refs_total, know, know_total

    async def hybrid_search(self, query: LegalSearchQuery):
        """混合检索：向量 + 关键词 → RRF 融合 → 可选重排。

        :return: (RetrievedChunkOut 列表, 引用元数据列表, used_hybrid, used_rerank)
        """
        retriever = HybridRetriever(self.refs.session)
        chunks, used_hybrid, used_rerank = await retriever.search(
            query.q,
            source=query.source,
            top_k=query.limit,
            use_rerank=query.use_rerank,
        )
        out = [
            RetrievedChunkOut(
                id=c.id,
                source_table=c.source_table,
                source=c.source,
                title=c.title,
                article=c.article,
                content=c.content,
                snippet=c.to_snippet(),
                score=round(c.score, 4),
                vector_score=c.vector_score,
                keyword_score=c.keyword_score,
                citation=c.citation,
            )
            for c in chunks
        ]
        citations = build_citations(chunks)
        return out, citations, used_hybrid, used_rerank
