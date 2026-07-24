"""案件路由：CRUD + 案件内消息。

案件相关子资源（证据/文书/Roadmap/任务/时间线）分布在各自路由文件中，
统一以 ``/cases/{case_id}/...`` 为前缀，并通过 ``get_owned_case`` 校验归属。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, get_owned_case
from app.models.case import Case
from app.models.enums import CaseStatusEnum, CaseTypeEnum
from app.models.user import User
from app.schemas.case import CaseCreate, CaseOut, CaseUpdate
from app.schemas.common import Page
from app.schemas.message import MessageCreate, MessageOut
from app.services.case_service import CaseService

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
async def create_case(
    body: CaseCreate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseOut:
    """创建案件（含初始化工作流与时间线）。"""
    return await CaseService(db).create_case(
        current, body.title, body.case_type, body.description
    )


@router.get("", response_model=Page[CaseOut])
async def list_cases(
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    status_filter: CaseStatusEnum | None = Query(None, alias="status"),
    case_type: CaseTypeEnum | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=500),
) -> Page[CaseOut]:
    """分页列出当前用户的案件，支持按状态/类型过滤。"""
    return await CaseService(db).list_cases(
        current,
        status=status_filter,
        case_type=case_type,
        page=page,
        page_size=page_size,
    )


@router.get("/{case_id}", response_model=CaseOut)
async def get_case(case: Case = Depends(get_owned_case)) -> CaseOut:
    """获取单个案件详情。"""
    return case


@router.patch("/{case_id}", response_model=CaseOut)
async def update_case(
    body: CaseUpdate,
    case: Case = Depends(get_owned_case),
    db: AsyncSession = Depends(get_db),
) -> CaseOut:
    """更新案件字段（含报告沉淀字段、状态等）。"""
    return await CaseService(db).update_case(case, body)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case: Case = Depends(get_owned_case),
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除案件（级联删除其子资源）。"""
    await CaseService(db).delete_case(case)


@router.post(
    "/{case_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_message(
    body: MessageCreate,
    case: Case = Depends(get_owned_case),
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    """向案件追加一条用户消息（原始写入；多轮 Agent 对话请使用 /chat 端点）。"""
    return await CaseService(db).add_user_message(
        case, body.content, body.message_type, body.metadata_json
    )


@router.get("/{case_id}/messages", response_model=list[MessageOut])
async def get_messages(
    case: Case = Depends(get_owned_case),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    """获取案件全部消息（按序号排序）。"""
    return await CaseService(db).get_messages(case)
