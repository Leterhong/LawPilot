"""law_search_history 表仓储。"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.law_search_history import LawSearchHistory


class LawSearchHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self, query: str, user_id: UUID | None = None, result_count: int | None = None
    ) -> LawSearchHistory:
        obj = LawSearchHistory(
            query=query, user_id=user_id, result_count=result_count
        )
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def list_recent_by_user(self, user_id: UUID, limit: int = 20):
        stmt = (
            select(LawSearchHistory)
            .where(LawSearchHistory.user_id == user_id)
            .order_by(LawSearchHistory.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def hot(self, limit: int = 10):
        """聚合去重后的热门查询词（按出现次数）。"""
        stmt = (
            select(LawSearchHistory.query, func.count().label("cnt"))
            .group_by(LawSearchHistory.query)
            .order_by(func.count().desc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).all()
