"""案件服务：案件全生命周期编排。

负责创建案件（含初始化工作流与时间线）、消息追加、列表/详情/更新/删除。
Agent 的多轮追问与报告生成将在 Phase 6 接入，此处先保证数据闭环可运行。
"""
from __future__ import annotations

from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.enums import (
    CaseStatusEnum,
    CaseTypeEnum,
    EventTypeEnum,
    MessageTypeEnum,
    RoleEnum,
    WorkflowStageEnum,
)
from app.models.message import Message
from app.models.user import User
from app.repositories.case_repo import (
    CaseRepository,
    MessageRepository,
    WorkflowRepository,
)
from app.repositories.task_repo import HistoryRepository
from app.schemas.common import Page
from app.schemas.case import CaseOut, CaseUpdate


class CaseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.cases: CaseRepository = CaseRepository(session)
        self.messages: MessageRepository = MessageRepository(session)
        self.workflow: WorkflowRepository = WorkflowRepository(session)
        self.history: HistoryRepository = HistoryRepository(session)

    async def create_case(
        self,
        user: User,
        title: str,
        case_type: CaseTypeEnum,
        description: str | None = None,
    ) -> Case:
        case = await self.cases.create(
            user_id=user.id,
            title=title,
            case_type=case_type,
            description=description,
            status=CaseStatusEnum.INTAKE,
            current_stage=WorkflowStageEnum.IDENTIFY.value,
        )
        # 初始化工作流状态机
        await self.workflow.create(case_id=case.id, stage=WorkflowStageEnum.IDENTIFY)
        # 时间线：创建事件
        await self.history.create(
            case_id=case.id,
            user_id=user.id,
            event_type=EventTypeEnum.CREATED,
            title="案件创建",
            detail=title,
        )
        # 若用户提供初始描述，作为首条 user 消息落库
        if description:
            seq = await self.messages.next_sequence(case.id)
            await self.messages.create(
                case_id=case.id,
                role=RoleEnum.USER,
                content=description,
                sequence=seq,
                message_type=MessageTypeEnum.TEXT,
            )
        return case

    async def list_cases(
        self,
        user: User,
        *,
        status: CaseStatusEnum | None = None,
        case_type: CaseTypeEnum | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Page[CaseOut]:
        filters = {"user_id": user.id}
        if status is not None:
            filters["status"] = status
        if case_type is not None:
            filters["case_type"] = case_type
        total = await self.cases.count(**filters)
        rows = await self.cases.list(
            skip=(page - 1) * page_size,
            limit=page_size,
            order_by=Case.created_at.desc(),
            **filters,
        )
        return Page[CaseOut].create([CaseOut.model_validate(c) for c in rows], total, page, page_size)

    async def get_owned(self, case_id, user: User) -> Case | None:
        case = await self.cases.get(case_id)
        if case is None or case.user_id != user.id:
            return None
        return case

    async def update_case(self, case: Case, data: CaseUpdate) -> Case:
        changed = data.model_dump(exclude_unset=True)
        # 若状态变更，记录时间线
        new_status = changed.get("status")
        case = await self.cases.update(case, **changed)
        if new_status is not None:
            await self.history.create(
                case_id=case.id,
                user_id=case.user_id,
                event_type=EventTypeEnum.STATUS_CHANGED,
                title="状态变更",
                detail=f"变更为 {new_status.value}",
            )
        return case

    async def delete_case(self, case: Case) -> None:
        await self.cases.delete(case)

    async def add_user_message(
        self,
        case: Case,
        content: str,
        message_type: MessageTypeEnum = MessageTypeEnum.TEXT,
        metadata_json: dict | None = None,
    ) -> Message:
        seq = await self.messages.next_sequence(case.id)
        msg = await self.messages.create(
            case_id=case.id,
            role=RoleEnum.USER,
            content=content,
            sequence=seq,
            message_type=message_type,
            metadata_json=metadata_json,
        )
        await self.history.create(
            case_id=case.id,
            user_id=case.user_id,
            event_type=EventTypeEnum.MESSAGE,
            title="用户消息",
            detail=content[:80],
        )
        return msg

    async def get_messages(self, case: Case) -> List[Message]:
        return await self.messages.list(order_by=Message.sequence, case_id=case.id)
