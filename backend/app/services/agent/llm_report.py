"""LLM 驱动的案件报告个性化分析。

背景与设计动机
--------------
早期版本（Phase 6）的报告正文全部来自 ``knowledge_base`` 的静态模板：
同一案由的用户，无论陈述了什么事实，都会拿到一字不差的「我的权益」「对方
可能存在的问题」「风险分析」。这使得报告与个案脱节，也让"AI 在该产品中承担
什么核心作用"难以成立。

本模块把「已收集事实」与「RAG 检索到的法条」一起输入模型，生成与个案强相关
的分析，同时用三道闸门约束幻觉：

1. **事实封闭**：只允许使用 ``collected`` 中用户亲口陈述的内容，不得补充虚构细节；
2. **法条封闭**：只能引用传入的 citation 列表，并以 ``【法条N】`` 标注出处，
   出现列表之外的编号即判定为越界；
3. **结构可校验**：要求模型返回严格 JSON，字段缺失、解析失败、引用越界
   任意一条不满足，立即整体回退到确定性模板。

因此本模块是"增强"而非"依赖"：没有 LLM 密钥、模型超时、输出不合规时，
产品行为与升级前完全一致，不会出现降级为空白报告的情况。
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.models.case import Case
from app.models.workflow import Workflow
from app.services.agent.knowledge_base import CASE_TYPE_LABELS, script_for
from app.services.llm.client import LLMClient

logger = logging.getLogger("lawpilot.agent.report")

# 允许模型生成的分析字段（与报告章节一一对应）
_SECTIONS = (
    "conclusion",           # 一句话结论
    "rights",               # 我的权益
    "counterparty_issues",  # 对方可能存在的问题
    "risk_suggestion",      # 风险与应对建议
    "evidence_advice",      # 针对本案的证据补充建议
)

# 报告正文的长度上限（字符），防止模型输出冗长导致前端排版失衡
_MAX_SECTION_CHARS = 600

# 引用编号形如 【法条1】【法条3】
_CITATION_RE = re.compile(r"【法条\s*(\d+)\s*】")

SYSTEM_PROMPT = (
    "你是一名严谨的中国法律事务助理，服务对象是完全不懂法律的普通群众。"
    "你的任务是基于用户自述的事实，给出清晰、可执行、通俗易懂的分析。\n"
    "硬性约束（违反即视为回答失败）：\n"
    "1. 只能使用「案情事实」中出现的信息，不得臆测或补充任何未提及的细节；\n"
    "2. 引用法律依据时，只能从「可用法条」中选择，格式必须为【法条N】，N 为给定编号；"
    "不得引用列表之外的法条，不得编造法条名称或条号；\n"
    "3. 不确定的地方必须明确说明「需进一步确认」，不得伪装确定；\n"
    "4. 只输出 JSON，不要输出 Markdown 代码块、解释性文字或任何前后缀。"
)

_OUTPUT_SPEC = """请严格输出如下 JSON 结构（每个字段 60-220 字，中文，口语化但不失专业）：
{{
  "conclusion": "一句话结论：用户本案的核心定性 + 最优维权路径",
  "rights": "我的权益：结合具体事实与法条，说明用户依法可以主张什么、金额或范围如何估算",
  "counterparty_issues": "对方可能存在的问题：结合具体事实指出对方违反了哪些义务，可能承担什么责任",
  "risk_suggestion": "风险与应对建议：本案的主要风险点（时效、举证、执行等）与规避办法",
  "evidence_advice": "针对本案还需补充哪些关键证据，以及如何固定"
}}"""


@dataclass
class PersonalizedAnalysis:
    """个性化分析结果。

    :param sections: 五个章节的正文
    :param source: ``llm`` 表示由模型生成，``template`` 表示回退到静态模板
    :param reason: 回退原因（便于线上排查与评测统计）
    :param cited: 本次分析实际引用的法条编号（升序）
    """

    sections: dict[str, str] = field(default_factory=dict)
    source: str = "template"
    reason: str = ""
    cited: List[int] = field(default_factory=list)

    @property
    def is_llm(self) -> bool:
        return self.source == "llm"


def build_fact_lines(case: Case, workflow: Optional[Workflow]) -> List[str]:
    """把结构化事实还原为「问题 → 回答」的可读列表。

    使用追问脚本的原问题文本而非字段 id，避免维护额外的 id→中文映射，
    也保证模型看到的语义与用户实际看到的措辞一致。
    """
    collected = dict(getattr(workflow, "collected_fields", None) or {})
    if not collected:
        return []

    label_by_id = {q.id: q.text for q in script_for(case.case_type)}
    lines: List[str] = []
    for qid, answer in collected.items():
        text = (answer or "").strip() if isinstance(answer, str) else str(answer)
        if not text:
            continue
        question = label_by_id.get(qid, qid)
        lines.append(f"- {question} → {text}")
    return lines


def build_prompt(
    case: Case,
    fact_lines: List[str],
    citations: List[dict],
) -> str:
    """构造分析请求。"""
    label = CASE_TYPE_LABELS.get(case.case_type, "纠纷")
    facts = "\n".join(fact_lines) or "（用户未提供结构化事实，仅有自由描述）"
    desc = (case.description or "").strip() or "（无）"
    laws = (
        "\n".join(
            f"【法条{i}】{c.get('label') or c.get('title') or '法条'}：{c.get('snippet') or ''}"
            for i, c in enumerate(citations, start=1)
        )
        or "（未检索到相关法条，此时不要编造任何法条，只做事实层面的分析）"
    )
    return (
        f"案件类型：{label}\n"
        f"用户原始描述：{desc}\n"
        f"案情事实（来自逐条追问，用户亲口陈述）：\n{facts}\n\n"
        f"可用法条（仅可引用以下编号）：\n{laws}\n\n"
        f"{_OUTPUT_SPEC}"
    )


def _strip_code_fence(text: str) -> str:
    """容忍模型仍返回 ```json ... ``` 的情况。"""
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _extract_json_object(text: str) -> Optional[dict]:
    """从模型输出中提取第一个 JSON 对象。"""
    raw = _strip_code_fence(text)
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def validate_sections(
    data: dict, citation_count: int
) -> tuple[Optional[dict[str, str]], str]:
    """校验模型输出。返回 (清洗后的章节, 失败原因)。"""
    sections: dict[str, str] = {}
    for key in _SECTIONS:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            return None, f"字段 {key} 缺失或为空"
        text = value.strip()
        if len(text) > _MAX_SECTION_CHARS:
            text = text[:_MAX_SECTION_CHARS].rstrip() + "…"
        sections[key] = text

    # 引用越界检查：出现 [1, citation_count] 之外的编号即判定为编造
    cited: set[int] = set()
    for key in _SECTIONS:
        for num in _CITATION_RE.findall(sections[key]):
            idx = int(num)
            if idx < 1 or idx > citation_count:
                return None, f"字段 {key} 引用了不存在的法条编号 {idx}（可用 1-{citation_count}）"
            cited.add(idx)

    sections["_cited"] = sorted(cited)  # type: ignore[assignment]
    return sections, ""


async def generate_personalized_analysis(
    case: Case,
    workflow: Optional[Workflow],
    citations: List[dict],
    llm: LLMClient,
) -> PersonalizedAnalysis:
    """生成个性化分析；任何一步不满足约束都回退到模板。

    本函数不抛异常，保证 Agent 主流程稳定。
    """
    try:
        if not await llm.available_async("agent_report"):
            return PersonalizedAnalysis(reason="未配置可用的大模型密钥")

        fact_lines = build_fact_lines(case, workflow)
        if not fact_lines and not (case.description or case.title):
            return PersonalizedAnalysis(reason="缺少可用的案情事实")

        prompt = build_prompt(case, fact_lines, citations)
        raw = await llm.complete(prompt, system=SYSTEM_PROMPT, json_mode=True)
        if not raw:
            return PersonalizedAnalysis(reason="模型返回空结果")

        data = _extract_json_object(raw)
        if data is None:
            return PersonalizedAnalysis(reason="模型输出无法解析为 JSON")

        sections, error = validate_sections(data, len(citations))
        if sections is None:
            return PersonalizedAnalysis(reason=error)

        cited = sections.pop("_cited", [])  # type: ignore[arg-type]
        logger.info(
            "报告个性化分析生成成功 case=%s sections=%d cited=%s",
            case.id, len(sections), cited,
        )
        return PersonalizedAnalysis(
            sections=sections, source="llm", cited=list(cited)  # type: ignore[arg-type]
        )
    except Exception as exc:  # noqa: BLE001 - 降级优先，绝不阻断主流程
        logger.warning("报告个性化分析失败，回退模板：%s", exc)
        return PersonalizedAnalysis(reason=f"调用异常：{exc}")


def summarize_facts(case: Case, workflow: Optional[Workflow]) -> List[str]:
    """对外暴露事实摘要（用于报告「事实梳理」展示与前端回显）。"""
    return build_fact_lines(case, workflow)
