"""Playground 业务编排。

- ``test_single``：单模型测试，保存历史会话。
- ``compare_models``：多模型并行调用 + AI 自动评分，保存对比结果与历史。
- ``publish_to_production``：一键把某 feature 的默认路由改写为指定模型（UPDATE routing_rules）。
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_center import RoutingRule
from app.models.playground import (
    ModelComparison,
    PlaygroundPublish,
    PlaygroundSession,
)
from app.playground.benchmark import estimate_cost
from app.playground.scorer import judge_one
from app.schemas.playground import (
    CompareRowOut,
    PlaygroundCompareRequest,
    PlaygroundPublishOut,
    PlaygroundPublishRequest,
    PlaygroundSessionOut,
    PlaygroundTestRequest,
)
from app.services.ai.manager import AIManager, ChatResult


def _build_messages(
    system_prompt: str | None, user_prompt: str, context: str | None
) -> list[dict[str, str]]:
    msgs: list[dict[str, str]] = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    u = user_prompt or ""
    if context:
        u = f"{u}\n\n【上下文】\n{context}" if u else f"【上下文】\n{context}"
    msgs.append({"role": "user", "content": u})
    return msgs


def _provider_name(db: AsyncSession, model_id: UUID, fallback: str | None) -> str | None:
    return fallback


async def _cost(db: AsyncSession, model_id: UUID, tin: int, tout: int) -> float | None:
    return await estimate_cost(db, model_id, tin, tout)


async def test_single(
    db: AsyncSession,
    mgr: AIManager,
    user_id: UUID | None,
    req: PlaygroundTestRequest,
) -> PlaygroundSessionOut:
    """单模型测试：调用 → 估算成本 → 存历史 → 返回会话。"""
    messages = _build_messages(req.system_prompt, req.user_prompt, req.context)
    res: ChatResult = await mgr.chat_model(
        req.model_id,
        messages,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )
    cost = await _cost(db, req.model_id, res.tokens_in, res.tokens_out)
    status = "success" if res.content else ("error" if res.error else "partial")
    session = PlaygroundSession(
        user_id=user_id,
        type="single",
        model_ids=[str(req.model_id)],
        system_prompt=req.system_prompt,
        user_prompt=req.user_prompt,
        context=req.context,
        files=[f.model_dump() for f in (req.files or [])],
        params={"temperature": req.temperature, "top_p": req.top_p, "max_tokens": req.max_tokens, "streaming": req.streaming},
        input={"model_id": str(req.model_id), "messages": messages},
        output={"content": res.content, "model_name": res.model_name, "provider_name": res.provider_name},
        token_usage={"in": res.tokens_in, "out": res.tokens_out, "total": res.tokens_in + res.tokens_out, "cost": cost},
        latency_ms=res.latency_ms,
        status=status,
        error_text=res.error,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return PlaygroundSessionOut.model_validate(session)


async def compare_models(
    db: AsyncSession,
    mgr: AIManager,
    user_id: UUID | None,
    req: PlaygroundCompareRequest,
) -> tuple[PlaygroundSessionOut, list[CompareRowOut]]:
    """多模型对比：并行调用各模型 → 可选 LLM Judge 评分 → 存对比结果与历史。"""
    messages = _build_messages(req.system_prompt, req.user_prompt, req.context)

    async def _call_one(mid: UUID) -> ChatResult:
        return await mgr.chat_model(
            mid, messages, temperature=req.temperature, max_tokens=req.max_tokens
        )

    results: list[ChatResult] = await asyncio.gather(*[_call_one(m) for m in req.model_ids])

    # 评分（并行）
    async def _judge_one(r: ChatResult):
        if req.judge_model_id is None or r.content is None:
            return None, None
        return await judge_one(mgr, req.judge_model_id, req.user_prompt, r.content)

    judged = await asyncio.gather(*[_judge_one(r) for r in results])

    rows: list[CompareRowOut] = []
    comparisons: list[ModelComparison] = []
    for mid, res, (score, detail) in zip(req.model_ids, results, judged):
        cost = await _cost(db, mid, res.tokens_in, res.tokens_out)
        provider_name = res.provider_name
        row = CompareRowOut(
            model_id=mid,
            model_name=res.model_name,
            provider_name=provider_name,
            content=res.content,
            tokens_in=res.tokens_in,
            tokens_out=res.tokens_out,
            latency_ms=res.latency_ms,
            cost=cost,
            score=score,
            score_detail=detail,
            status="success" if res.content else ("error" if res.error else "partial"),
            error=res.error,
        )
        rows.append(row)
        comparisons.append(
            ModelComparison(
                model_id=mid,
                model_name=res.model_name,
                provider_id=None,
                provider_name=provider_name,
                response=res.content,
                tokens_in=res.tokens_in,
                tokens_out=res.tokens_out,
                cost=Decimal(cost) if cost is not None else Decimal("0"),
                latency_ms=res.latency_ms,
                score=score,
                score_detail=detail,
                status=row.status,
                error_text=res.error,
            )
        )

    scores = [r.score for r in rows if r.score is not None]
    avg_score = round(sum(scores) / len(scores), 2) if scores else None
    # 各维度均值
    score_detail_avg: dict | None = None
    if any(r.score_detail for r in rows):
        from app.models.playground import SCORE_DIMS

        score_detail_avg = {}
        for dim in SCORE_DIMS:
            vals = [r.score_detail.get(dim, 0) for r in rows if r.score_detail and dim in r.score_detail]
            if vals:
                score_detail_avg[dim] = round(sum(vals) / len(vals), 1)

    session = PlaygroundSession(
        user_id=user_id,
        type="compare",
        model_ids=[str(m) for m in req.model_ids],
        system_prompt=req.system_prompt,
        user_prompt=req.user_prompt,
        context=req.context,
        params={"temperature": req.temperature, "top_p": req.top_p, "max_tokens": req.max_tokens},
        input={"model_ids": [str(m) for m in req.model_ids], "messages": messages},
        output={"judge_model_id": str(req.judge_model_id) if req.judge_model_id else None,
                "rows": [{"model_id": str(r.model_id), "model_name": r.model_name, "score": r.score} for r in rows]},
        score=avg_score,
        score_detail=score_detail_avg,
        token_usage={},
        latency_ms=max((r.latency_ms for r in rows), default=0),
        status="success" if any(r.content for r in rows) else "error",
    )
    db.add(session)
    await db.flush()
    for c in comparisons:
        c.session_id = session.id
        db.add(c)
    await db.commit()
    await db.refresh(session)
    return PlaygroundSessionOut.model_validate(session), rows


async def publish_to_production(
    db: AsyncSession,
    user_id: UUID | None,
    req: PlaygroundPublishRequest,
) -> PlaygroundPublishOut:
    """一键应用到生产：把某 feature 的 routing_rules.model_id 改为指定模型。"""
    rule = (
        await db.scalars(select(RoutingRule).where(RoutingRule.feature == req.feature))
    ).first()
    if rule is None:
        from fastapi import HTTPException
        from fastapi import status as http_status

        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"未找到 feature={req.feature} 的路由规则，无法发布",
        )
    from_model_id = rule.model_id
    rule.model_id = req.model_id
    rule.enabled = True
    await db.flush()

    publish = PlaygroundPublish(
        user_id=user_id,
        feature=req.feature,
        from_model_id=from_model_id,
        to_model_id=req.model_id,
        routing_rule_id=rule.id,
        note=req.note,
    )
    db.add(publish)
    await db.commit()
    await db.refresh(publish)
    return PlaygroundPublishOut.model_validate(publish)
