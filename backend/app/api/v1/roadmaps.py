"""Roadmap 路由：生成/获取办理路线图，更新步骤状态。"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, get_owned_case
from app.models.case import Case
from app.models.roadmap import Roadmap, RoadmapStep
from app.repositories.roadmap_repo import RoadmapRepository, RoadmapStepRepository
from app.schemas.roadmap import RoadmapOut, RoadmapStepOut, RoadmapStepUpdate
from app.services.roadmap_service import RoadmapService

router = APIRouter(prefix="/cases/{case_id}/roadmaps", tags=["roadmaps"])


@router.post("", response_model=RoadmapOut, status_code=status.HTTP_201_CREATED)
async def generate_roadmap(
    case: Case = Depends(get_owned_case),
    db: AsyncSession = Depends(get_db),
) -> RoadmapOut:
    """基于案件类型生成办理路线图，并派生待办任务。"""
    return await RoadmapService(db).generate(case)


@router.get("", response_model=Optional[RoadmapOut])
async def get_roadmap(
    case: Case = Depends(get_owned_case),
    db: AsyncSession = Depends(get_db),
) -> Optional[RoadmapOut]:
    """获取当前生效的路线图；未生成时返回 null（前端据此判断是否显示「生成」按钮）。"""
    return await RoadmapService(db).get_active(case)


@router.patch("/steps/{step_id}", response_model=RoadmapStepOut)
async def update_step(
    step_id: UUID,
    body: RoadmapStepUpdate,
    case: Case = Depends(get_owned_case),
    db: AsyncSession = Depends(get_db),
) -> RoadmapStepOut:
    """更新某步骤状态（完成/跳过），并同步对应任务状态。"""
    step = await RoadmapStepRepository(db).get(step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="步骤不存在")
    roadmap = await RoadmapRepository(db).get(step.roadmap_id)
    if roadmap is None or roadmap.case_id != case.id:
        raise HTTPException(status_code=404, detail="步骤不属于该案件")
    return await RoadmapService(db).set_step_status(case, step, body.status)
