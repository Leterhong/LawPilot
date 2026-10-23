"""法律研究中心服务（Legal Research Center）。

编排检索/详情/推荐，并在详情页按需懒生成 AI 解读（通俗解释 + 摘要）：
- 优先使用已落库的 ai_explanation / ai_summary；
- 未生成且 LLM key 可用时，调用 LLM 生成并写回（缓存），避免重复开销；
- LLM 不可用或失败时优雅降级为 None，前端展示占位提示，绝不抛错。
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.legal_case_repo import _tokenize  # 复用中文分词
from app.repositories.research_repo import ResearchRepository
from app.schemas.research import (
    CATEGORY_LABELS,
    DOC_TYPE_LABELS,
    RelatedDocRef,
    ResearchDocDetail,
    ResearchRecommendResult,
    ResearchSearchItem,
    ResearchSearchResult,
)
from app.services.llm.client import LLMClient
from app.services.rag.reranker import RerankerService


class ResearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ResearchRepository(session)
        self.reranker = RerankerService()
        self.llm = LLMClient(db=self.session, feature="legal_analysis")

    # --------------------------- 搜索 ---------------------------
    async def search(
        self,
        q: str,
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
    ) -> ResearchSearchResult:
        ranked, total, parsed = await self.repo.search(
            q,
            doc_type=doc_type,
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
            search_mode=search_mode,
            limit=limit,
            offset=offset,
        )

        # 跨表重排（远程优先，失败降级词法 bigram 重叠度）
        if ranked:
            pairs = [
                (
                    f"{dt}:{obj.id}",
                    f"{obj.title} {obj.doc_number or ''} "
                    f"{(obj.full_text or '')[:200]} {obj.source or ''} "
                    f"{obj.issuing_authority or ''}",
                )
                for obj, dt, _ in ranked
            ]
            try:
                reranked = await self.reranker.rerank_pairs(q, pairs)
                order = {pid: sc for pid, sc in reranked}
                ranked = sorted(
                    ranked,
                    key=lambda x: order.get(f"{x[1]}:{x[0].id}", 0.0),
                    reverse=True,
                )
            except Exception:
                pass

        page = ranked[offset : offset + limit]
        terms = list(parsed.get("terms") or [])
        items = [self._to_item(obj, dt, terms, q, score) for obj, dt, score in page]
        facets = self._facets(ranked)
        return ResearchSearchResult(
            query=q,
            total=total,
            items=items,
            parsed=parsed,
            filters=parsed.get("filters"),
            facets=facets,
        )

    def _to_item(self, obj, dt: str, terms: list[str], q: str, score) -> ResearchSearchItem:
        snippet = self._build_snippet(obj, terms)
        return ResearchSearchItem(
            id=obj.id,
            doc_type=dt,
            title=obj.title,
            doc_number=obj.doc_number,
            category=obj.category,
            summary_one_line=obj.summary_one_line,
            core_points=obj.core_points,
            scope=obj.scope,
            common_misconceptions=obj.common_misconceptions,
            publish_date=obj.publish_date,
            effective_date=obj.effective_date,
            expiry_date=obj.expiry_date,
            is_current=obj.is_current,
            source=obj.source,
            level=obj.level,
            region=obj.region,
            issuing_authority=obj.issuing_authority,
            keywords=obj.keywords,
            related_law_ids=obj.related_law_ids,
            related_case_ids=obj.related_case_ids,
            related_interpretation_ids=obj.related_interpretation_ids,
            snippet=snippet,
            score=round(float(score), 4) if score is not None else None,
            highlight={"title": self._highlight(obj.title or "", terms), "snippet": snippet},
            category_label=CATEGORY_LABELS.get(obj.category, obj.category),
            doc_type_label=DOC_TYPE_LABELS.get(dt, dt),
        )

    # --------------------------- 详情 ---------------------------
    async def detail(self, doc_id: UUID) -> Optional[ResearchDocDetail]:
        obj, dt = await self.repo.get_by_id(doc_id)
        if obj is None:
            return None

        related_raw = (
            list(obj.related_law_ids or [])
            + list(obj.related_case_ids or [])
            + list(obj.related_interpretation_ids or [])
        )
        related_rows = await self.repo.get_related(related_raw)
        related_docs = [
            RelatedDocRef(
                id=o.id,
                doc_type=d,
                title=o.title,
                category=o.category,
                summary_one_line=o.summary_one_line,
            )
            for o, d in related_rows
        ]

        # 懒生成 AI 解读（已落库则直接复用）
        ai_explanation, ai_summary = await self._ensure_ai(obj, dt)

        return ResearchDocDetail(
            id=obj.id,
            doc_type=dt,
            title=obj.title,
            doc_number=obj.doc_number,
            category=obj.category,
            summary_one_line=obj.summary_one_line,
            core_points=obj.core_points,
            scope=obj.scope,
            common_misconceptions=obj.common_misconceptions,
            publish_date=obj.publish_date,
            effective_date=obj.effective_date,
            expiry_date=obj.expiry_date,
            is_current=obj.is_current,
            source=obj.source,
            level=obj.level,
            region=obj.region,
            issuing_authority=obj.issuing_authority,
            keywords=obj.keywords,
            related_law_ids=obj.related_law_ids,
            related_case_ids=obj.related_case_ids,
            related_interpretation_ids=obj.related_interpretation_ids,
            full_text=obj.full_text,
            related_docs=related_docs,
            ai_explanation=ai_explanation,
            ai_summary=ai_summary,
            category_label=CATEGORY_LABELS.get(obj.category, obj.category),
            doc_type_label=DOC_TYPE_LABELS.get(dt, dt),
        )

    async def _ensure_ai(self, obj, dt: str):
        """懒生成并缓存 AI 通俗解释与摘要；LLM 不可用则降级为 None。"""
        if obj.ai_explanation and obj.ai_summary:
            return obj.ai_explanation, obj.ai_summary
        if not await self.llm.available_async():
            return obj.ai_explanation, obj.ai_summary
        data = await self._generate_ai(obj)
        if not data:
            return obj.ai_explanation, obj.ai_summary
        explanation = data.get("ai_explanation")
        summary = data.get("ai_summary")
        # 写回缓存（仅新表，不影响任何已有模块）
        try:
            if explanation:
                obj.ai_explanation = explanation
            if summary:
                obj.ai_summary = summary
            await self.session.commit()
        except Exception:
            await self.session.rollback()
        return explanation or obj.ai_explanation, summary or obj.ai_summary

    async def _generate_ai(self, obj) -> Optional[dict]:
        brief = (
            f"标题：{obj.title}\n"
            f"分类：{CATEGORY_LABELS.get(obj.category, obj.category)}（{DOC_TYPE_LABELS.get(getattr(obj, 'doc_type', ''), '')}）\n"
            f"发文字号：{obj.doc_number or '—'}\n"
            f"发文机关：{obj.issuing_authority or '—'}\n"
            f"生效日期：{obj.effective_date or '—'}　是否现行有效：{'是' if obj.is_current else '否'}\n"
            f"全文：\n{(obj.full_text or '')[:2200]}\n"
        )
        prompt = (
            "你是一个资深法律研究助手。请基于下面这份法律研究文档，输出 JSON：\n"
            "{\"ai_explanation\": \"用通俗语言向普通民众解释：这份文件是什么、解决什么问题、"
            "普通人/企业应当注意哪些要点（200字以内，避免法律黑话）\", "
            "\"ai_summary\": \"一句话精炼摘要（50字以内）\"}\n"
            "只输出 JSON，不要解释。\n\n"
            f"{brief}"
        )
        try:
            return await self.llm.complete_json(prompt)
        except Exception:
            return None

    # --------------------------- 推荐 ---------------------------
    @staticmethod
    def _recommend_query(obj) -> str:
        """为「相关推荐」构造检索式：优先用关键词；否则从标题抽取中文 bigram 并以 OR 连接，
        避免把整句长标题当作单一字面量（否则无法命中其它文档）。"""
        kw = list(obj.keywords or [])
        if kw:
            return " OR ".join(kw[:12])
        terms = _tokenize(obj.title or "")
        # 丢弃整句长词（=_tokenize 的首个整串 token），仅保留 bigram 级短词以扩大召回
        short = [t for t in terms if len(t) <= 4]
        if short:
            return " OR ".join(short[:12])
        return obj.title or ""

    async def recommend(
        self,
        doc_id: Optional[UUID] = None,
        q: Optional[str] = None,
        limit: int = 10,
    ) -> ResearchRecommendResult:
        if doc_id is not None:
            obj, _ = await self.repo.get_by_id(doc_id)
            if obj is None:
                return ResearchRecommendResult(query="", seed_id=doc_id, total=0, items=[])
            seed_query = self._recommend_query(obj)
            ranked, total, parsed = await self.repo.search(
                seed_query, search_mode="auto", limit=limit + 6
            )
            ranked = [(o, d, s) for (o, d, s) in ranked if str(o.id) != str(doc_id)]
            query = obj.title
        elif q and q.strip():
            ranked, total, parsed = await self.repo.search(
                q.strip(), search_mode="auto", limit=limit
            )
            query = q.strip()
        else:
            return ResearchRecommendResult(query="", seed_id=doc_id, total=0, items=[])

        # 重排
        if ranked:
            pairs = [
                (f"{d}:{o.id}", f"{o.title} {(o.full_text or '')[:200]}")
                for o, d, _ in ranked
            ]
            try:
                reranked = await self.reranker.rerank_pairs(query, pairs)
                order = {pid: sc for pid, sc in reranked}
                ranked = sorted(
                    ranked, key=lambda x: order.get(f"{x[1]}:{x[0].id}", 0.0), reverse=True
                )
            except Exception:
                pass

        page = ranked[:limit]
        items = [
            self._to_item(o, d, [], query, s) for o, d, s in page
        ]
        return ResearchRecommendResult(
            query=query, seed_id=doc_id, total=len(items), items=items
        )

    # --------------------------- 工具 ---------------------------
    @staticmethod
    def _facets(ranked) -> dict:
        counts: dict[str, int] = {}
        for obj, _dt, _s in ranked:
            cat = getattr(obj, "category", None) or "其他"
            counts[cat] = counts.get(cat, 0) + 1
        return {cat: {"label": CATEGORY_LABELS.get(cat, cat), "count": n} for cat, n in counts.items()}

    @staticmethod
    def _highlight(text: str, terms: list[str], window: int = 90) -> str:
        if not text:
            return ""
        low = text.lower()
        pos = -1
        for t in terms:
            if not t:
                continue
            i = low.find(t.lower())
            if i >= 0 and (pos < 0 or i < pos):
                pos = i
        if pos < 0:
            snippet = text[:window]
            return snippet + ("…" if len(text) > window else "")
        start = max(0, pos - window // 2)
        end = min(len(text), pos + window // 2)
        snippet = text[start:end]
        for t in terms:
            if not t:
                continue
            snippet = re.sub(
                re.escape(t), lambda m: f"<mark>{m.group(0)}</mark>", snippet, flags=re.I
            )
        return ("…" if start > 0 else "") + snippet + ("…" if end < len(text) else "")

    @staticmethod
    def _build_snippet(obj, terms: list[str]) -> str:
        for field in (obj.full_text, obj.scope, obj.summary_one_line):
            if field:
                return ResearchService._highlight(field, terms)
        return ResearchService._highlight(obj.title or "", terms)
