"""研究文档仓储（Legal Research Center）。

检索架构（与 legal_cases / law 保持一致，复用 Reranker 与 Embedding）：
- 关键词/布尔检索：对 title / doc_number / full_text / source / issuing_authority 做
  ILIKE 子串 + 中文 bigram 扩展，支持 AND / OR / NOT（空格分隔，可加括号）；
- 语义检索：pgvector 余弦相似度（BGE-M3，dim=1024）；
- 混合：RRF 融合两路候选（跨 6 张表统一以 (doc_type, id) 为键）；
- 优雅降级：无 embedding key / 向量全零时自动退化为纯关键词检索；
- 高级过滤：分类 / 文档类型 / 层级 / 地区 / 发文机关 / 时效 / 发布·实施·失效日期区间。
"""
from __future__ import annotations

import re
from datetime import date
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy import case as sa_case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.research import RESEARCH_TABLES

# 复用 legal_cases 的中文分词（bigram 提升召回）
from app.repositories.legal_case_repo import _tokenize  # noqa: F401
from app.services.rag.embedder import EmbeddingService

_RRF_K = 60
_CANDIDATE_CAP = 60
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")

# 布尔运算符（中英文均可，须以空格分隔；缺省相邻词视为 AND）
_OP_AND = {"AND", "与", "&&", "并且", "且"}
_OP_OR = {"OR", "或", "||", "或者"}
_OP_NOT = {"NOT", "非", "!", "不"}
_PREC = {"OR": 1, "AND": 2, "NOT": 3}


def _is_zero_vec(v) -> bool:
    if not v:
        return True
    return sum(float(x) * float(x) for x in v) < 1e-6


def _bigrams_cjk(term: str) -> List[str]:
    """对中文术语做字符 bigram（≥2 字时扩展，提升子串召回）。"""
    out: List[str] = []
    for m in _CJK_RUN.finditer(term):
        run = m.group(0)
        if len(run) >= 2:
            out.extend(run[i : i + 2] for i in range(len(run) - 1))
    return out


def _lex(q: str) -> List[Tuple[str, str]]:
    """分词为 token 流：(类型, 值)。在相邻操作数之间插入隐式 AND。"""
    raw = (q or "").strip()
    if not raw:
        return []
    tokens: List[Tuple[str, str]] = []
    for piece in raw.split():
        u = piece.upper()
        if u in _OP_AND:
            tokens.append(("AND", piece))
        elif u in _OP_OR:
            tokens.append(("OR", piece))
        elif u in _OP_NOT:
            tokens.append(("NOT", piece))
        elif piece in ("(", "（"):
            tokens.append(("LP", piece))
        elif piece in (")", "）"):
            tokens.append(("RP", piece))
        else:
            # 隐式 AND：前一 token 为操作数（TERM 或右括号）时插入
            if tokens and tokens[-1][0] in ("TERM", "RP"):
                tokens.append(("AND", "AND"))
            tokens.append(("TERM", piece))
    return tokens


def _term_clause(term: str, columns) -> "sa_case":
    """单关键词条件：对可检索字段做 ILIKE（原词 + 中文 bigram 扩展）。"""
    grams = {term} | set(_bigrams_cjk(term))
    conds = []
    for col in columns:
        for g in grams:
            conds.append(col.ilike(f"%{g}%"))
    return or_(*conds)


def _build_keyword_clause(q: str, columns) -> Optional["sa_case"]:
    """将查询字符串解析为布尔表达式（AND/OR/NOT 可加括号）。无关键词返回 None。"""
    toks = _lex(q)
    if not toks:
        return None

    # 调度场算法（shunting-yard）-> 逆波兰式
    output: List[Tuple[str, str]] = []
    ops: List[Tuple[str, str]] = []
    for t in toks:
        if t[0] == "TERM":
            output.append(t)
        elif t[0] in ("AND", "OR", "NOT"):
            while (
                ops
                and ops[-1][0] != "LP"
                and _PREC[ops[-1][0]] >= _PREC[t[0]]
            ):
                output.append(ops.pop())
            ops.append(t)
        elif t[0] == "LP":
            ops.append(t)
        elif t[0] == "RP":
            while ops and ops[-1][0] != "LP":
                output.append(ops.pop())
            if ops and ops[-1][0] == "LP":
                ops.pop()
    while ops:
        output.append(ops.pop())

    if not output:
        return None

    stack: List = []
    for t in output:
        if t[0] == "TERM":
            stack.append(_term_clause(t[1], columns))
        elif t[0] == "NOT":
            a = stack.pop()
            stack.append(~a)
        elif t[0] == "AND":
            b = stack.pop()
            a = stack.pop()
            stack.append(and_(a, b))
        elif t[0] == "OR":
            b = stack.pop()
            a = stack.pop()
            stack.append(or_(a, b))
    return stack[0] if stack else None


class ResearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.embedder = EmbeddingService(db=self.session, feature="embedding")

    # --------------------------- 检索 ---------------------------
    async def search(
        self,
        query: str,
        *,
        doc_type: Optional[str] = None,
        category: Optional[str] = None,
        level: Optional[str] = None,
        region: Optional[str] = None,
        issuing_authority: Optional[str] = None,
        is_current: Optional[bool] = None,
        publish_from: Optional[date] = None,
        publish_to: Optional[date] = None,
        effective_from: Optional[date] = None,
        effective_to: Optional[date] = None,
        expiry_from: Optional[date] = None,
        expiry_to: Optional[date] = None,
        search_mode: str = "auto",
        limit: int = 10,
        offset: int = 0,
    ) -> Tuple[List[Tuple[object, str, float]], int, dict]:
        """混合检索（关键词/布尔 + 语义）+ 高级过滤 + 跨表 RRF 融合。

        返回 ``(ranked, total, parsed)``，``ranked`` 为 ``List[(obj, doc_type, score)]``。
        """
        raw = (query or "").strip()
        terms = _tokenize(raw)
        use_vector = search_mode != "full_text"

        merged: dict = {}  # (doc_type, id) -> [obj, doc_type, score]
        for model, dt, _ in RESEARCH_TABLES:
            if doc_type and dt != doc_type:
                continue
            columns = [
                model.title,
                model.doc_number,
                model.full_text,
                model.source,
                model.issuing_authority,
            ]
            kw = _build_keyword_clause(raw, columns)
            facet = self._build_filters(
                model,
                category=category,
                level=level,
                region=region,
                issuing_authority=issuing_authority,
                is_current=is_current,
                publish_from=publish_from,
                publish_to=publish_to,
                effective_from=effective_from,
                effective_to=effective_to,
                expiry_from=expiry_from,
                expiry_to=expiry_to,
            )

            bm25 = await self._bm25(model, raw, kw, facet, terms)
            vector: List[Tuple[object, float]] = []
            if use_vector:
                qvec = await self._query_embedding(raw)
                if qvec is not None:
                    vector = await self._vector(model, qvec, facet)
            fused = self._rrf_fuse(bm25, vector)
            for obj, score in fused:
                key = (dt, str(obj.id))
                if key in merged:
                    merged[key][2] += score
                else:
                    merged[key] = [obj, dt, score]

        # 跨表统一排序（RRF 分求和后再按分降序）
        ranked = sorted(merged.values(), key=lambda x: x[2], reverse=True)
        total = len(ranked)
        parsed = {
            "terms": terms,
            "mode": "semantic" if (use_vector and any(vector)) else "full_text",
            "boolean": bool(raw and (" " in raw or any(op in raw.upper() for op in (" AND ", " OR ", " NOT ")))),
            "filters": {
                "doc_type": doc_type,
                "category": category,
                "level": level,
                "region": region,
                "issuing_authority": issuing_authority,
                "is_current": is_current,
            },
        }
        return ranked, total, parsed

    async def _bm25(self, model, raw, kw, facet, terms):
        conds = list(facet)
        if kw is not None:
            conds.append(kw)
        stmt = select(model)
        if conds:
            stmt = stmt.where(and_(*conds))
        score = (
            sa_case((model.title.ilike(f"%{raw}%"), 3), else_=0)
            if raw
            else sa_case((model.is_current.is_(True), 1), else_=0)
        )
        for t in terms:
            score = score + sa_case((model.title.ilike(f"%{t}%"), 2), else_=0)
            score = score + sa_case(
                (
                    or_(
                        model.full_text.ilike(f"%{t}%"),
                        model.doc_number.ilike(f"%{t}%"),
                        model.source.ilike(f"%{t}%"),
                        model.issuing_authority.ilike(f"%{t}%"),
                    ),
                    1,
                ),
                else_=0,
            )
        rows = (
            await self.session.execute(
                stmt.order_by(score.desc(), model.publish_date.desc().nullslast())
                .limit(_CANDIDATE_CAP)
            )
        ).scalars().all()
        return [(law, 0.0) for law in rows]

    async def _vector(self, model, qvec, facet) -> List[Tuple[object, float]]:
        sim = (1 - model.embedding.cosine_distance(qvec)).label("sim")
        stmt = select(model, sim).where(model.embedding.isnot(None))
        for c in facet:
            stmt = stmt.where(c)
        stmt = stmt.order_by(sim.desc()).limit(_CANDIDATE_CAP)
        rows = await self.session.execute(stmt)
        return [
            (obj, float(s)) for obj, s in rows.all() if s is not None
        ]

    async def _query_embedding(self, raw: str):
        if not raw or not await self.embedder.available_async():
            return None
        try:
            return await self.embedder.embed_query(raw)
        except Exception:
            return None

    # --------------------------- 过滤 ---------------------------
    @staticmethod
    def _build_filters(
        model,
        *,
        category=None,
        level=None,
        region=None,
        issuing_authority=None,
        is_current=None,
        publish_from=None,
        publish_to=None,
        effective_from=None,
        effective_to=None,
        expiry_from=None,
        expiry_to=None,
    ) -> List:
        conds = []
        if category:
            conds.append(model.category == category)
        if level:
            conds.append(model.level == level)
        if region:
            conds.append(model.region == region)
        if issuing_authority:
            conds.append(model.issuing_authority == issuing_authority)
        if is_current is not None:
            conds.append(model.is_current == is_current)
        if publish_from is not None:
            conds.append(model.publish_date >= publish_from)
        if publish_to is not None:
            conds.append(model.publish_date <= publish_to)
        if effective_from is not None:
            conds.append(model.effective_date >= effective_from)
        if effective_to is not None:
            conds.append(model.effective_date <= effective_to)
        if expiry_from is not None:
            conds.append(model.expiry_date >= expiry_from)
        if expiry_to is not None:
            conds.append(model.expiry_date <= expiry_to)
        return conds

    @staticmethod
    def _rrf_fuse(bm25_list, vector_list, k: int = _RRF_K):
        """互逆排名融合（RRF）：score = Σ 1/(k + rank_i)。"""
        fused: dict = {}
        for lst in (bm25_list, vector_list):
            for rank, (obj, _) in enumerate(lst, start=1):
                rrf = 1.0 / (k + rank)
                if obj.id in fused:
                    fused[obj.id][1] += rrf
                else:
                    fused[obj.id] = [obj, rrf]
        return [
            (obj, score)
            for obj, score in sorted(fused.values(), key=lambda x: x[1], reverse=True)
        ]

    # --------------------------- 单文档 / 关联 ---------------------------
    async def get_by_id(self, doc_id: UUID) -> Tuple[Optional[object], Optional[str]]:
        for model, dt, _ in RESEARCH_TABLES:
            obj = await self.session.get(model, doc_id)
            if obj is not None:
                return obj, dt
        return None, None

    async def get_related(self, related_ids: List[str]) -> List[Tuple[object, str]]:
        out: List[Tuple[object, str]] = []
        ids: List[UUID] = []
        for rid in related_ids or []:
            try:
                ids.append(UUID(rid))
            except (ValueError, AttributeError):
                continue
        if not ids:
            return out
        for model, dt, _ in RESEARCH_TABLES:
            rows = (
                await self.session.execute(select(model).where(model.id.in_(ids)))
            ).scalars().all()
            for o in rows:
                out.append((o, dt))
        return out
