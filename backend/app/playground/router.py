"""AI Playground API 路由。

端点：
- GET  /api/playground/models       模型选择器列表（复用 ai_models）
- POST /api/playground/test         单模型测试
- POST /api/playground/compare      多模型对比
- POST /api/playground/evaluate     模型评测（Evaluation Center）
- GET  /api/playground/history      测试历史
- POST /api/playground/publish      一键应用到生产（仅超管）
- GET  /api/playground/routing      当前路由规则（AI 路由测试用）
- GET/POST/PUT/DELETE /api/playground/prompts  Prompt 收藏
- GET/POST /api/playground/datasets + items     评测测试集
- GET /api/playground/evaluations + /{id}       评测任务与结果
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_superuser
from app.models.ai_center import AIModel, RoutingRule
from app.models.playground import (
    EvaluationDataset,
    EvaluationItem,
    EvaluationResult,
    EvaluationTask,
)
from app.models.user import User
from app.playground.evaluator import run_evaluation
from app.playground.history import (
    # 注意：必须用别名导入。路由函数 ``create_prompt`` 会覆盖与本模块同名的
    # 服务函数，若不加别名，函数体内再调用 ``create_prompt`` 会触发无限递归
    # （RecursionError），POST /api/playground/prompts 直接 500。
    create_prompt as create_prompt_service,
)
from app.playground.history import (
    delete_prompt,
    list_models_for_picker,
    list_prompt_library,
    list_sessions,
    update_prompt,
)
from app.playground.service import compare_models, publish_to_production, test_single
from app.schemas.playground import (
    EvalItemIn,
    EvaluationDatasetOut,
    EvaluationItemOut,
    EvaluationResultOut,
    EvaluationTaskOut,
    PlaygroundCompareRequest,
    PlaygroundEvaluateRequest,
    PlaygroundModelOut,
    PlaygroundPublishOut,
    PlaygroundPublishRequest,
    PlaygroundSessionOut,
    PlaygroundTestRequest,
    PromptLibraryCreate,
    PromptLibraryOut,
    PromptLibraryUpdate,
    RoutingRuleSimpleOut,
)
from app.services.ai.manager import AIManager

router = APIRouter(prefix="/api/playground", tags=["playground"])


def _mgr(db: AsyncSession) -> AIManager:
    return AIManager(db=db)


# ---------------------------------------------------------------------------
# 模型选择器
# ---------------------------------------------------------------------------
@router.get("/models", response_model=list[PlaygroundModelOut])
async def list_models(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[PlaygroundModelOut]:
    return await list_models_for_picker(db)


# ---------------------------------------------------------------------------
# 单模型测试
# ---------------------------------------------------------------------------
@router.post("/test", response_model=PlaygroundSessionOut)
async def playground_test(
    req: PlaygroundTestRequest,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> PlaygroundSessionOut:
    return await test_single(db, _mgr(db), current.id, req)


# ---------------------------------------------------------------------------
# 多模型对比
# ---------------------------------------------------------------------------
@router.post("/compare")
async def playground_compare(
    req: PlaygroundCompareRequest,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    session, rows = await compare_models(db, _mgr(db), current.id, req)
    return {"session": session, "rows": rows}


# ---------------------------------------------------------------------------
# 模型评测
# ---------------------------------------------------------------------------
@router.post("/evaluate", response_model=EvaluationTaskOut)
async def playground_evaluate(
    req: PlaygroundEvaluateRequest,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> EvaluationTaskOut:
    return await run_evaluation(db, _mgr(db), current.id, req)


@router.get("/evaluations", response_model=list[EvaluationTaskOut])
async def list_evaluations(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[EvaluationTaskOut]:
    stmt = select(EvaluationTask)
    if not current.is_superuser:
        stmt = stmt.where(EvaluationTask.user_id == current.id)
    stmt = stmt.order_by(EvaluationTask.created_at.desc()).limit(limit).offset(offset)
    rows = (await db.scalars(stmt)).all()
    return [EvaluationTaskOut.model_validate(r) for r in rows]


@router.get("/evaluations/{task_id}", response_model=list[EvaluationResultOut])
async def get_evaluation_results(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[EvaluationResultOut]:
    stmt = select(EvaluationResult).where(EvaluationResult.task_id == task_id)
    rows = (await db.scalars(stmt)).all()
    return [EvaluationResultOut.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# 测试历史
# ---------------------------------------------------------------------------
@router.get("/history", response_model=list[PlaygroundSessionOut])
async def playground_history(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
    type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[PlaygroundSessionOut]:
    user_id = None if current.is_superuser else current.id
    return await list_sessions(db, user_id, type=type, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# 一键发布到生产（仅超管）
# ---------------------------------------------------------------------------
@router.post("/publish", response_model=PlaygroundPublishOut)
async def playground_publish(
    req: PlaygroundPublishRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superuser),
) -> PlaygroundPublishOut:
    return await publish_to_production(db, None, req)


# ---------------------------------------------------------------------------
# 当前路由规则（AI 路由测试用）
# ---------------------------------------------------------------------------
@router.get("/routing", response_model=list[RoutingRuleSimpleOut])
async def current_routing(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[RoutingRuleSimpleOut]:
    rules = (await db.scalars(select(RoutingRule))).all()
    out = []
    for r in rules:
        m = await db.get(AIModel, r.model_id)
        out.append(
            RoutingRuleSimpleOut(
                feature=r.feature,
                model_id=r.model_id,
                model_name=m.name if m else None,
                enabled=r.enabled,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Prompt 收藏
# ---------------------------------------------------------------------------
@router.get("/prompts", response_model=list[PromptLibraryOut])
async def list_prompts(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
    category: str | None = Query(None),
) -> list[PromptLibraryOut]:
    user_id = None if current.is_superuser else current.id
    return await list_prompt_library(db, user_id, category=category)


@router.post("/prompts", response_model=PromptLibraryOut, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    req: PromptLibraryCreate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> PromptLibraryOut:
    return await create_prompt_service(db, current.id, req)


@router.put("/prompts/{pid}", response_model=PromptLibraryOut)
async def update_prompt_endpoint(
    pid: UUID,
    req: PromptLibraryUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> PromptLibraryOut:
    out = await update_prompt(db, pid, current.id, req)
    if out is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt 不存在或无权限")
    return out


@router.delete("/prompts/{pid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt_endpoint(
    pid: UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> None:
    ok = await delete_prompt(db, pid, current.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt 不存在或无权限")


# ---------------------------------------------------------------------------
# 评测测试集
# ---------------------------------------------------------------------------
@router.get("/datasets", response_model=list[EvaluationDatasetOut])
async def list_datasets(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[EvaluationDatasetOut]:
    stmt = select(EvaluationDataset)
    if not current.is_superuser:
        stmt = stmt.where(
            (EvaluationDataset.user_id == current.id) | (EvaluationDataset.is_public == True)  # noqa: E712
        )
    stmt = stmt.order_by(EvaluationDataset.created_at.desc())
    rows = (await db.scalars(stmt)).all()
    return [EvaluationDatasetOut.model_validate(r) for r in rows]


@router.post("/datasets", response_model=EvaluationDatasetOut, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    name: str,
    items: list[EvalItemIn],
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
    category: str | None = None,
    description: str | None = None,
    is_public: bool = False,
) -> EvaluationDatasetOut:
    ds = EvaluationDataset(
        user_id=current.id,
        name=name,
        category=category,
        description=description,
        is_public=is_public,
        item_count=len(items),
    )
    db.add(ds)
    await db.flush()
    for i, it in enumerate(items):
        db.add(
            EvaluationItem(
                dataset_id=ds.id,
                input=it.input,
                expected=it.expected,
                context=it.context,
                order_index=i,
            )
        )
    await db.commit()
    await db.refresh(ds)
    return EvaluationDatasetOut.model_validate(ds)


@router.get("/datasets/{dataset_id}/items", response_model=list[EvaluationItemOut])
async def list_dataset_items(
    dataset_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[EvaluationItemOut]:
    rows = (
        await db.scalars(select(EvaluationItem).where(EvaluationItem.dataset_id == dataset_id))
    ).all()
    return [EvaluationItemOut.model_validate(r) for r in rows]
