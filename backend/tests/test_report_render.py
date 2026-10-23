"""案件报告渲染测试。

报告是本产品交付给用户的最终产物，"涉及法律"章节必须满足：
- 有结果时渲染为可读列表且不超过 5 条；
- 无结果时给出明确降级提示，而不是空白或编造条文。
"""
from __future__ import annotations

import pytest

from app.services.agent.report import DOC_TYPE_LABELS, _format_legal_markdown
from app.models.enums import DocTypeEnum
from app.services.agent.prompts import DISCLAIMER


class TestLegalMarkdown:
    def test_empty_citations_gives_actionable_fallback(self) -> None:
        md = _format_legal_markdown([])
        assert "暂未检索到" in md
        # 不能出现虚构条文的痕迹
        assert "第" not in md

    def test_renders_up_to_five_items(self) -> None:
        citations = [
            {"label": f"《民法典》 第{i}条", "snippet": f"条文{i}摘要"} for i in range(9)
        ]
        md = _format_legal_markdown(citations)
        lines = md.splitlines()
        assert len(lines) == 5
        assert lines[0].startswith("- **《民法典》 第0条**：")

    def test_falls_back_to_title_when_label_missing(self) -> None:
        md = _format_legal_markdown([{"title": "《劳动合同法》 第38条", "snippet": "摘要"}])
        assert "《劳动合同法》 第38条" in md

    def test_handles_missing_snippet(self) -> None:
        md = _format_legal_markdown([{"label": "某条文"}])
        assert md.strip().endswith("：")


class TestReportMetadata:
    def test_every_doc_type_has_chinese_label(self) -> None:
        for doc_type in DocTypeEnum:
            assert doc_type in DOC_TYPE_LABELS, f"{doc_type} 缺少中文标签"

    def test_disclaimer_states_scope_and_limits(self) -> None:
        """免责声明必须同时说明"不构成法律意见"与"建议咨询律师"。"""
        assert "不构成法律意见" in DISCLAIMER
        assert "律师" in DISCLAIMER

    @pytest.mark.parametrize("keyword", ["仅供办事参考", "AI"])
    def test_disclaimer_discloses_ai_generation(self, keyword: str) -> None:
        assert keyword in DISCLAIMER
