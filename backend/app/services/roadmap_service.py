"""Roadmap 服务：基于案件类型生成办理路线图与待办任务。

Phase 3 采用规则模板（确定性、可离线）。Phase 6 可由 Agent 结合案情动态生成。
生成时会将历史进行中的路线图置为失效，并派生对应 Task 供「下一步」提醒。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.models.case import Case
from app.models.enums import (
    EventTypeEnum,
    PriorityEnum,
    TaskStatusEnum,
)
from app.models.roadmap import Roadmap, RoadmapStep
from app.models.task import Task
from app.repositories.roadmap_repo import RoadmapRepository, RoadmapStepRepository
from app.repositories.task_repo import HistoryRepository, TaskRepository


# 步骤模板：(标题, 说明, 建议第N天执行)
_STEPS: dict[str, list[tuple[str, str, int | None]]] = {
    "rent": [
        ("保存并整理证据", "归集合同、聊天记录、付款凭证、房屋照片等", 0),
        ("向房东发送催告函", "要求按约定退还押金，留存发送记录", 1),
        ("等待房东回应", "给予合理期限（约 7 日）", 2),
        ("向住建部门/街道办投诉", "协商不成可向主管部门或人民调解委员会反映", 9),
        ("申请人民调解", "通过人民调解委员会组织调解", 12),
        ("向人民法院起诉", "准备起诉状与证据，向有管辖权法院立案", 16),
    ],
    "labor": [
        ("保存劳动关系证据", "劳动合同、工资流水、考勤、聊天记录等", 0),
        ("向用人单位发送催告函", "要求支付拖欠工资/补偿", 1),
        ("向劳动监察大队投诉", "举报用人单位违法行为", 3),
        ("申请劳动仲裁", "向劳动合同履行地仲裁委提出申请", 7),
        ("向人民法院起诉", "对仲裁结果不服可于 15 日内起诉", 30),
    ],
    "consumer": [
        ("保存消费凭证", "订单、支付记录、商品照片、聊天记录", 0),
        ("与商家协商", "先行沟通退换货或赔偿", 1),
        ("平台投诉", "通过电商/服务平台发起投诉", 3),
        ("向市场监管/12315 投诉", "拨打 12315 或全国平台投诉", 5),
        ("向人民法院起诉", "准备材料向有管辖权法院起诉", 20),
    ],
    "loan": [
        ("保存借贷证据", "借条、转账记录、催收聊天记录", 0),
        ("发送催款通知", "明确要求还款并保留凭证", 1),
        ("协商还款方案", "尝试达成分期或延期协议", 3),
        ("向人民法院起诉", "准备起诉状与证据立案", 10),
    ],
}

_DEFAULT_STEPS = [
    ("保存证据", "整理与案件相关的全部材料", 0),
    ("咨询专业意见", "就案情获取法律信息参考", 1),
    ("向主管部门投诉", "视情况向对应监管部门反映", 3),
    ("向人民法院起诉", "准备材料向有管辖权法院起诉", 15),
]


class RoadmapService:
    def __init__(self, session) -> None:
        self.roadmaps = RoadmapRepository(session)
        self.steps = RoadmapStepRepository(session)
        self.tasks = TaskRepository(session)
        self.history = HistoryRepository(session)
        self.session = session

    async def generate(self, case: Case) -> Roadmap:
        # 1) 失效历史进行中的路线图
        active = await self.roadmaps.get_active_by_case(case.id)
        if active is not None:
            active.is_active = False
            self.session.add(active)
            await self.session.commit()

        # 2) 创建新路线图
        template = _STEPS.get(case.case_type.value, _DEFAULT_STEPS)
        roadmap = await self.roadmaps.create(
            case_id=case.id,
            title=f"{case.title} · 办理路线图",
            is_active=True,
        )

        # 3) 创建步骤与对应任务
        base_date = datetime.now()
        for order, (title, desc, offset) in enumerate(template, start=1):
            step = await self.steps.create(
                roadmap_id=roadmap.id,
                title=title,
                description=desc,
                order=order,
                due_offset_days=offset,
            )
            due = (base_date + timedelta(days=offset)) if offset is not None else None
            await self.tasks.create(
                case_id=case.id,
                user_id=case.user_id,
                title=title,
                description=desc,
                due_date=due,
                status=TaskStatusEnum.TODO,
                priority=PriorityEnum.MEDIUM,
            )

        await self.history.create(
            case_id=case.id,
            user_id=case.user_id,
            event_type=EventTypeEnum.STATUS_CHANGED,
            title="生成办理路线图",
            detail=roadmap.title,
        )
        # 重新加载以包含 steps
        return await self.roadmaps.get(roadmap.id)  # type: ignore[return-value]

    async def get_active(self, case: Case) -> Roadmap | None:
        return await self.roadmaps.get_active_by_case(case.id)

    async def set_step_status(
        self, case: Case, step: RoadmapStep, status
    ) -> RoadmapStep:
        updated = await self.steps.set_status(step, status)
        # 同步更新对应任务状态（按标题+案件匹配首条未完成任务）
        if status.value == "done":
            stmt = select(Task).where(
                Task.case_id == case.id,
                Task.title == step.title,
                Task.status != TaskStatusEnum.DONE,
            )
            result = await self.session.execute(stmt)
            task = result.scalars().first()
            if task is not None:
                await self.tasks.update(task, status=TaskStatusEnum.DONE)
        return updated
