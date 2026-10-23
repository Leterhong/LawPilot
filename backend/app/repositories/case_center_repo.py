"""案件中心仓储（Case Center 模块）。

集中 7 个实体的通用 CRUD；列表查询针对案件卡片提供搜索/标签/状态/收藏过滤，
并按 ``position`` 排序（拖拽排序）。各子资源均提供按 ``case_id`` 的列表与归属校验。
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import JSONB

from app.models.case_center import (
    CaseAnalysis,
    CaseCenter,
    CaseDocument,
    CaseEvidence,
    CaseNote,
    CaseTask,
    CaseTimeline,
)
from app.repositories.base import BaseRepository


class CaseCenterRepository(BaseRepository[CaseCenter]):
    model = CaseCenter

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        q: str | None = None,
        status=None,
        case_type=None,
        tag: str | None = None,
        starred: bool | None = None,
        favorite: bool | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[CaseCenter]:
        """当前用户的案件卡片列表（搜索/过滤/排序）。"""
        stmt = select(CaseCenter).where(CaseCenter.user_id == user_id)
        if q:
            stmt = stmt.where(CaseCenter.title.ilike(f"%{q}%"))
        if status is not None:
            stmt = stmt.where(CaseCenter.status == status)
        if case_type is not None:
            stmt = stmt.where(CaseCenter.case_type == case_type)
        if tag is not None:
            # tags 为 JSON 数组，强转 JSONB 后使用 @> 包含判断
            stmt = stmt.where(CaseCenter.tags.cast(JSONB).contains([tag]))
        if starred is not None:
            stmt = stmt.where(CaseCenter.starred == starred)
        if favorite is not None:
            stmt = stmt.where(CaseCenter.favorite == favorite)
        stmt = stmt.order_by(CaseCenter.position.asc(), CaseCenter.updated_at.desc())
        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_user(
        self,
        user_id: UUID,
        *,
        q: str | None = None,
        status=None,
        case_type=None,
        tag: str | None = None,
        starred: bool | None = None,
        favorite: bool | None = None,
    ) -> int:
        """与 ``list_for_user`` 同条件的计数。"""
        from sqlalchemy import func

        stmt = select(func.count()).select_from(CaseCenter).where(CaseCenter.user_id == user_id)
        if q:
            stmt = stmt.where(CaseCenter.title.ilike(f"%{q}%"))
        if status is not None:
            stmt = stmt.where(CaseCenter.status == status)
        if case_type is not None:
            stmt = stmt.where(CaseCenter.case_type == case_type)
        if tag is not None:
            stmt = stmt.where(CaseCenter.tags.cast(JSONB).contains([tag]))
        if starred is not None:
            stmt = stmt.where(CaseCenter.starred == starred)
        if favorite is not None:
            stmt = stmt.where(CaseCenter.favorite == favorite)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def max_position(self, user_id: UUID) -> int:
        """返回该用户当前最大 position（用于新卡片追加到末尾）。"""
        stmt = select(func.max(CaseCenter.position)).where(CaseCenter.user_id == user_id)
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return int(val) if val is not None else 0


class CaseAnalysisRepository(BaseRepository[CaseAnalysis]):
    model = CaseAnalysis

    async def list_by_case(self, case_id: UUID) -> list[CaseAnalysis]:
        stmt = select(CaseAnalysis).where(CaseAnalysis.case_id == case_id).order_by(CaseAnalysis.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class CaseEvidenceRepository(BaseRepository[CaseEvidence]):
    model = CaseEvidence

    async def list_by_case(self, case_id: UUID) -> list[CaseEvidence]:
        stmt = select(CaseEvidence).where(CaseEvidence.case_id == case_id).order_by(CaseEvidence.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class CaseDocumentRepository(BaseRepository[CaseDocument]):
    model = CaseDocument

    async def list_by_case(self, case_id: UUID) -> list[CaseDocument]:
        stmt = select(CaseDocument).where(CaseDocument.case_id == case_id).order_by(CaseDocument.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class CaseTaskRepository(BaseRepository[CaseTask]):
    model = CaseTask

    async def list_by_case(self, case_id: UUID) -> list[CaseTask]:
        stmt = select(CaseTask).where(CaseTask.case_id == case_id).order_by(CaseTask.position)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class CaseTimelineRepository(BaseRepository[CaseTimeline]):
    model = CaseTimeline

    async def list_by_case(self, case_id: UUID) -> list[CaseTimeline]:
        stmt = select(CaseTimeline).where(CaseTimeline.case_id == case_id).order_by(CaseTimeline.occurred_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class CaseNoteRepository(BaseRepository[CaseNote]):
    model = CaseNote

    async def list_by_case(self, case_id: UUID) -> list[CaseNote]:
        stmt = select(CaseNote).where(CaseNote.case_id == case_id).order_by(CaseNote.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
