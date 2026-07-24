"""legal_cases 表仓储：混合检索（BM25 + pgvector）+ 过滤 + 收藏。

检索模式与 Law Search（law_repo）保持一致，保证技术栈统一：
- BM25 风格中文友好匹配：ILIKE 子串 + 综合打分；
- pgvector 语义检索：1 - 余弦距离；
- RRF 融合两路候选；语义向量不可用时（无 key / 全零向量）自动退化为纯 BM25。
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import String, and_, case as sa_case, cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CourtLevelEnum, LegalCaseTypeEnum
from app.models.legal_case import LegalCase, LegalCaseFavorite
from app.services.rag.embedder import EmbeddingService

# RRF 融合常数（与 law_repo / rag/retriever 保持一致）
_RRF_K = 60
# 候选集上限（混合检索在应用层融合，数据集较小时足够）
_CANDIDATE_CAP = 60
# 时间范围映射
_TIME_RANGES = {"1y": 365, "5y": 1825}
# 连续中文段正则（仅对中文做 bigram，避免拉丁词产生无意义 bigram）
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")


def _is_zero_vec(v) -> bool:
    if not v:
        return True
    norm2 = sum(float(x) * float(x) for x in v)
    return norm2 < 1e-6


def _is_all_zero(cands: List[Tuple[LegalCase, float]]) -> bool:
    return all(_is_zero_vec(c.embedding) for c, _ in cands)


def _tokenize(raw: str) -> List[str]:
    """查询分词：按空白切分；每个片段保留原词，并对其中的连续中文段生成字符
    bigram 以提升召回。

    例：「押金不退」→ ['押金不退', '押金', '金不', '不退']；
    「房东不退押金」→ ['房东不退押金', '房东', '东不', '不退', '退押', '押金']；
    自然语言/多行案情描述（含空白）也会对每个中文片段做 bigram，避免长句整体
    无法命中（修复「查找类似案例」传入整段案情时召回为 0 的问题）。
    """
    raw = (raw or "").strip()
    if not raw:
        return []
    parts = [p for p in raw.split() if p]
    terms: List[str] = []
    for p in parts:
        terms.append(p)
        for m in _CJK_RUN.finditer(p):
            run = m.group(0)
            if len(run) >= 2:
                terms.extend(run[i : i + 2] for i in range(len(run) - 1))
    # 去重保序
    seen: set[str] = set()
    out: List[str] = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


class LegalCaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.embedder = EmbeddingService(db=self.session, feature="embedding")

    # --------------------------- 基础 ---------------------------
    async def get_by_id(self, case_id) -> Optional[LegalCase]:
        return await self.session.get(LegalCase, case_id)

    async def distinct_provinces(self) -> list[str]:
        stmt = (
            select(LegalCase.province)
            .where(LegalCase.province.isnot(None))
            .distinct()
        )
        return [r[0] for r in (await self.session.execute(stmt)).all()]

    async def distinct_cities(self) -> list[str]:
        stmt = (
            select(LegalCase.city).where(LegalCase.city.isnot(None)).distinct()
        )
        return [r[0] for r in (await self.session.execute(stmt)).all()]

    # --------------------------- 检索 ---------------------------
    async def search(
        self,
        query: str,
        *,
        province: Optional[str] = None,
        city: Optional[str] = None,
        court_level: Optional[str] = None,
        case_type: Optional[str] = None,
        time_range: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ):
        """混合检索（BM25 + pgvector）+ 过滤 + RRF 融合。

        返回 ``(ranked, total, parsed)``，``ranked`` 为已融合排序、已过滤但未分页的
        ``List[Tuple[LegalCase, float]]``，分页交给上层在重排后执行。
        """
        raw = (query or "").strip()
        terms = _tokenize(raw)

        # 过滤条件（同时作用于 BM25 与向量两路候选）
        filter_conds = self._build_filters(
            province, city, court_level, case_type, time_range
        )

        # BM25 候选：中文友好的 ILIKE 子串匹配 + 综合打分
        conds = list(filter_conds)
        for t in terms:
            conds.append(
                or_(
                    LegalCase.title.ilike(f"%{t}%"),
                    LegalCase.cause_of_action.ilike(f"%{t}%"),
                    LegalCase.facts.ilike(f"%{t}%"),
                    LegalCase.court_reasoning.ilike(f"%{t}%"),
                    LegalCase.judgement.ilike(f"%{t}%"),
                    LegalCase.court.ilike(f"%{t}%"),
                    LegalCase.plaintiff.ilike(f"%{t}%"),
                    LegalCase.defendant.ilike(f"%{t}%"),
                )
            )
        bm25_stmt = (
            select(LegalCase) if not conds else select(LegalCase).where(or_(*conds))
        )
        score = sa_case((LegalCase.title.ilike(f"%{raw}%"), 3), else_=0)
        for t in terms:
            score = score + sa_case((LegalCase.cause_of_action.ilike(f"%{t}%"), 2), else_=0)
            score = score + sa_case((LegalCase.facts.ilike(f"%{t}%"), 1), else_=0)
            score = score + sa_case((LegalCase.court_reasoning.ilike(f"%{t}%"), 1), else_=0)
            score = score + sa_case((LegalCase.judgement.ilike(f"%{t}%"), 1), else_=0)
            score = score + sa_case((LegalCase.court.ilike(f"%{t}%"), 1), else_=0)

        rows = (
            await self.session.execute(
                bm25_stmt.order_by(score.desc(), LegalCase.trial_date.desc())
                .limit(_CANDIDATE_CAP)
            )
        ).scalars().all()
        bm25_list: List[Tuple[LegalCase, float]] = [(law, 0.0) for law in rows]

        # 向量语义检索（最佳努力）
        vector_list: List[Tuple[LegalCase, float]] = []
        qvec = await self._query_embedding(raw)
        if qvec is not None:
            vec = await self.search_vector(
                qvec,
                province=province,
                city=city,
                court_level=court_level,
                case_type=case_type,
                time_range=time_range,
                limit=_CANDIDATE_CAP,
            )
            if not _is_all_zero(vec):
                vector_list = vec

        if vector_list:
            fused = self._rrf_fuse(bm25_list, vector_list)
        else:
            fused = [(law, 0.0) for law in rows]

        total = len(fused)
        parsed = {
            "terms": terms,
            "hybrid": bool(vector_list),
            "filters": {
                "province": province,
                "city": city,
                "court_level": court_level,
                "case_type": case_type,
                "time_range": time_range,
            },
        }
        return fused, total, parsed

    async def search_vector(
        self,
        qvec: List[float],
        *,
        province: Optional[str] = None,
        city: Optional[str] = None,
        court_level: Optional[str] = None,
        case_type: Optional[str] = None,
        time_range: Optional[str] = None,
        limit: int = _CANDIDATE_CAP,
    ) -> List[Tuple[LegalCase, float]]:
        """pgvector 余弦相似度检索（1 - 余弦距离）。仅对 embedding 非空生效。"""
        sim = (1 - LegalCase.embedding.cosine_distance(qvec)).label("sim")
        stmt = select(LegalCase, sim).where(LegalCase.embedding.isnot(None))
        for c in self._build_filters(
            province, city, court_level, case_type, time_range
        ):
            stmt = stmt.where(c)
        stmt = stmt.order_by(sim.desc()).limit(limit)
        rows = await self.session.execute(stmt)
        return [
            (law, float(sim_val))
            for law, sim_val in rows.all()
            if sim_val is not None
        ]

    async def _query_embedding(self, raw: str) -> Optional[List[float]]:
        if not raw or not await self.embedder.available_async():
            return None
        try:
            return await self.embedder.embed_query(raw)
        except Exception:
            return None

    @staticmethod
    def _build_filters(
        province, city, court_level, case_type, time_range
    ) -> List:
        conds = []
        if province:
            conds.append(LegalCase.province == province)
        if city:
            conds.append(LegalCase.city == city)
        if court_level:
            conds.append(LegalCase.court_level == court_level)
        if case_type:
            conds.append(LegalCase.case_type == case_type)
        if time_range in _TIME_RANGES:
            cutoff = date.today() - timedelta(days=_TIME_RANGES[time_range])
            conds.append(
                and_(
                    LegalCase.trial_date.isnot(None),
                    LegalCase.trial_date >= cutoff,
                )
            )
        return conds

    @staticmethod
    def _rrf_fuse(
        bm25_list: List[Tuple[LegalCase, float]],
        vector_list: List[Tuple[LegalCase, float]],
        k: int = _RRF_K,
    ) -> List[Tuple[LegalCase, float]]:
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

    # --------------------------- 收藏 ---------------------------
    async def add_favorite(self, user_id, case_id) -> LegalCaseFavorite:
        existing = await self.get_favorite(user_id, case_id)
        if existing:
            return existing
        return await self._create_favorite(user_id, case_id)

    async def get_favorite(self, user_id, case_id) -> Optional[LegalCaseFavorite]:
        stmt = select(LegalCaseFavorite).where(
            LegalCaseFavorite.user_id == user_id,
            LegalCaseFavorite.case_id == case_id,
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def remove_favorite(self, user_id, case_id) -> None:
        stmt = select(LegalCaseFavorite).where(
            LegalCaseFavorite.user_id == user_id,
            LegalCaseFavorite.case_id == case_id,
        )
        fav = (await self.session.execute(stmt)).scalars().first()
        if fav:
            await self.session.delete(fav)

    async def list_favorites(self, user_id) -> list[LegalCase]:
        stmt = (
            select(LegalCase)
            .join(
                LegalCaseFavorite,
                LegalCaseFavorite.case_id == LegalCase.id,
            )
            .where(LegalCaseFavorite.user_id == user_id)
            .order_by(LegalCaseFavorite.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def _create_favorite(self, user_id, case_id) -> LegalCaseFavorite:
        fav = LegalCaseFavorite(user_id=user_id, case_id=case_id)
        self.session.add(fav)
        await self.session.flush()
        return fav
