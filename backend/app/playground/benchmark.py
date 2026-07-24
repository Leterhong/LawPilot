"""Playground 基准/成本工具。

- ``estimate_cost``：根据 ``model_pricing`` 单价估算单次调用成本（未配置则返回 None）。
- ``aggregate``：把多次调用结果聚合成摘要指标。
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.playground import ModelPricing


async def estimate_cost(
    db: AsyncSession,
    model_id: UUID,
    tokens_in: int,
    tokens_out: int,
) -> float | None:
    """按模型单价估算成本（USD）。无定价记录 → None（前端显示「--」）。"""
    pricing = (
        await db.scalars(select(ModelPricing).where(ModelPricing.model_id == model_id))
    ).first()
    if pricing is None:
        return None
    cost = (
        (Decimal(tokens_in) / 1000) * pricing.price_in_per_1k
        + (Decimal(tokens_out) / 1000) * pricing.price_out_per_1k
    )
    return float(cost)


def aggregate_results(rows: list[dict]) -> dict:
    """把若干对比/评测结果行聚合成摘要（平均延迟/成本/得分、成功率）。"""
    if not rows:
        return {"count": 0}
    latencies = [r["latency_ms"] for r in rows if r.get("latency_ms")]
    costs = [r["cost"] for r in rows if isinstance(r.get("cost"), (int, float))]
    scores = [r["score"] for r in rows if isinstance(r.get("score"), (int, float))]
    ok = [r for r in rows if r.get("error") is None and r.get("status") in (None, "success")]
    return {
        "count": len(rows),
        "avg_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
        "avg_cost": round(sum(costs) / len(costs), 6) if costs else None,
        "avg_score": round(sum(scores) / len(scores), 2) if scores else None,
        "success_rate": round(len(ok) / len(rows), 3),
    }
