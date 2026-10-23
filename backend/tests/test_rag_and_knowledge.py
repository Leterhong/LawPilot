"""RAG 检索与法律知识库测试。

重点验证"可核验性"这一参赛核心主张：
- 混合检索的 RRF 融合必须得分单调、可解释、同源去重；
- 引用必须可回溯（带 source_table / id / label），不允许凭空生成；
- 8 类案由的追问脚本与知识模板必须完整，不能有空壳分支。
"""
from __future__ import annotations

import uuid

import pytest

from app.models.enums import CaseTypeEnum, LegalSourceEnum
from app.services.agent import knowledge_base as kb
from app.services.rag.citations import build_citation, build_citations, format_legal_basis
from app.services.rag.retriever import HybridRetriever, RetrievedChunk


def _chunk(title: str, *, table: str = "legal_reference", vec: float | None = None,
           kw: float | None = None, article: str | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        id=uuid.uuid4(),
        source_table=table,
        source=LegalSourceEnum.LAW,
        title=title,
        content=f"{title} 的正文内容，用于验证摘要截断与引用渲染。",
        article=article,
        vector_score=vec,
        keyword_score=kw,
        citation=title,
    )


class TestReciprocalRankFusion:
    """RRF 是混合检索的核心，必须保证可解释性。"""

    def test_single_chunk_ranked_first(self) -> None:
        a = _chunk("A")
        fused = HybridRetriever._rrf_fuse([[a]])
        assert [c.title for c in fused] == ["A"]
        assert fused[0].score == pytest.approx(1.0 / 61)

    def test_scores_are_monotonically_decreasing(self) -> None:
        fused = HybridRetriever._rrf_fuse([[_chunk("A"), _chunk("B"), _chunk("C")]])
        scores = [c.score for c in fused]
        assert scores == sorted(scores, reverse=True)

    def test_same_item_in_both_lists_accumulates_score(self) -> None:
        """同一法条同时被向量与关键词召回时，得分应高于只被单路召回者。"""
        shared = _chunk("共同命中")
        only_vec = _chunk("仅向量命中")
        fused = HybridRetriever._rrf_fuse([[shared, only_vec], [shared, _chunk("仅关键词命中")]])
        by_title = {c.title: c for c in fused}
        assert by_title["共同命中"].score > by_title["仅向量命中"].score
        assert fused[0].title == "共同命中"

    def test_duplicates_across_tables_are_not_merged(self) -> None:
        """去重键是 (source_table, id)，不同表同 id 不应合并。"""
        same_id = uuid.uuid4()
        a = RetrievedChunk(id=same_id, source_table="legal_reference",
                           source=LegalSourceEnum.LAW, title="条文", content="x")
        b = RetrievedChunk(id=same_id, source_table="knowledge",
                           source=LegalSourceEnum.LAW, title="知识", content="y")
        fused = HybridRetriever._rrf_fuse([[a], [b]])
        assert len(fused) == 2

    def test_best_sub_scores_are_preserved(self) -> None:
        a1 = _chunk("X", vec=0.72, kw=None)
        a2 = RetrievedChunk(id=a1.id, source_table=a1.source_table,
                            source=a1.source, title="X", content="c",
                            vector_score=0.91, keyword_score=1.0)
        fused = HybridRetriever._rrf_fuse([[a1], [a2]])
        assert fused[0].vector_score == pytest.approx(0.91)
        assert fused[0].keyword_score == pytest.approx(1.0)

    def test_empty_input_is_safe(self) -> None:
        assert HybridRetriever._rrf_fuse([]) == []
        assert HybridRetriever._rrf_fuse([[], []]) == []


class TestCitations:
    def test_citation_is_traceable(self) -> None:
        c = _chunk("《民法典》 第577条", article="第577条")
        data = build_citation(c)
        # 可回溯所需的最小字段集合
        for key in ("id", "source_table", "source", "label", "title", "snippet", "score"):
            assert key in data
        assert data["source_table"] == "legal_reference"
        assert data["label"]

    def test_snippet_is_truncated(self) -> None:
        c = _chunk("长文")
        c.content = "法" * 500
        assert len(c.to_snippet(160)) == 161  # 160 + 省略号
        assert c.to_snippet(160).endswith("…")

    def test_snippet_kept_whole_when_short(self) -> None:
        c = _chunk("短文")
        assert c.to_snippet(160) == c.content

    def test_batch_order_preserved(self) -> None:
        chunks = [_chunk("A"), _chunk("B"), _chunk("C")]
        assert [c["title"] for c in build_citations(chunks)] == ["A", "B", "C"]

    def test_format_legal_basis_limits_items(self) -> None:
        md = format_legal_basis([_chunk(f"条文{i}") for i in range(10)], max_items=5)
        assert len(md.splitlines()) == 5
        assert md.startswith("- **")

    def test_format_legal_basis_empty(self) -> None:
        assert format_legal_basis([]) == ""


class TestKnowledgeBaseCompleteness:
    """8 类案由都不能是空壳，否则用户走到该分支会拿不到任何指引。"""

    ALL_TYPES = list(CaseTypeEnum)

    def test_every_case_type_has_question_script(self) -> None:
        for ct in self.ALL_TYPES:
            script = kb.script_for(ct)
            assert script, f"{ct} 缺少追问脚本"
            assert all(q.id and q.text for q in script), f"{ct} 存在空问题"

    def test_every_case_type_has_core_templates(self) -> None:
        for ct in self.ALL_TYPES:
            assert kb.CONCLUSION.get(ct), f"{ct} 缺少一句话结论"
            assert kb.RIGHTS.get(ct), f"{ct} 缺少权益分析"
            assert kb.COUNTERPARTY.get(ct), f"{ct} 缺少对方问题分析"
            assert kb.RISK_NOTES.get(ct), f"{ct} 缺少风险提示"

    def test_case_type_labels_cover_all(self) -> None:
        assert set(kb.CASE_TYPE_LABELS) == set(self.ALL_TYPES)

    def test_question_ids_are_unique_within_script(self) -> None:
        """重复 id 会导致 Agent 覆盖已收集字段，造成事实丢失。"""
        for ct in self.ALL_TYPES:
            ids = [q.id for q in kb.script_for(ct)]
            assert len(ids) == len(set(ids)), f"{ct} 追问脚本存在重复 id"

    def test_options_are_non_empty_when_present(self) -> None:
        for ct in self.ALL_TYPES:
            for q in kb.script_for(ct):
                if q.options is not None:
                    assert q.options, f"{ct}/{q.id} 的 options 为空列表"


class TestLegalQueryConstruction:
    def test_query_includes_case_label_and_description(self, sample_case) -> None:
        q = kb.build_legal_query(sample_case)
        assert "房屋租赁纠纷" in q
        assert "押金" in q

    def test_query_truncates_long_description(self, sample_case) -> None:
        sample_case.description = "租" * 500
        q = kb.build_legal_query(sample_case)
        # 标签 + 空格 + 120 字以内
        assert len(q) <= len("房屋租赁纠纷") + 1 + 120

    def test_query_falls_back_to_label(self, sample_case) -> None:
        sample_case.description = ""
        sample_case.title = ""
        assert kb.build_legal_query(sample_case) == "房屋租赁纠纷"
