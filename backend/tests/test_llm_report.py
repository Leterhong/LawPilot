"""个性化报告分析测试（防幻觉闸门）。

这三道闸门是本产品在法律场景下可被信任的前提，必须有自动化证据支撑：
1. 事实封闭 —— 只使用用户亲口陈述的内容；
2. 法条封闭 —— 只能引用给定编号，越界即整段作废；
3. 结构可校验 —— 输出不合规一律回退模板，绝不把坏数据写进报告。
"""
from __future__ import annotations

import json
from typing import Any, Optional

import pytest

from app.models.enums import CaseTypeEnum
from app.models.workflow import Workflow
from app.services.agent.llm_report import (
    SYSTEM_PROMPT,
    PersonalizedAnalysis,
    build_fact_lines,
    build_prompt,
    generate_personalized_analysis,
    validate_sections,
)

CITATIONS = [
    {"label": "《民法典》 第577条", "snippet": "当事人一方不履行合同义务，应当承担违约责任。"},
    {"label": "《民法典》 第703条", "snippet": "租赁合同是出租人将租赁物交付承租人使用、收益的合同。"},
    {"label": "《民法典》 第721条", "snippet": "承租人应当按照约定的期限支付租金。"},
]

GOOD = {
    "conclusion": "房东无权以房屋污渍为由全额扣押金，您可先协商再投诉。",
    "rights": "依据【法条1】与【法条2】，您有权要求返还押金并主张逾期利息。",
    "counterparty_issues": "房东以非约定理由拒退，违反【法条2】项下的返还义务。",
    "risk_suggestion": "注意保留入住与退租时的房屋状况证据，避免举证不利。",
    "evidence_advice": "补充退租时的交房照片与聊天记录，固定房东拒退的原话。",
}


class StubLLM:
    """可控的 LLM 替身，用于覆盖各条降级路径。"""

    def __init__(self, *, available: bool = True, reply: Optional[str] = None,
                 raises: Optional[Exception] = None) -> None:
        self._available = available
        self._reply = reply
        self._raises = raises
        self.calls: list[str] = []

    async def available_async(self, feature: str | None = None) -> bool:
        return self._available

    async def complete(self, prompt: str, **kwargs: Any) -> Optional[str]:
        self.calls.append(prompt)
        if self._raises:
            raise self._raises
        return self._reply


@pytest.fixture
def workflow() -> Workflow:
    return Workflow(
        case_id="case-1",
        collected_fields={
            "has_contract": "签订了",
            "deposit": "8000 元，有转账记录",
            "issue": "无故扣押金",
        },
        missing_fields=[],
    )


class TestFactExtraction:
    def test_facts_use_original_question_text(self, sample_case, workflow) -> None:
        lines = build_fact_lines(sample_case, workflow)
        assert len(lines) == 3
        # 应还原为人话，而不是暴露 has_contract 这类内部字段名
        assert any("是否签订了书面租赁合同" in ln for ln in lines)
        assert not any("has_contract" in ln for ln in lines)

    def test_empty_answers_are_skipped(self, sample_case, workflow) -> None:
        workflow.collected_fields = {"has_contract": "签订了", "deposit": "   "}
        assert len(build_fact_lines(sample_case, workflow)) == 1

    def test_none_workflow_is_safe(self, sample_case) -> None:
        assert build_fact_lines(sample_case, None) == []

    def test_prompt_contains_facts_and_law_numbers(self, sample_case, workflow) -> None:
        prompt = build_prompt(sample_case, build_fact_lines(sample_case, workflow), CITATIONS)
        assert "【法条1】" in prompt and "【法条3】" in prompt
        assert "8000 元" in prompt
        assert "房屋租赁纠纷" in prompt

    def test_prompt_without_citations_forbids_fabrication(self, sample_case, workflow) -> None:
        prompt = build_prompt(sample_case, build_fact_lines(sample_case, workflow), [])
        assert "不要编造" in prompt


