"""重排服务（Reranker）。

对混合检索的候选结果做二次精排，提升「最相关条文」的排序质量。

策略分级（优雅降级）：
1. 若配置了远程重排接口（settings.rerank_base_url + rerank_model），调用
   Cohere 兼容的 ``/rerank`` 端点，按 relevance_score 重排。
2. 任何异常或未完成配置时，自动降级到「词法重排」：基于中文字符 bigram
   重叠度计算查询与候选的相关性，保证在无外部依赖时仍有合理排序。

这样即便不接入付费重排模型，系统也能给出可用的精排结果。
"""
from __future__ import annotations

import re
from typing import List, Tuple, TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from app.services.rag.retriever import RetrievedChunk


def _bigrams(text: str) -> set[str]:
    """生成字符串的字符 bigram 集合（适配中文无空格文本）。"""
    text = re.sub(r"\s+", "", text)
    if len(text) <= 1:
        return {text}
    return {text[i : i + 2] for i in range(len(text) - 1)}


def _lexical_score(query: str, content: str) -> float:
    """查询与候选内容的 bigram 重叠率（Jaccard 式，以查询为基准）。"""
    qg = _bigrams(query)
    cg = _bigrams(content)
    if not qg:
        return 0.0
    if not cg:
        return 0.0
    return len(qg & cg) / len(qg)


class RerankerService:
    """重排服务：优先远程重排，失败则词法重排。"""

    def __init__(self) -> None:
        self.enabled = bool(settings.rerank_base_url and settings.rerank_model)
        self.base_url = (settings.rerank_base_url or "").rstrip("/")
        self.model = settings.rerank_model or ""
        self.api_key = settings.rerank_api_key or ""

    async def rerank(
        self, query: str, chunks: List["RetrievedChunk"]
    ) -> List["RetrievedChunk"]:
        """对候选 chunks 重排，返回新的有序列表（不修改原列表顺序引用）。"""
        if not chunks:
            return chunks
        if self.enabled:
            try:
                return await self._http_rerank(query, chunks)
            except Exception:
                # 远程重排不可用时静默降级，保证可用性
                pass
        return self._lexical_rerank(query, chunks)

    async def _http_rerank(
        self, query: str, chunks: List["RetrievedChunk"]
    ) -> List["RetrievedChunk"]:
        """调用 Cohere 兼容 /rerank 端点。"""
        import httpx

        documents = [f"[{c.source_table}] {c.title}\n{c.content}" for c in chunks]
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_n": len(documents),
        }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{self.base_url}/rerank", json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])
        # 按 relevance_score 降序；缺失分时使用原融合分作为兜底
        results = sorted(
            results, key=lambda r: r.get("relevance_score", 0.0), reverse=True
        )
        out: List["RetrievedChunk"] = []
        for r in results:
            idx = r.get("index")
            if idx is None or idx >= len(chunks):
                continue
            chunk = chunks[idx]
            chunk.score = float(r.get("relevance_score", chunk.score))
            out.append(chunk)
        return out

    def _lexical_rerank(
        self, query: str, chunks: List["RetrievedChunk"]
    ) -> List["RetrievedChunk"]:
        scored = [
            (c, _lexical_score(query, f"{c.title} {c.content}")) for c in chunks
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        for chunk, s in scored:
            chunk.score = round(float(s), 4)
        return [c for c, _ in scored]

    # ---------------------------------------------------------------
    # 通用重排：直接接受 (id, text) 候选，返回 (id, score) 降序。
    # 供 Law Search 等非 RetrievedChunk 场景复用同一套远程/词法降级。
    # ---------------------------------------------------------------
    async def rerank_pairs(
        self, query: str, pairs: List[Tuple[str, str]]
    ) -> List[Tuple[str, float]]:
        """对 (id, text) 候选重排，返回 (id, score) 按 score 降序。

        优先远程重排（Cohere 兼容 /rerank），失败或未完成配置时降级词法重排。
        """
        if not pairs:
            return list(pairs)
        if self.enabled:
            try:
                return await self._http_rerank_pairs(query, pairs)
            except Exception:
                pass
        return self._lexical_rerank_pairs(query, pairs)

    async def _http_rerank_pairs(
        self, query: str, pairs: List[Tuple[str, str]]
    ) -> List[Tuple[str, float]]:
        import httpx

        documents = [text for _, text in pairs]
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_n": len(documents),
        }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{self.base_url}/rerank", json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()

        results = sorted(
            data.get("results", []),
            key=lambda r: r.get("relevance_score", 0.0),
            reverse=True,
        )
        out: List[Tuple[str, float]] = []
        for r in results:
            idx = r.get("index")
            if idx is None or idx >= len(pairs):
                continue
            pid = pairs[idx][0]
            out.append((pid, float(r.get("relevance_score", 0.0))))
        return out

    def _lexical_rerank_pairs(
        self, query: str, pairs: List[Tuple[str, str]]
    ) -> List[Tuple[str, float]]:
        scored = [(pid, _lexical_score(query, text)) for pid, text in pairs]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(pid, round(float(s), 4)) for pid, s in scored]
