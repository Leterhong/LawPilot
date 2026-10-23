"""Playground 评测引擎（Evaluation Center 后端）。

给定测试集（dataset_id 或直接 items）+ 被测模型列表 + 可选 LLM Judge，
逐题逐模型调用，落库 evaluation_results，并聚合出报告（score_summary）。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_center import PromptTemplate
from app.models.playground import (
    EvaluationItem,
    EvaluationResult,
    EvaluationTask,
)
from app.playground.benchmark import aggregate_results, estimate_cost
from app.playground.scorer import judge_one
from app.schemas.playground import EvaluationTaskOut, PlaygroundEvaluateRequest
from app.services.ai.manager import AIManager


def _build_messages(system: str | None, user: str, context: str | None) -> list[dict[str, str]]:
    msgs: list[dict[str, str]] = []
    if system:
        msgs.append({"role": "system", "content": system})
    u = user or ""
    if context:
        u = f"{u}\n\n【上下文】\n{context}" if u else f"【上下文】\n{context}"
    msgs.append({"role": "user", "content": u})
    return msgs


async def run_evaluation(
    db: AsyncSession,
    mgr: AIManager,
    user_id: UUID | None,
    req: PlaygroundEvaluateRequest,
) -> EvaluationTaskOut:
    # 收集题目
    items: list[tuple[str, str | None, str | None, UUID | None]] = []
    if req.dataset_id is not None:
        rows = (
            await db.scalars(select(EvaluationItem).where(EvaluationItem.dataset_id == req.dataset_id))
        ).all()
        items = [(r.input, r.expected, r.context, r.id) for r in rows]
    elif req.items:
        items = [(it.input, it.expected, it.context, None) for it in req.items]
    if not items:
        from fastapi import HTTPException
        from fastapi import status as http_status

        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="评测需要 dataset_id 或直接提供 items",
        )

    cfg = req.config or {}
    temperature = cfg.get("temperature")
    max_tokens = cfg.get("max_tokens")

    # 可选 system prompt（来自 prompt_templates）
    system: str | None = None
    if req.prompt_template_key:
        pt = (
            await db.scalars(
                select(PromptTemplate).where(PromptTemplate.key == req.prompt_template_key)
            )
        ).first()
        if pt is not None:
            system = pt.content

    task = EvaluationTask(
        user_id=user_id,
        name=req.name,
        model_ids=[str(m) for m in req.model_ids],
        judge_model_id=req.judge_model_id,
        feature=req.feature,
        prompt_template_key=req.prompt_template_key,
        config=cfg,
        status="running",
        total_items=len(items) * len(req.model_ids),
        started_at=datetime.utcnow(),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    per_model_rows: dict[UUID, list[dict]] = {m: [] for m in req.model_ids}

    try:
        for mid in req.model_ids:
            for inp, expected, context, item_id in items:
                messages = _build_messages(system, inp, context)
                res = await mgr.chat_model(mid, messages, temperature=temperature, max_tokens=max_tokens)
                cost = await estimate_cost(db, mid, res.tokens_in, res.tokens_out)
                is_correct = None
                if expected and res.content:
                    is_correct = expected.strip() in res.content
                score = None
                detail = None
                if req.judge_model_id is not None and res.content is not None:
                    score, detail = await judge_one(mgr, req.judge_model_id, inp, res.content)
                result = EvaluationResult(
                    task_id=task.id,
                    item_id=item_id,
                    model_id=mid,
                    input=inp,
                    expected=expected,
                    output=res.content,
                    is_correct=is_correct,
                    is_json_valid=None,
                    has_hallucination=None,
                    score=score,
                    metrics=detail,
                    latency_ms=res.latency_ms,
                    tokens_in=res.tokens_in,
                    tokens_out=res.tokens_out,
                    cost=Decimal(cost) if cost is not None else Decimal("0"),
                    error_text=res.error,
                )
                db.add(result)
                await db.flush()
                per_model_rows[mid].append(
                    {
                        "latency_ms": res.latency_ms,
                        "cost": cost,
                        "score": score,
                        "status": "success" if res.content else "error",
                        "error": res.error,
                    }
                )
                task.processed_items += 1
                await db.flush()

        # 聚合
        model_summaries = {}
        for mid, rows in per_model_rows.items():
            model_summaries[str(mid)] = aggregate_results(rows)
        all_rows = [r for rows in per_model_rows.values() for r in rows]
        overall = aggregate_results(all_rows)
        task.score_summary = {"models": model_summaries, "overall": overall}
        task.status = "done"
        task.finished_at = datetime.utcnow()
        await db.commit()
        await db.refresh(task)
    except Exception:  # noqa: BLE001
        task.status = "error"
        await db.commit()
        raise

    return EvaluationTaskOut.model_validate(task)
