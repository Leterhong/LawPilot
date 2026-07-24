"""法律检索仓储：LegalReference / Knowledge。

Phase 3 提供关键词/类型检索（真实可用）。Phase 5 将在此基础上叠加
pgvector 语义检索形成混合检索（Hybrid Search）。
"""
from __future__ import annotations

from typing import Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LegalSourceEnum
from app.models.knowledge import Knowledge
from app.models.legal_reference import LegalReference
from app.repositories.base import BaseRepository


class LegalReferenceRepository(BaseRepository[LegalReference]):
    model = LegalReference

    async def search(
        self, q: str, source: LegalSourceEnum | None, limit: int, offset: int
    ) -> Tuple[list[LegalReference], int]:
        """关键词检索法律条文，返回 (结果列表, 总数)。"""
        pattern = f"%{q}%"
        stmt = select(LegalReference).where(
            or_(
                LegalReference.title.ilike(pattern),
                LegalReference.content.ilike(pattern),
                LegalReference.article.ilike(pattern),
            )
        )
        if source is not None:
            stmt = stmt.where(LegalReference.source == source)

        total = await self.session.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        rows = await self.session.execute(
            stmt.order_by(LegalReference.source).offset(offset).limit(limit)
        )
        return list(rows.scalars().all()), int(total or 0)


class KnowledgeRepository(BaseRepository[Knowledge]):
    model = Knowledge

    async def search(
        self, q: str, category: LegalSourceEnum | None, limit: int, offset: int
    ) -> Tuple[list[Knowledge], int]:
        """关键词检索知识条目，返回 (结果列表, 总数)。"""
        pattern = f"%{q}%"
        stmt = select(Knowledge).where(
            or_(
                Knowledge.title.ilike(pattern),
                Knowledge.content.ilike(pattern),
            )
        )
        if category is not None:
            stmt = stmt.where(Knowledge.category == category)

        total = await self.session.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        rows = await self.session.execute(stmt.offset(offset).limit(limit))
        return list(rows.scalars().all()), int(total or 0)
