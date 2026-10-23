"""Playground AI 评分器（LLM Judge）。

使用一个独立评分模型（``judge_model_id``）对候选回答自动评分。
评分维度：准确性 / 完整性 / 专业性 / 逻辑性 / 格式 / 引用质量（各 0-100，总分取均值）。
评分模型不可用或无输出时优雅返回 ``None``（不影响主流程）。
"""
from __future__ import annotations

import json
from uuid import UUID

from app.models.playground import SCORE_DIMS
from app.services.ai.manager import AIManager

_JUDGE_SYSTEM = (
    "你是一位严谨的法律 AI 评测专家。请根据给定维度，对「被测模型的回答」进行客观打分。"
    "每个维度 0-100 分，总分 total 为各维度均值。只输出 JSON，不要任何解释性文字。"
)

_DIM_DESC = {
    "accuracy": "准确性（事实/法条/结论是否正确）",
    "completeness": "完整性（是否覆盖问题要点）",
    "professionalism": "专业性（法律术语与表述是否专业）",
    "logic": "逻辑性（推理链条是否清晰严密）",
    "format": "格式（结构、可读性、条理）",
    "citation": "引用质量（是否恰当引用法条/案例/依据）",
}


def _build_user_prompt(question: str, answer: str) -> str:
    dims_line = "\n".join(f"- {k}: {_DIM_DESC[k]}" for k in SCORE_DIMS)
    return (
        f"【评测问题】\n{question}\n\n"
        f"【被测模型回答】\n{answer}\n\n"
        f"【评分维度】\n{dims_line}\n\n"
        f"请严格按以下 JSON 结构输出（字段缺一不可）：\n"
        f'{{"accuracy": <int>, "completeness": <int>, "professionalism": <int>, '
        f'"logic": <int>, "format": <int>, "citation": <int>, "total": <int>}}'
    )


def _parse_judge(raw: str | None) -> tuple[float | None, dict | None]:
    if not raw:
        return None, None
    try:
        # 容忍模型在 JSON 前后包裹 ``` 或说明文字
        txt = raw.strip()
        if txt.startswith("```"):
            txt = txt.strip("`")
            txt = txt[txt.find("{") :] if "{" in txt else txt
        start, end = txt.find("{"), txt.rfind("}")
        if start == -1 or end == -1:
            return None, None
        data = json.loads(txt[start : end + 1])
    except Exception:  # noqa: BLE001
        return None, None
    detail = {k: int(data.get(k, 0)) for k in SCORE_DIMS if isinstance(data.get(k), (int, float))}
    total = data.get("total")
    if total is None and detail:
        total = sum(detail.values()) / len(detail)
    return (float(total) if total is not None else None), (detail or None)


async def judge_one(
    mgr: AIManager,
    judge_model_id: UUID,
    question: str,
    answer: str | None,
) -> tuple[float | None, dict | None]:
    """对单条回答评分，返回 (总分, 维度明细)；失败返回 (None, None)。"""
    if not answer:
        return None, None
    messages = [
        {"role": "system", "content": _JUDGE_SYSTEM},
        {"role": "user", "content": _build_user_prompt(question, answer)},
    ]
    res = await mgr.chat_model(judge_model_id, messages, json_mode=True)
    if res.content is None:
        return None, None
    return _parse_judge(res.content)
