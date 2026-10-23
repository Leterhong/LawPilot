"""Roadmap 仓储：Roadmap / RoadmapStep。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.roadmap import Roadmap, RoadmapStep
from app.repositories.base import BaseRepository


class RoadmapRepository(BaseRepository[Roadmap]):
    model = Roadmap

    async def get_active_by_case(self, case_id) -> Roadmap | None:
        stmt = select(Roadmap).options(selectinload(Roadmap.steps)).where(
            Roadmap.case_id == case_id, Roadmap.is_active.is_(True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get(self, obj_id) -> Roadmap | None:
        """按主键查询（一并加载步骤，避免异步懒加载）。"""
        stmt = select(Roadmap).options(selectinload(Roadmap.steps)).where(
            Roadmap.id == obj_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class RoadmapStepRepository(BaseRepository[RoadmapStep]):
    model = RoadmapStep

    async def set_status(
        self, step: RoadmapStep, status
    ) -> RoadmapStep:
        """更新步骤状态，并据状态维护 completed_at。"""
        step.status = status
        step.completed_at = datetime.now() if status.value == "done" else None
        self.session.add(step)
        await self.session.commit()
        await self.session.refresh(step)
        return step
