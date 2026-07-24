"""RAG 流水线包。

对外暴露：切块 / 嵌入 / 混合检索 / 重排 / 引用 / 入库 的公共 API。
"""
from __future__ import annotations

from app.services.rag.chunker import chunk_document, chunk_text
from app.services.rag.citations import (
    build_citation,
    build_citations,
    format_legal_basis,
)
from app.services.rag.embedder import EmbeddingService
from app.services.rag.ingest import ingest_knowledge, ingest_legal_references
from app.services.rag.reranker import RerankerService
from app.services.rag.retriever import HybridRetriever, RetrievedChunk

__all__ = [
    "chunk_text",
    "chunk_document",
    "EmbeddingService",
    "HybridRetriever",
    "RetrievedChunk",
    "RerankerService",
    "build_citation",
    "build_citations",
    "format_legal_basis",
    "ingest_legal_references",
    "ingest_knowledge",
]