class TestValidationGates:
    def test_good_payload_passes(self) -> None:
        sections, error = validate_sections(json.loads(json.dumps(GOOD)), len(CITATIONS))
        assert error == ""
        assert sections is not None
        assert sections["_cited"] == [1, 2]

    @pytest.mark.parametrize("field", ["conclusion", "rights", "counterparty_issues",
                                       "risk_suggestion", "evidence_advice"])
    def test_missing_field_rejected(self, field: str) -> None:
        payload = dict(GOOD)
        payload.pop(field)
        sections, error = validate_sections(payload, len(CITATIONS))
        assert sections is None
        assert field in error

    def test_blank_field_rejected(self) -> None:
        payload = dict(GOOD, rights="   ")
        sections, error = validate_sections(payload, len(CITATIONS))
        assert sections is None

    @pytest.mark.parametrize("bad", ["【法条4】", "【法条99】", "【法条0】"])
    def test_out_of_range_citation_rejected(self, bad: str) -> None:
        """核心防幻觉断言：引用不存在的法条编号必须整段作废。"""
        payload = dict(GOOD, rights=f"依据{bad}，您有权主张返还。")
        sections, error = validate_sections(payload, len(CITATIONS))
        assert sections is None
        assert "不存在的法条编号" in error

    def test_no_citation_allowed_when_kb_empty(self) -> None:
        payload = dict(GOOD, rights="依据【法条1】，您有权主张返还。")
        sections, error = validate_sections(payload, 0)
        assert sections is None

    def test_overlong_section_is_truncated(self) -> None:
        payload = dict(GOOD, rights="权" * 2000)
        sections, _ = validate_sections(payload, len(CITATIONS))
        assert sections is not None
        assert len(sections["rights"]) <= 601
        assert sections["rights"].endswith("…")


class TestGeneratePersonalizedAnalysis:
    async def test_success_path(self, sample_case, workflow) -> None:
        llm = StubLLM(reply=json.dumps(GOOD, ensure_ascii=False))
        result = await generate_personalized_analysis(sample_case, workflow, CITATIONS, llm)
        assert result.is_llm
        assert result.cited == [1, 2]
        assert result.sections["conclusion"] == GOOD["conclusion"]
        assert len(llm.calls) == 1

    async def test_tolerates_markdown_fence(self, sample_case, workflow) -> None:
        fenced = "```json\n" + json.dumps(GOOD, ensure_ascii=False) + "\n```"
        result = await generate_personalized_analysis(
            sample_case, workflow, CITATIONS, StubLLM(reply=fenced)
        )
        assert result.is_llm

    async def test_no_key_skips_model_call(self, sample_case, workflow) -> None:
        llm = StubLLM(available=False, reply=json.dumps(GOOD))
        result = await generate_personalized_analysis(sample_case, workflow, CITATIONS, llm)
        assert not result.is_llm
        assert "密钥" in result.reason
        assert llm.calls == []

    async def test_broken_json_falls_back(self, sample_case, workflow) -> None:
        result = await generate_personalized_analysis(
            sample_case, workflow, CITATIONS, StubLLM(reply="抱歉，我无法回答")
        )
        assert not result.is_llm
        assert "JSON" in result.reason

    async def test_hallucinated_citation_falls_back(self, sample_case, workflow) -> None:
        payload = dict(GOOD, rights="依据【法条7】，房东应双倍返还押金。")
        result = await generate_personalized_analysis(
            sample_case, workflow, CITATIONS,
            StubLLM(reply=json.dumps(payload, ensure_ascii=False)),
        )
        assert not result.is_llm
        assert "不存在的法条编号" in result.reason

    async def test_exception_falls_back_without_raising(self, sample_case, workflow) -> None:
        result = await generate_personalized_analysis(
            sample_case, workflow, CITATIONS, StubLLM(raises=TimeoutError("model timeout"))
        )
        assert not result.is_llm
        assert "异常" in result.reason

    async def test_empty_reply_falls_back(self, sample_case, workflow) -> None:
        result = await generate_personalized_analysis(
            sample_case, workflow, CITATIONS, StubLLM(reply=None)
        )
        assert not result.is_llm


class TestPromptSafety:
    def test_system_prompt_states_all_three_gates(self) -> None:
        assert "只能使用" in SYSTEM_PROMPT        # 事实封闭
        assert "【法条N】" in SYSTEM_PROMPT        # 法条封闭
        assert "只输出 JSON" in SYSTEM_PROMPT      # 结构可校验

    def test_fallback_result_has_template_source(self) -> None:
        assert PersonalizedAnalysis().source == "template"
