"""法律搜索服务（Law Search 模块）。

第二步实现基础检索：BM25 风格中文友好匹配 + 查询结构解析 + 关键词高亮 +
详情关联（上/下条、相关法条、司法解释、案例、推荐）+ 搜索历史记录。
第四步将升级为 pgvector 语义检索 + Hybrid(向量+BM25) + Reranker 精排。
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.law import Law, LawStatusEnum
from app.models.user import User
from app.repositories.law_repo import LawRepository
from app.repositories.law_search_history_repo import LawSearchHistoryRepository
from app.schemas.law import (
    LawDetail,
    LawHistoryOut,
    LawOut,
    LawSearchItem,
    LawSearchResult,
)
from app.services.llm.client import LLMClient
from app.services.rag.reranker import RerankerService

# AI 通俗解释缓存（按 law id），避免重复调用 LLM；数据集小，无需淘汰。
_EXPLAIN_CACHE: dict = {}


class LawSearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.law = LawRepository(session)
        self.history = LawSearchHistoryRepository(session)
        self.reranker = RerankerService()
        self.llm = LLMClient(db=self.session, feature="law_explain")

    # --------------------------- 搜索 ---------------------------
    async def search(
        self,
        q: str,
        current_user: Optional[User] = None,
        status: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> LawSearchResult:
        ranked, total, parsed = await self.law.search(
            q, status=status, limit=limit, offset=offset
        )
        terms = list(parsed.get("terms") or [])
        if parsed.get("law_name"):
            terms.insert(0, parsed["law_name"])
        if parsed.get("article"):
            terms.insert(0, parsed["article"])

        # 重排：对融合候选做 Reranker（远程优先，否则词法 bigram 重叠度）
        if ranked:
            pairs = [
                (str(law.id), f"{law.law_name} {law.article or ''} {law.content}")
                for law, _ in ranked
            ]
            try:
                reranked = await self.reranker.rerank_pairs(q, pairs)
                order = {pid: sc for pid, sc in reranked}
                # 重排后回填 score，并按重排分重新排序
                ranked = sorted(
                    [(law, order.get(str(law.id), 0.0)) for law, _ in ranked],
                    key=lambda ls: ls[1],
                    reverse=True,
                )
            except Exception:
                pass

        # 分页（重排后再切片，保证全局排序正确）
        page = ranked[offset : offset + limit]
        out = [self._to_item(law, terms, score=score) for law, score in page]

        # 记录搜索历史（匿名搜索 user_id 为 NULL）
        await self.history.add(
            q, user_id=current_user.id if current_user else None, result_count=total
        )
        await self.session.commit()
        return LawSearchResult(query=q, total=total, items=out, parsed=parsed)

    def _to_item(self, law: Law, terms: list[str], score: Optional[float] = None) -> LawSearchItem:
        snippet = self._highlight(law.content, terms)
        return LawSearchItem(
            id=law.id,
            law_name=law.law_name,
            chapter=law.chapter,
            section=law.section,
            article=law.article,
            content=law.content,
            keywords=law.keywords,
            effective_date=law.effective_date,
            status=self._status_val(law.status),
            source=law.source,
            snippet=snippet,
            score=score,
            highlight={
                "content": snippet,
                "law_name": self._highlight(law.law_name or "", terms),
            },
        )

    # --------------------------- 详情 ---------------------------
    async def _explain(self, law: Law) -> Optional[str]:
        """生成法条通俗解释（第四步）：有真实 LLM key 时调用，否则返回 None。"""
        if not await self.llm.available_async():
            return None
        key = str(law.id)
        cached = _EXPLAIN_CACHE.get(key)
        if cached is not None:
            return cached
        prompt = (
            f"请用通俗语言向普通老百姓解释下面这条法律条文：\n"
            f"法律：《{law.law_name}》{law.article or ''}\n"
            f"正文：{law.content}\n\n"
            f"请说明：①这条法律保护谁、保护什么；②老百姓遇到类似情况能怎么做；"
            f"③一句话核心要点。控制在 2-4 句话，不要编造法律条文。"
        )
        try:
            text = await self.llm.complete(
                prompt,
                system="你是一名中国法律科普助手，语言通俗、准确、不误导。",
            )
        except Exception:
            text = None
        if text:
            _EXPLAIN_CACHE[key] = text
        return text

    async def detail(self, law_id):
        law = await self.law.get_by_id(law_id)
        if not law:
            return None
        prev, nxt = await self.law.get_prev_next(law)
        related = await self.law.get_related_by_keywords(
            law.keywords, law.id, limit=6
        )
        refs = await self.law.related_from_legal_reference(
            law.law_name, law.keywords, limit=8
        )
        interps, cases = self._split_legal_references(refs)
        recs = await self.recommend(law.id, limit=6)
        return LawDetail(
            id=law.id,
            law_name=law.law_name,
            chapter=law.chapter,
            section=law.section,
            article=law.article,
            content=law.content,
            keywords=law.keywords,
            effective_date=law.effective_date,
            status=self._status_val(law.status),
            source=law.source,
            ai_explanation=await self._explain(law),  # 第四步：LLM 生成通俗解释（无 key 时降级 None）
            prev=self._to_out(prev) if prev else None,
            next=self._to_out(nxt) if nxt else None,
            related_laws=[self._to_out(r) for r in related],
            related_interpretations=interps,
            related_cases=cases,
            recommendations=[self._to_out(r) for r in recs],
        )

    # --------------------------- 推荐 ---------------------------
    async def recommend(self, law_id=None, limit: int = 6) -> list[LawOut]:
        if law_id:
            law = await self.law.get_by_id(law_id)
            if not law:
                return []
            sibs = await self.law.get_siblings(
                law.law_name, exclude_id=law.id, limit=limit
            )
            if len(sibs) >= limit:
                return [self._to_out(s) for s in sibs]
            more = await self.law.get_related_by_keywords(
                law.keywords, law.id, limit=limit - len(sibs)
            )
            return [self._to_out(s) for s in sibs] + [
                self._to_out(m) for m in more
            ]
        latest = await self.law.get_latest(limit)
        return [self._to_out(item) for item in latest]

    # --------------------------- 历史 ---------------------------
    async def history(self, current_user: User, limit: int = 20) -> list[LawHistoryOut]:
        rows = await self.history.list_recent_by_user(current_user.id, limit)
        return [LawHistoryOut.model_validate(r) for r in rows]

    # --------------------------- 工具 ---------------------------
    @staticmethod
    def _status_val(status):
        return status.value if isinstance(status, LawStatusEnum) else status

    @staticmethod
    def _to_out(law: Law) -> LawOut:
        return LawOut(
            id=law.id,
            law_name=law.law_name,
            chapter=law.chapter,
            section=law.section,
            article=law.article,
            content=law.content,
            keywords=law.keywords,
            effective_date=law.effective_date,
            status=LawSearchService._status_val(law.status),
            source=law.source,
        )

    @staticmethod
    def _split_legal_references(refs):
        interps, cases = [], []
        for r in refs:
            src = r.source.value if hasattr(r.source, "value") else r.source
            item = {
                "id": str(r.id),
                "source": src,
                "title": r.title,
                "article": r.article,
                "snippet": (r.content or "")[:160],
            }
            if src == "judicial_interpretation":
                interps.append(item)
            else:
                cases.append(item)
        return interps, cases

    @staticmethod
    def _highlight(text: str, terms: list[str], window: int = 90) -> str:
        """生成带 <mark> 的高亮摘要（中文友好，子串匹配）。"""
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
                re.escape(t),
                lambda m: f"<mark>{m.group(0)}</mark>",
                snippet,
                flags=re.I,
            )
        return ("…" if start > 0 else "") + snippet + ("…" if end < len(text) else "")
