"""合同服务层：落库 / 列表 / 详情 / 删除。

只负责 contracts 主表的增删查（Step2 范围）。AI 分析（Step3）与子表（后续步骤）
由各自服务处理，本服务保持纯净、可复用。
"""
from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import (
    Contract,
    ContractClause,
    ContractReport,
    ContractRisk,
    ContractTask,
)


class ContractService:
    """合同主记录 CRUD。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        user_id: UUID | None,
        title: str | None,
        contract_type: str | None = None,
        status: str = "parsing",
        file_path: str | None = None,
        file_type: str | None = None,
        file_size: int | None = None,
        full_text: str | None = None,
        ocr_text: str | None = None,
        language: str = "zh",
        page_count: int | None = None,
    ) -> Contract:
        contract = Contract(
            user_id=user_id,
            title=title,
            contract_type=contract_type,
            status=status,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size,
            full_text=full_text,
            ocr_text=ocr_text,
            language=language,
            page_count=page_count,
        )
        self.db.add(contract)
        await self.db.flush()
        return contract

    async def update_after_parse(
        self,
        contract: Contract,
        *,
        contract_type: str | None,
        full_text: str | None,
        ocr_text: str | None,
        status: str = "uploaded",
    ) -> None:
        """文本提取 / 分类完成后回写。"""
        contract.contract_type = contract_type
        contract.full_text = full_text
        contract.ocr_text = ocr_text
        contract.status = status
        self.db.add(contract)
        await self.db.flush()

    async def get(self, contract_id: UUID) -> Contract | None:
        return await self.db.get(Contract, contract_id)

    async def list_for_user(
        self,
        user_id: UUID | None = None,
        *,
        contract_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Contract], int]:
        """列出合同。

        - 普通用户只看自己的（user_id 匹配）；
        - 传入 ``user_id=None`` 视为「管理员视角查看全部」（由调用方控制权限）。
        """
        conds = []
        if user_id is not None:
            conds.append(Contract.user_id == user_id)
        if contract_type:
            conds.append(Contract.contract_type == contract_type)
        if status:
            conds.append(Contract.status == status)

        total = await self.db.scalar(
            select(func.count()).select_from(Contract).where(*conds)
        )
        total = int(total or 0)

        stmt = (
            select(Contract)
            .where(*conds)
            .order_by(Contract.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.db.scalars(stmt)).all()
        return list(rows), total

    async def delete(self, contract: Contract) -> None:
        await self.db.delete(contract)
        await self.db.flush()

    # ------------------------------------------------------------------
    # Step3：子表读取（风险 / 条款）
    # ------------------------------------------------------------------
    async def get_risks(self, contract_id: UUID) -> list[ContractRisk]:
        """返回合同全部风险（按风险分降序）。"""
        stmt = (
            select(ContractRisk)
            .where(ContractRisk.contract_id == contract_id)
            .order_by(ContractRisk.score.desc())
        )
        return list((await self.db.scalars(stmt)).all())

    async def get_clauses(self, contract_id: UUID) -> list[ContractClause]:
        """返回合同全部条款（按 order_index 升序）。"""
        stmt = (
            select(ContractClause)
            .where(ContractClause.contract_id == contract_id)
            .order_by(ContractClause.order_index.asc())
        )
        return list((await self.db.scalars(stmt)).all())

    # ------------------------------------------------------------------
    # Step5：报告读取（contract_reports）
    # ------------------------------------------------------------------
    async def get_report(
        self, contract_id: UUID, report_type: str
    ) -> ContractReport | None:
        """返回指定类型的最新报告（无则 None）。"""
        stmt = (
            select(ContractReport)
            .where(
                ContractReport.contract_id == contract_id,
                ContractReport.report_type == report_type,
            )
            .order_by(ContractReport.created_at.desc())
            .limit(1)
        )
        return (await self.db.scalars(stmt)).first()

    async def list_reports(self, contract_id: UUID) -> list[ContractReport]:
        """返回合同全部报告（按生成时间倒序）。"""
        stmt = (
            select(ContractReport)
            .where(ContractReport.contract_id == contract_id)
            .order_by(ContractReport.created_at.desc())
        )
        return list((await self.db.scalars(stmt)).all())

    # ------------------------------------------------------------------
    # Step6：提醒 / 待办（contract_tasks）
    # ------------------------------------------------------------------
    async def create_task(
        self,
        contract_id: UUID,
        *,
        type: str = "reminder",
        title: str,
        category: str | None = None,
        due_date: date | None = None,
        remind_before_days: int = 7,
        done: bool = False,
        priority: str = "normal",
        note: str | None = None,
    ) -> ContractTask:
        """创建一条提醒 / 待办。"""
        task = ContractTask(
            contract_id=contract_id,
            type=type,
            title=title,
            category=category,
            due_date=due_date,
            remind_before_days=remind_before_days,
            done=done,
            priority=priority,
            note=note,
        )
        self.db.add(task)
        await self.db.flush()
        return task

    async def get_task(self, task_id: UUID) -> ContractTask | None:
        return await self.db.get(ContractTask, task_id)

    async def list_tasks(
        self, contract_id: UUID, *, type: str | None = None
    ) -> list[ContractTask]:
        """列出合同下的提醒 / 待办。"""
        conds = [ContractTask.contract_id == contract_id]
        if type:
            conds.append(ContractTask.type == type)
        stmt = (
            select(ContractTask)
            .where(*conds)
            .order_by(ContractTask.due_date.asc().nullslast(), ContractTask.created_at.desc())
        )
        return list((await self.db.scalars(stmt)).all())

    async def list_upcoming(
        self, user_id: UUID | None, days: int = 30
    ) -> list[tuple[ContractTask, str]]:
        """提醒中心聚合：当前用户所有「未完成」且 due_date 在窗口内的 reminder。

        返回 ``(task, contract_title)`` 列表，按 due_date 升序（null 排最后）。
        ``user_id=None`` 视为管理员视角（返回全部，由调用方控制权限）。
        """
        horizon = date.today() + timedelta(days=days)
        conds = [
            Contract.user_id == user_id if user_id is not None else True,
            ContractTask.type == "reminder",
            ContractTask.done == False,  # noqa: E712
            ContractTask.due_date.isnot(None),
            ContractTask.due_date <= horizon,
        ]
        stmt = (
            select(ContractTask, Contract.title)
            .join(Contract, ContractTask.contract_id == Contract.id)
            .where(*conds)
            .order_by(ContractTask.due_date.asc().nullslast())
        )
        rows = (await self.db.execute(stmt)).all()
        return [(task, title or "（未命名合同）") for task, title in rows]

    async def update_task(self, task: ContractTask, **fields: object) -> ContractTask:
        """按字段更新一条提醒（忽略 None 以外的空值由调用方决定）。"""
        allowed = {
            "type",
            "title",
            "category",
            "due_date",
            "remind_before_days",
            "done",
            "priority",
            "note",
        }
        for k, v in fields.items():
            if k in allowed and v is not None:
                setattr(task, k, v)
        self.db.add(task)
        await self.db.flush()
        return task

    async def delete_task(self, task: ContractTask) -> None:
        await self.db.delete(task)
        await self.db.flush()
