"""任务路由：列出与更新案件待办。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_owned_case
from app.models.case import Case
from app.models.task import Task
from app.repositories.task_repo import TaskRepository
from app.schemas.task import TaskOut, TaskUpdate

router = APIRouter(prefix="/cases/{case_id}/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskOut])
async def list_tasks(
    case: Case = Depends(get_owned_case),
    db: AsyncSession = Depends(get_db),
) -> list[TaskOut]:
    """列出案件全部待办（按到期日升序）。"""
    return await TaskRepository(db).list(case_id=case.id, order_by=Task.due_date.asc())


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: UUID,
    body: TaskUpdate,
    case: Case = Depends(get_owned_case),
    db: AsyncSession = Depends(get_db),
) -> TaskOut:
    """更新任务（状态/优先级/到期日等）。"""
    task = await TaskRepository(db).get(task_id)
    if task is None or task.case_id != case.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    return await TaskRepository(db).update(task, **body.model_dump(exclude_unset=True))
