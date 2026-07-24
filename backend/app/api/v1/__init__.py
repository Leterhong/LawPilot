"""API v1 路由聚合。

在此挂载所有子路由。每个子模块暴露 ``router``（APIRouter），
由本文件统一注册到 ``api_router``，最终由 main.py 以 ``/api/v1`` 前缀挂载。
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    agent,
    auth,
    cases,
    documents,
    evidence,
    evidence_center,
    history,
    legal,
    roadmaps,
    tasks,
    users,
)

api_router = APIRouter()

# 健康检查（无需前缀层级，保持简单）
@api_router.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """服务健康检查（v1）。"""
    return {"status": "ok", "service": "lawpilot-backend", "version": "0.1.0"}


# 业务路由
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(cases.router)
api_router.include_router(evidence.router)
api_router.include_router(evidence_center.router)
api_router.include_router(documents.router)
api_router.include_router(roadmaps.router)
api_router.include_router(tasks.router)
api_router.include_router(history.router)
api_router.include_router(legal.router)
api_router.include_router(agent.router)
