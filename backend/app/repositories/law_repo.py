"""law 表仓储：搜索、详情关联查询。

第二步实现「中文友好的 BM25 风格匹配」：
- 解析查询中的条款号（第X条）、法律名称、关键词；
- 用 ILIKE 子串匹配（中文无需分词即可命中）+ 法律名精确匹配；
- 综合打分排序（法律名 > 条款号 > 关键词），现行有效优先。

第四步在 BM25 基础上叠加 pgvector 语义检索，做 Hybrid（向量 + BM25）
+ RRF 融合 + Reranker 重排（见 services/law_search_service.py 调用 RerankerService）。
"""
from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import String, case as sa_case, cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LegalSourceEnum
from app.models.law import Law, LawStatusEnum
from app.services.rag.embedder import EmbeddingService

ARTICLE_RE = re.compile(r"第\s*(\d+)\s*条")

# RRF 融合常数（与 rag/retriever.py 保持一致）
_RRF_K = 60
# 候选集上限（混合检索在应用层融合，数据集较小时足够）
_CANDIDATE_CAP = 60


def _article_sort_key(article: Optional[str]):
    """同法条文按条款号数值排序；无号码的排后面。"""
    if not article:
        return (2, 0, "")
    m = ARTICLE_RE.search(article)
    if m:
        return (1, int(m.group(1)), article)
    return (2, 0, article or "")


def _is_zero_vec(v) -> bool:
    """判断向量是否为零向量（占位 key 灌库会产生全零向量，语义检索无意义）。"""
    if not v:
        return True
    norm2 = sum(float(x) * float(x) for x in v)
    return norm2 < 1e-6


def _is_all_zero(cands: List[Tuple[Law, float]]) -> bool:
    """候选集是否全是零向量（语义检索退化为 BM25 的信号）。"""
    return all(_is_zero_vec(law.embedding) for law, _ in cands)


class LawRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.embedder = EmbeddingService(db=self.session, feature="embedding")

    async def get_by_id(self, law_id) -> Optional[Law]:
        return await self.session.get(Law, law_id)

    async def distinct_law_names(self) -> list[str]:
        stmt = select(Law.law_name).where(Law.law_name.isnot(None)).distinct()
        res = await self.session.execute(stmt)
        return [r[0] for r in res.all()]

    async def search(
        self,
        query: str,
        *,
        status: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ):
        """混合检索（第四步）：BM25 + pgvector 语义，RRF 融合。

        返回 ``(ranked, total, parsed)``，其中 ``ranked`` 为
        ``List[Tuple[Law, float]]``（已融合排序、并已按 status 过滤，但未分页）；
        分页交给上层 ``LawSearchService`` 在重排之后执行，便于全局重排。
        语义向量不可用时（无 key / 全零向量）自动退化为纯 BM25。
        """
        raw = (query or "").strip()
        terms = [t for t in re.split(r"\s+", raw) if t]

        # 解析条款号
        article_num = None
        for t in list(terms):
            m = ARTICLE_RE.search(t)
            if m:
                article_num = m.group(1)
                terms.remove(t)

        # 识别法律名称（库内已有法律名被查询词包含）
        law_names = await self.distinct_law_names()
        matched_law = next((ln for ln in law_names if ln and ln in raw), None)

        # keywords 是 json 列，需先转 jsonb 再取文本才能用 ILIKE 命中数组元素
        kw_text = cast(cast(Law.keywords, JSONB), String)
        conds = []
        if matched_law:
            conds.append(Law.law_name == matched_law)
        if article_num:
            conds.append(Law.article.ilike(f"%{article_num}%"))
        for t in terms:
            conds.append(
                or_(
                    Law.content.ilike(f"%{t}%"),
                    Law.law_name.ilike(f"%{t}%"),
                    Law.article.ilike(f"%{t}%"),
                    Law.chapter.ilike(f"%{t}%"),
                    Law.section.ilike(f"%{t}%"),
                    kw_text.ilike(f"%{t}%"),
                )
            )

        bm25_stmt = select(Law) if not conds else select(Law).where(or_(*conds))

        # 打分：法律名命中 > 条款号命中 > 关键词命中
        score = sa_case((Law.law_name.ilike(f"%{raw}%"), 3), else_=0)
        if article_num:
            score = score + sa_case((Law.article.ilike(f"%{article_num}%"), 2), else_=0)
        for t in terms:
            score = score + sa_case((Law.content.ilike(f"%{t}%"), 1), else_=0)
            score = score + sa_case((Law.law_name.ilike(f"%{t}%"), 2), else_=0)
            score = score + sa_case((kw_text.ilike(f"%{t}%"), 1), else_=0)

        # 现行有效优先
        status_rank = sa_case(
            (Law.status == LawStatusEnum.EFFECTIVE.value, 0), else_=1
        )

        rows = (
            await self.session.execute(
                bm25_stmt.order_by(
                    status_rank, score.desc(), Law.law_name, Law.article
                ).limit(_CANDIDATE_CAP)
            )
        ).scalars().all()
        # BM25 候选：仅用排名做 RRF（与向量路公平竞争）
        bm25_list: List[Tuple[Law, float]] = [(law, 0.0) for law in rows]

        # 向量语义检索（最佳努力；不可用或全零向量时退化为 BM25）
        vector_list: List[Tuple[Law, float]] = []
        qvec = await self._query_embedding(raw)
        if qvec is not None:
            vec = await self.search_vector(qvec, limit=_CANDIDATE_CAP)
            if not _is_all_zero(vec):
                vector_list = vec

        if vector_list:
            fused = self._rrf_fuse_laws(bm25_list, vector_list)
        else:
            fused = [(law, 0.0) for law in rows]

        # 状态过滤（两条候选路都需统一过滤）
        if status:
            fused = [(law, s) for law, s in fused if str(law.status) == status]

        total = len(fused)
        parsed = {
            "law_name": matched_law,
            "article": f"第{article_num}条" if article_num else None,
            "terms": terms,
            "hybrid": bool(vector_list),
        }
        return fused, total, parsed

    async def search_vector(
        self, qvec: List[float], *, status: Optional[str] = None, limit: int = _CANDIDATE_CAP
    ) -> List[Tuple[Law, float]]:
        """pgvector 余弦相似度检索（1 - 余弦距离）。仅对 embedding 非空生效。"""
        sim = (1 - Law.embedding.cosine_distance(qvec)).label("sim")
        stmt = select(Law, sim).where(Law.embedding.isnot(None))
        if status:
            stmt = stmt.where(Law.status == status)
        stmt = stmt.order_by(sim.desc()).limit(limit)
        rows = await self.session.execute(stmt)
        return [
            (law, float(sim_val))
            for law, sim_val in rows.all()
            if sim_val is not None
        ]

    async def _query_embedding(self, raw: str) -> Optional[List[float]]:
        """取得查询向量；无 key / 调用失败时返回 None（语义检索降级）。"""
        if not raw or not await self.embedder.available_async():
            return None
        try:
            return await self.embedder.embed_query(raw)
        except Exception:
            return None

    @staticmethod
    def _rrf_fuse_laws(
        bm25_list: List[Tuple[Law, float]],
        vector_list: List[Tuple[Law, float]],
        k: int = _RRF_K,
    ) -> List[Tuple[Law, float]]:
        """互逆排名融合（RRF）：score = Σ 1/(k + rank_i)。"""
        fused: dict = {}
        for lst in (bm25_list, vector_list):
            for rank, (law, _) in enumerate(lst, start=1):
                rrf = 1.0 / (k + rank)
                if law.id in fused:
                    fused[law.id][1] += rrf
                else:
                    fused[law.id] = [law, rrf]
        return [
            (law, score)
            for law, score in sorted(
                fused.values(), key=lambda x: x[1], reverse=True
            )
        ]

    async def get_prev_next(self, law: Law):
        """同法律名下按条款号排序的相邻条文。"""
        sibs = (
            await self.session.execute(
                select(Law).where(Law.law_name == law.law_name)
            )
        ).scalars().all()
        sibs = sorted(sibs, key=lambda x: _article_sort_key(x.article))
        idx = next((i for i, l in enumerate(sibs) if l.id == law.id), None)
        prev = sibs[idx - 1] if (idx is not None and idx > 0) else None
        nxt = sibs[idx + 1] if (idx is not None and idx + 1 < len(sibs)) else None
        return prev, nxt

    async def get_related_by_keywords(
        self, keywords, exclude_id, limit: int = 6
    ) -> list[Law]:
        if not keywords:
            return []
        # JSON 列用 jsonb 的 @> 包含操作符（不要用 .contains 列表，会生成错误的 LIKE）
        conds = [
            cast(Law.keywords, JSONB).op("@>")(func.jsonb_build_array(k))
            for k in keywords
        ]
        stmt = (
            select(Law)
            .where(or_(*conds))
            .where(Law.id != exclude_id)
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_siblings(
        self, law_name, exclude_id=None, limit: int = 20
    ) -> list[Law]:
        stmt = select(Law).where(Law.law_name == law_name)
        if exclude_id:
            stmt = stmt.where(Law.id != exclude_id)
        rows = (await self.session.execute(stmt)).scalars().all()
        return sorted(rows, key=lambda x: _article_sort_key(x.article))[:limit]

    async def related_from_legal_reference(
        self, law_name, keywords, limit: int = 5
    ) -> list:
        """从 legal_reference（RAG 库）关联司法解释 / 指导案例 / 典型案例。

        复用既有 RAG 法律库，避免重复存储法条释义与案例。
        """
        from app.models.legal_reference import LegalReference

        conds = []
        if law_name:
            conds.append(LegalReference.title.ilike(f"%{law_name}%"))
        for k in keywords or []:
            conds.append(LegalReference.content.ilike(f"%{k}%"))
        if not conds:
            return []
        stmt = (
            select(LegalReference)
            .where(
                LegalReference.source.in_(
                    [
                        LegalSourceEnum.JUDICIAL_INTERPRETATION,
                        LegalSourceEnum.GUIDING_CASE,
                        LegalSourceEnum.TYPICAL_CASE,
                    ]
                )
            )
            .where(or_(*conds))
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_latest(self, limit: int = 10) -> list[Law]:
        stmt = select(Law).order_by(Law.created_at.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())
