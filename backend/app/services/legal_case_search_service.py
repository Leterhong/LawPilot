"""案例搜索服务（Legal Case Search 模块）。

第二步实现基础检索：BM25 + pgvector 混合 + Reranker 重排 + 过滤 + 详情关联法条
+ 收藏 + 相似案例（AI 提取关键词，无 key 时优雅降级为原文检索）。
第四步将升级 AI 相似度总结（ai_summary 字段已预留）。
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CourtLevelEnum, LegalCaseTypeEnum
from app.models.legal_case import LegalCase
from app.models.user import User
from app.repositories.law_repo import LawRepository
from app.repositories.legal_case_repo import LegalCaseRepository
from app.schemas.legal_case import (
    CaseFilterFacets,
    FacetItem,
    LegalCaseAiSummary,
    LegalCaseDetail,
    LegalCaseSearchItem,
    LegalCaseSearchResult,
    SimilarCaseRequest,
)
from app.schemas.law import LawOut
from app.services.case_center_service import CaseCenterService
from app.services.llm.client import LLMClient
from app.services.rag.reranker import RerankerService

# 过滤面中文标签
_COURT_LEVEL_LABELS = {
    CourtLevelEnum.BASIC.value: "基层人民法院",
    CourtLevelEnum.INTERMEDIATE.value: "中级人民法院",
    CourtLevelEnum.ADVANCED.value: "高级人民法院",
    CourtLevelEnum.SUPREME.value: "最高人民法院",
}
_CASE_TYPE_LABELS = {
    LegalCaseTypeEnum.CIVIL.value: "民事",
    LegalCaseTypeEnum.LABOR.value: "劳动",
    LegalCaseTypeEnum.CONTRACT.value: "合同",
    LegalCaseTypeEnum.CONSUMER.value: "消费",
    LegalCaseTypeEnum.OTHER.value: "其他",
}
_TIME_RANGE_LABELS = {
    "1y": "近一年",
    "5y": "近五年",
    "all": "全部",
}


class LegalCaseSearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.cases = LegalCaseRepository(session)
        self.laws = LawRepository(session)
        self.reranker = RerankerService()
        self.llm = LLMClient(db=self.session, feature="case_search")

    # --------------------------- 搜索 ---------------------------
    async def search(
        self,
        q: str,
        *,
        province: Optional[str] = None,
        city: Optional[str] = None,
        court_level: Optional[str] = None,
        case_type: Optional[str] = None,
        time_range: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> LegalCaseSearchResult:
        ranked, total, parsed = await self.cases.search(
            q,
            province=province,
            city=city,
            court_level=court_level,
            case_type=case_type,
            time_range=time_range,
            limit=limit,
            offset=offset,
        )
        terms = list(parsed.get("terms") or [])

        # 重排：对融合候选做 Reranker（远程优先，否则词法 bigram 重叠度）
        if ranked:
            pairs = [
                (
                    str(c.id),
                    f"{c.title} {c.cause_of_action or ''} {(c.facts or '')[:200]} "
                    f"{(c.court_reasoning or '')[:200]}",
                )
                for c, _ in ranked
            ]
            try:
                reranked = await self.reranker.rerank_pairs(q, pairs)
                order = {pid: sc for pid, sc in reranked}
                ranked = sorted(
                    [(c, order.get(str(c.id), 0.0)) for c, _ in ranked],
                    key=lambda cs: cs[1],
                    reverse=True,
                )
            except Exception:
                pass

        page = ranked[offset : offset + limit]
        out = [self._to_item(c, terms, score=score) for c, score in page]
        return LegalCaseSearchResult(
            query=q,
            total=total,
            items=out,
            parsed=parsed,
            filters=parsed.get("filters"),
        )

    def _to_item(
        self, case: LegalCase, terms: list[str], score: Optional[float] = None
    ) -> LegalCaseSearchItem:
        snippet = self._build_snippet(case, terms)
        return LegalCaseSearchItem(
            id=case.id,
            title=case.title,
            case_number=case.case_number,
            court=case.court,
            province=case.province,
            city=case.city,
            trial_date=case.trial_date,
            case_type=self._enum_val(case.case_type),
            court_level=self._enum_val(case.court_level),
            cause_of_action=case.cause_of_action,
            plaintiff=case.plaintiff,
            defendant=case.defendant,
            winner=case.winner,
            compensation=case.compensation,
            keywords=case.keywords,
            related_laws=case.related_laws,
            source=case.source,
            snippet=snippet,
            score=score,
            highlight={
                "title": self._highlight(case.title or "", terms),
                "facts": snippet,
            },
        )

    # --------------------------- 详情 ---------------------------
    async def detail(self, case_id) -> Optional[LegalCaseDetail]:
        case = await self.cases.get_by_id(case_id)
        if not case:
            return None
        # 关联法律库（动态关联真实法条，可链 /laws/{id}）
        kw = case.keywords or ([case.cause_of_action] if case.cause_of_action else [])
        related = await self.laws.get_related_by_keywords(kw, exclude_id=None, limit=6)
        # 第四步：AI 相似度总结（similar_points/different_points/reference_value）。
        # 无 LLM key 时 _ai_summary 返回 None，前端展示占位提示，纯只读、不落库。
        ai_summary = await self._ai_summary(case)
        return LegalCaseDetail(
            id=case.id,
            title=case.title,
            case_number=case.case_number,
            court=case.court,
            province=case.province,
            city=case.city,
            trial_date=case.trial_date,
            case_type=self._enum_val(case.case_type),
            court_level=self._enum_val(case.court_level),
            cause_of_action=case.cause_of_action,
            plaintiff=case.plaintiff,
            defendant=case.defendant,
            winner=case.winner,
            compensation=case.compensation,
            keywords=case.keywords,
            source=case.source,
            facts=case.facts,
            court_reasoning=case.court_reasoning,
            judgement=case.judgement,
            related_laws=[LawOut.model_validate(r) for r in related],
            related_law_citations=case.related_laws,
            ai_summary=ai_summary,
        )

    # --------------------------- 过滤面 ---------------------------
    async def filter_facets(self) -> CaseFilterFacets:
        provinces = await self.cases.distinct_provinces()
        cities = await self.cases.distinct_cities()
        return CaseFilterFacets(
            provinces=provinces,
            cities=cities,
            court_levels=[
                FacetItem(value=v, label=_COURT_LEVEL_LABELS.get(v, v))
                for v in [e.value for e in CourtLevelEnum]
            ],
            case_types=[
                FacetItem(value=v, label=_CASE_TYPE_LABELS.get(v, v))
                for v in [e.value for e in LegalCaseTypeEnum]
            ],
            time_ranges=[
                FacetItem(value=v, label=_TIME_RANGE_LABELS.get(v, v))
                for v in ["1y", "5y", "all"]
            ],
        )

    # --------------------------- 相似案例 ---------------------------
    async def similar(
        self, body: SimilarCaseRequest, current_user: Optional[User] = None
    ) -> LegalCaseSearchResult:
        """根据用户的案件（或查询文本）查找相似案例 TOP N。

        有 LLM key 时自动提取关键词构建检索式；否则以原始文本检索（优雅降级）。
        """
        context, source_label = await self._build_similar_context(body, current_user)
        if not context:
            return LegalCaseSearchResult(
                query="", total=0, items=[], parsed={"error": "缺少 case_id 或 query"}
            )

        query = context
        if await self.llm.available_async():
            extracted = await self._extract_query(context)
            if extracted:
                query = extracted

        result = await self.search(query, limit=body.limit or 10)
        result.parsed = {**(result.parsed or {}), "similar_source": source_label}
        return result

    async def _build_similar_context(
        self, body: SimilarCaseRequest, current_user: Optional[User]
    ) -> tuple[str, str]:
        if body.case_id and current_user is not None:
            case = await CaseCenterService(self.session).get_owned(
                body.case_id, current_user
            )
            if case is None:
                return "", "case_not_found"
            ctx = f"{case.title}\n{case.description or ''}\n案件类型：{self._enum_val(case.case_type)}"
            return ctx.strip(), "case"
        if body.query:
            return body.query.strip(), "query"
        return "", "none"

    async def _ai_summary(self, case: LegalCase) -> Optional[LegalCaseAiSummary]:
        """AI 对本案例的通用相似度总结（相似点 / 不同点 / 参考价值）。

        仅依赖案例自身字段，给出「办理同类案件时的可借鉴之处」。
        无 LLM key 或调用失败时优雅降级为 None（前端展示占位提示）。
        """
        if not await self.llm.available_async():
            return None
        brief = (
            f"标题：{case.title}\n"
            f"案由：{case.cause_of_action or '—'}\n"
            f"当事人：原告 {case.plaintiff or '—'} / 被告 {case.defendant or '—'}\n"
            f"法院：{case.court or '—'}\n"
            f"案件事实：{(case.facts or '')[:1500]}\n"
            f"法院观点：{(case.court_reasoning or '')[:1500]}\n"
            f"裁判结果：{(case.judgement or '')[:800]}\n"
        )
        prompt = (
            "你是一个资深法律检索助手。请基于下面这份裁判文书，提炼出对未来办理"
            "同类案件的参考价值，输出 JSON：\n"
            "{\"similar_points\": \"这类案件的共性要点（事实认定、争议焦点、举证要点等）\", "
            "\"different_points\": \"个案之间的差异与边界（可能影响结果的关键变量）\", "
            "\"reference_value\": \"参考价值：高/中/低，并一句话说明理由\", "
            "\"raw\": \"以上三点的完整原文\"}\n"
            "只输出 JSON，不要解释。\n\n"
            f"{brief}"
        )
        try:
            data = await self.llm.complete_json(prompt)
        except Exception:
            return None
        if not data:
            return None
        return LegalCaseAiSummary(
            similar_points=data.get("similar_points"),
            different_points=data.get("different_points"),
            reference_value=data.get("reference_value"),
            raw=data.get("raw"),
        )

    async def _extract_query(self, context: str) -> Optional[str]:
        """用 LLM 从案件描述中提取检索关键词；失败返回 None（降级为原文检索）。"""
        prompt = (
            "你是一个法律案例检索助手。请从下面的案件描述中提取用于检索相似裁判文书的"
            "关键词与检索式。\n\n"
            f"案件描述：\n{context}\n\n"
            "请返回 JSON：{\"keywords\": [\"关键词1\",\"关键词2\"], "
            "\"query\": \"用于检索的一句话，包含核心案由与争议焦点\"}。"
            "只输出 JSON，不要解释。"
        )
        try:
            data = await self.llm.complete_json(prompt)
        except Exception:
            return None
        if not data:
            return None
        keywords = data.get("keywords") or []
        query = data.get("query")
        if query:
            return query
        if keywords:
            return " ".join([str(k) for k in keywords])
        return None

    # --------------------------- 收藏 ---------------------------
    async def add_favorite(self, user: User, case_id) -> bool:
        case = await self.cases.get_by_id(case_id)
        if not case:
            return False
        await self.cases.add_favorite(user.id, case_id)
        await self.session.commit()
        return True

    async def remove_favorite(self, user: User, case_id) -> bool:
        case = await self.cases.get_by_id(case_id)
        if not case:
            return False
        await self.cases.remove_favorite(user.id, case_id)
        await self.session.commit()
        return True

    async def list_favorites(self, user: User) -> LegalCaseSearchResult:
        rows = await self.cases.list_favorites(user.id)
        items = [
            self._to_item(c, [], score=None) for c in rows
        ]
        return LegalCaseSearchResult(query="", total=len(items), items=items)

    # --------------------------- 工具 ---------------------------
    @staticmethod
    def _enum_val(v):
        return v.value if hasattr(v, "value") else v

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

    @staticmethod
    def _build_snippet(case: LegalCase, terms: list[str]) -> str:
        """选择最能反映案情的正文字段做高亮摘要。"""
        for field in (case.facts, case.court_reasoning, case.judgement):
            if field:
                return LegalCaseSearchService._highlight(field, terms)
        return LegalCaseSearchService._highlight(case.title or "", terms)
