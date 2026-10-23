"""案件聚合仓储：Case / Message / Evidence / Document / Workflow。

这些实体均围绕案件（Case）组织，集中于此便于事务与联查。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.models.case import Case
from app.models.document import Document
from app.models.evidence import Evidence
from app.models.message import Message
from app.models.workflow import Workflow
from app.repositories.base import BaseRepository


class CaseRepository(BaseRepository[Case]):
    model = Case


class MessageRepository(BaseRepository[Message]):
    model = Message

    async def next_sequence(self, case_id) -> int:
        """返回该案件下一条消息的序号（现有最大序号 + 1）。"""
        stmt = select(Message.sequence).where(Message.case_id == case_id)
        result = await self.session.execute(stmt)
        seqs = [s for s in result.scalars().all()]
        return (max(seqs) + 1) if seqs else 1


class EvidenceRepository(BaseRepository[Evidence]):
    model = Evidence


class DocumentRepository(BaseRepository[Document]):
    model = Document


class WorkflowRepository(BaseRepository[Workflow]):
    model = Workflow

    async def get_by_case(self, case_id) -> Workflow | None:
        return await self.find(case_id=case_id)

    async def touch(self, workflow: Workflow) -> Workflow:
        """更新 updated_at 时间戳（状态变更时调用）。"""
        workflow.updated_at = datetime.now()
        self.session.add(workflow)
        await self.session.commit()
        await self.session.refresh(workflow)
        return workflow
