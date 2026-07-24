"""时间线路由：案件事件流。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_owned_case
from app.models.case import Case
from app.models.history import History
from app.repositories.task_repo import HistoryRepository
from app.schemas.history import HistoryOut

router = APIRouter(prefix="/cases/{case_id}/history", tags=["history"])


@router.get("", response_model=list[HistoryOut])
async def list_history(
    case: Case = Depends(get_owned_case),
    db: AsyncSession = Depends(get_db),
) -> list[HistoryOut]:
    """获取案件时间线（按时间倒序）。"""
    return await HistoryRepository(db).list(
        case_id=case.id, order_by=History.created_at.desc()
    )
