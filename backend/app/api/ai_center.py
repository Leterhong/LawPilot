"""AI 能力中心 API 路由。

前缀 ``/api/ai``，标签 ``ai-center``。所有接口均要求**超级管理员**权限
（``require_superuser``）。不影响任何已有业务接口。
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_superuser
from app.models.user import User
from app.schemas.ai_center import (
    AIMeta,
    AIModelCreate,
    AIModelOut,
    AIModelUpdate,
    ModelHealthOut,
    ModelLogOut,
    PromptTemplateCreate,
    PromptTemplateOut,
    PromptTemplateUpdate,
    PromptVersionOut,
    ProviderCreate,
    ProviderOut,
    ProviderUpdate,
    RoutingRuleCreate,
    RoutingRuleOut,
    RoutingRuleUpdate,
    TestConnectionRequest,
    TestConnectionResult,
)
from app.services.ai_center_service import AICenterService

router = APIRouter(prefix="/api/ai", tags=["ai-center"])


def _svc(db: AsyncSession = Depends(get_db)) -> AICenterService:
    return AICenterService(db)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资源不存在")


# ---------------------------------------------------------------------------
# 全局 AI 配置状态（供前端门控：是否已配置真实模型）
# 仅返回布尔，不泄露密钥，故只需登录态即可访问
# ---------------------------------------------------------------------------
@router.get("/status", summary="全局 AI 是否已配置真实模型")
async def ai_status(
    _: User = Depends(get_current_user),
    svc: AICenterService = Depends(_svc),
) -> dict:
    return await svc.get_ai_status()


# ---------------------------------------------------------------------------
# Meta（前端下拉选项）
# ---------------------------------------------------------------------------
@router.get("/meta", response_model=AIMeta, summary="AI 能力中心元数据（枚举选项）")
async def meta(
    _: User = Depends(require_superuser),
    svc: AICenterService = Depends(_svc),
) -> AIMeta:
    from app.models.ai_center import (
        AI_FEATURES,
        CAPABILITY_KEYS,
        PROVIDER_TYPES,
        ROUTING_STRATEGIES,
    )

    return AIMeta(
        provider_types=PROVIDER_TYPES,
        features=AI_FEATURES,
        strategies=ROUTING_STRATEGIES,
        capability_keys=CAPABILITY_KEYS,
    )


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------
@router.get("/providers", response_model=list[ProviderOut], summary="Provider 列表")
async def list_providers(
    _: User = Depends(require_superuser), svc: AICenterService = Depends(_svc)
) -> list[ProviderOut]:
    return await svc.list_providers()


@router.post("/providers", response_model=ProviderOut, status_code=201, summary="新增 Provider")
async def create_provider(
    data: ProviderCreate,
    _: User = Depends(require_superuser),
    svc: AICenterService = Depends(_svc),
) -> ProviderOut:
    return await svc.create_provider(data)


@router.put("/providers/{pid}", response_model=ProviderOut, summary="编辑 Provider")
async def update_provider(
    pid: UUID,
    data: ProviderUpdate,
    _: User = Depends(require_superuser),
    svc: AICenterService = Depends(_svc),
) -> ProviderOut:
    obj = await svc.update_provider(pid, data)
    if obj is None:
        raise _not_found()
    return obj


@router.delete("/providers/{pid}", summary="删除 Provider", status_code=204)
async def delete_provider(
    pid: UUID, _: User = Depends(require_superuser), svc: AICenterService = Depends(_svc)
) -> None:
    if not await svc.delete_provider(pid):
        raise _not_found()


# ---------------------------------------------------------------------------
# AIModel
# ---------------------------------------------------------------------------
@router.get("/models", response_model=list[AIModelOut], summary="模型列表")
async def list_models(
    _: User = Depends(require_superuser), svc: AICenterService = Depends(_svc)
) -> list[AIModelOut]:
    return await svc.list_models()


@router.post("/models", response_model=AIModelOut, status_code=201, summary="添加模型")
async def create_model(
    data: AIModelCreate,
    _: User = Depends(require_superuser),
    svc: AICenterService = Depends(_svc),
) -> AIModelOut:
    return await svc.create_model(data)


@router.put("/models/{mid}", response_model=AIModelOut, summary="编辑模型")
async def update_model(
    mid: UUID,
    data: AIModelUpdate,
    _: User = Depends(require_superuser),
    svc: AICenterService = Depends(_svc),
) -> AIModelOut:
    obj = await svc.update_model(mid, data)
    if obj is None:
        raise _not_found()
    return obj


@router.delete("/models/{mid}", summary="删除模型", status_code=204)
async def delete_model(
    mid: UUID, _: User = Depends(require_superuser), svc: AICenterService = Depends(_svc)
) -> None:
    if not await svc.delete_model(mid):
        raise _not_found()


@router.post("/models/test", response_model=TestConnectionResult, summary="测试连接（真实调用）")
async def test_connection(
    req: TestConnectionRequest,
    _: User = Depends(require_superuser),
    svc: AICenterService = Depends(_svc),
) -> TestConnectionResult:
    return await svc.test_connection(req)


@router.post(
    "/models/{mid}/health/check",
    response_model=ModelHealthOut,
    summary="手动触发模型健康检测",
)
async def health_check(
    mid: UUID, _: User = Depends(require_superuser), svc: AICenterService = Depends(_svc)
) -> ModelHealthOut:
    obj = await svc.check_health(mid)
    if obj is None:
        raise _not_found()
    return obj


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
@router.get("/routing", response_model=list[RoutingRuleOut], summary="路由规则列表")
async def list_routing(
    _: User = Depends(require_superuser), svc: AICenterService = Depends(_svc)
) -> list[RoutingRuleOut]:
    return await svc.list_routing()


@router.post("/routing", response_model=RoutingRuleOut, status_code=201, summary="新增路由规则")
async def create_routing(
    data: RoutingRuleCreate,
    _: User = Depends(require_superuser),
    svc: AICenterService = Depends(_svc),
) -> RoutingRuleOut:
    return await svc.create_routing(data)


@router.put("/routing/{rid}", response_model=RoutingRuleOut, summary="编辑路由规则")
async def update_routing(
    rid: UUID,
    data: RoutingRuleUpdate,
    _: User = Depends(require_superuser),
    svc: AICenterService = Depends(_svc),
) -> RoutingRuleOut:
    obj = await svc.update_routing(rid, data)
    if obj is None:
        raise _not_found()
    return obj


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
@router.get("/prompts", response_model=list[PromptTemplateOut], summary="Prompt 列表")
async def list_prompts(
    _: User = Depends(require_superuser), svc: AICenterService = Depends(_svc)
) -> list[PromptTemplateOut]:
    return await svc.list_prompts()


@router.post("/prompts", response_model=PromptTemplateOut, status_code=201, summary="新增 Prompt")
async def create_prompt(
    data: PromptTemplateCreate,
    user: User = Depends(require_superuser),
    svc: AICenterService = Depends(_svc),
) -> PromptTemplateOut:
    return await svc.create_prompt(data, user=user)


@router.put("/prompts/{pid}", response_model=PromptTemplateOut, summary="编辑 Prompt")
async def update_prompt(
    pid: UUID,
    data: PromptTemplateUpdate,
    user: User = Depends(require_superuser),
    svc: AICenterService = Depends(_svc),
) -> PromptTemplateOut:
    obj = await svc.update_prompt(pid, data, user=user)
    if obj is None:
        raise _not_found()
    return obj


@router.delete("/prompts/{pid}", summary="删除 Prompt", status_code=204)
async def delete_prompt(
    pid: UUID, _: User = Depends(require_superuser), svc: AICenterService = Depends(_svc)
) -> None:
    if not await svc.delete_prompt(pid):
        raise _not_found()


@router.get(
    "/prompts/{pid}/versions",
    response_model=list[PromptVersionOut],
    summary="Prompt 版本历史",
)
async def prompt_versions(
    pid: UUID, _: User = Depends(require_superuser), svc: AICenterService = Depends(_svc)
) -> list[PromptVersionOut]:
    return await svc.list_prompt_versions(pid)


# ---------------------------------------------------------------------------
# 统计 / 日志 / 健康
# ---------------------------------------------------------------------------
@router.get("/statistics", summary="Token 统计")
async def statistics(
    days: int = Query(30, ge=1, le=365),
    _: User = Depends(require_superuser),
    svc: AICenterService = Depends(_svc),
) -> dict:
    return await svc.get_statistics(days=days)


@router.get("/logs", response_model=list[ModelLogOut], summary="调用日志")
async def logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    feature: str | None = Query(None),
    _: User = Depends(require_superuser),
    svc: AICenterService = Depends(_svc),
) -> list[ModelLogOut]:
    items, _ = await svc.list_logs(limit=limit, offset=offset, feature=feature)
    return items


@router.get("/health", response_model=list[ModelHealthOut], summary="模型健康状态")
async def health(
    _: User = Depends(require_superuser), svc: AICenterService = Depends(_svc)
) -> list[ModelHealthOut]:
    return await svc.list_health()
