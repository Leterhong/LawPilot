"""Agent 提示词（仅在使用真实 LLM 时启用）。

提供「对话决策」所需的系统提示与请求构造。当未配置 LLM 时，引擎走确定性
规则分支，不会使用本文件。
"""
from __future__ import annotations

from typing import List

from app.models.case import Case
from app.services.agent.knowledge_base import CASE_TYPE_LABELS, Question

SYSTEM_PROMPT = (
    "你是 LawPilot 的法律办事助手，服务对象是完全不懂法律的普通用户。"
    "你的目标不是给出法律意见，而是帮助用户理清：自己遇到什么问题、享有什么权利、"
    "该准备什么证据、去哪里办、下一步做什么。语气要平实、友好、易懂，避免法言法语堆砌。"
    "请根据给定的问题清单逐条收集事实，提取用户回答中的关键信息，决定下一个要问的"
    "问题；当清单全部问完、关键信息已足够时，标记可以生成报告。"
)

DISCLAIMER = (
    "本报告由 AI 基于您提供的信息自动生成，仅供办事参考，不构成法律意见，"
    "也不替代专业律师或司法机关的判断。个案事实与法律适用可能存在差异，"
    "重大权益事项建议咨询执业律师或前往法律援助机构。"
)


def build_decision_prompt(
    case: Case,
    script: List[Question],
    collected: dict,
    pending_qid: str,
    history_lines: List[str],
) -> str:
    """构造一轮对话决策请求（要求模型返回 JSON）。"""
    label = CASE_TYPE_LABELS.get(case.case_type, "纠纷")
    script_lines = "\n".join(
        "- id={qid}, 问题：{text}{opts}".format(
            qid=q.id,
            text=q.text,
            opts=f"（选项：{'/'.join(q.options)}）" if q.options else "",
        )
        for q in script
    )
    collected_lines = (
        "\n".join(f"- {k}: {v}" for k, v in collected.items()) or "（暂无）"
    )
    hist = "\n".join(history_lines) or "（暂无）"

    return f"""案件类型：{label}
问题清单（按顺序收集关键事实）：
{script_lines}

已收集事实：
{collected_lines}

近几轮对话：
{hist}

用户刚刚回答的是问题 id={pending_qid}。

请仅输出如下 JSON（不要多余解释）：
{{
  "collected_updates": {{ /* 从用户本次及历史回答中提取的事实，键为问题 id，值为提炼后的要点 */ }},
  "next_question_id": "下一个要问的问题 id；若所有问题已问完则为 null",
  "is_complete": false,
  "reply": "给用户的自然语言回复（简洁、友好、中文，先肯定已记录，再自然引出下一问或告知即将生成报告）"
}}"""
