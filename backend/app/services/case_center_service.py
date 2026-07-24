"""案件中心服务（Case Center 模块编排）。

负责案件卡片 CRUD、聚合详情、AI 分析（含概览自动同步）、证据/文书/任务/时间线/
备注的子资源创建。AI 自动生成（Step 4）通过 ``_generate_analysis`` 钩子接入，
当前在无可用 LLM 时优雅降级：接受前端提交的分析结果并回写卡片概览字段。
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case_center import (
    CaseAnalysis,
    CaseCenter,
    CaseDocument,
    CaseEvidence,
    CaseNote,
    CaseTask,
    CaseTimeline,
)
from app.models.enums import (
    CaseCenterStatusEnum,
    CaseTypeEnum,
    DocStatusEnum,
    DocTypeEnum,
    EvidenceCategoryEnum,
    PriorityEnum,
    TaskStatusEnum,
)
from app.models.user import User
from app.repositories.case_center_repo import (
    CaseAnalysisRepository,
    CaseCenterRepository,
    CaseDocumentRepository,
    CaseEvidenceRepository,
    CaseNoteRepository,
    CaseTaskRepository,
    CaseTimelineRepository,
)
from app.schemas.case_center import (
    CaseAnalysisCreate,
    CaseAnalysisOut,
    CaseCenterCreate,
    CaseCenterDetailOut,
    CaseCenterOut,
    CaseCenterUpdate,
    CaseDocumentCreate,
    CaseDocumentOut,
    CaseEvidenceCreate,
    CaseEvidenceOut,
    CaseNoteCreate,
    CaseNoteOut,
    CaseTaskCreate,
    CaseTaskOut,
    CaseTimelineCreate,
    CaseTimelineOut,
)
from app.schemas.common import Page


class CaseCenterService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.cases: CaseCenterRepository = CaseCenterRepository(session)
        self.analyses: CaseAnalysisRepository = CaseAnalysisRepository(session)
        self.evidences: CaseEvidenceRepository = CaseEvidenceRepository(session)
        self.documents: CaseDocumentRepository = CaseDocumentRepository(session)
        self.tasks: CaseTaskRepository = CaseTaskRepository(session)
        self.timelines: CaseTimelineRepository = CaseTimelineRepository(session)
        self.notes: CaseNoteRepository = CaseNoteRepository(session)

    # ---------------------------
    # 案件卡片
    # ---------------------------
    async def create_case(self, user: User, body: CaseCenterCreate) -> CaseCenter:
        data = body.model_dump(exclude_unset=True)
        # 负责人默认当前用户昵称
        if data.get("owner") is None:
            data["owner"] = user.display_name or user.email
        # 排序追加到末尾
        if data.get("position") is None:
            data["position"] = await self.cases.max_position(user.id) + 1
        return await self.cases.create(user_id=user.id, **data)

    async def list_cases(
        self,
        user: User,
        *,
        q: str | None = None,
        status: CaseCenterStatusEnum | None = None,
        case_type: CaseTypeEnum | None = None,
        tag: str | None = None,
        starred: bool | None = None,
        favorite: bool | None = None,
        page: int = 1,
        page_size: int = 12,
    ) -> Page[CaseCenterOut]:
        total = await self.cases.count_for_user(
            user.id, q=q, status=status, case_type=case_type, tag=tag,
            starred=starred, favorite=favorite,
        )
        rows = await self.cases.list_for_user(
            user.id, q=q, status=status, case_type=case_type, tag=tag,
            starred=starred, favorite=favorite,
            skip=(page - 1) * page_size, limit=page_size,
        )
        return Page[CaseCenterOut].create(
            [CaseCenterOut.model_validate(c) for c in rows], total, page, page_size
        )

    async def get_owned(self, case_id: UUID, user: User) -> CaseCenter | None:
        case = await self.cases.get(case_id)
        if case is None or case.user_id != user.id:
            return None
        return case

    async def get_detail(self, case: CaseCenter) -> CaseCenterDetailOut:
        return CaseCenterDetailOut(
            case=CaseCenterOut.model_validate(case),
            analyses=[CaseAnalysisOut.model_validate(a) for a in await self.analyses.list_by_case(case.id)],
            evidences=[CaseEvidenceOut.model_validate(e) for e in await self.evidences.list_by_case(case.id)],
            documents=[CaseDocumentOut.model_validate(d) for d in await self.documents.list_by_case(case.id)],
            tasks=[CaseTaskOut.model_validate(t) for t in await self.tasks.list_by_case(case.id)],
            timelines=[CaseTimelineOut.model_validate(t) for t in await self.timelines.list_by_case(case.id)],
            notes=[CaseNoteOut.model_validate(n) for n in await self.notes.list_by_case(case.id)],
        )

    async def update_case(self, case: CaseCenter, body: CaseCenterUpdate) -> CaseCenter:
        changed = body.model_dump(exclude_unset=True)
        return await self.cases.update(case, **changed)

    async def delete_case(self, case: CaseCenter) -> None:
        await self.cases.delete(case)

    # ---------------------------
    # AI 分析（含概览自动同步）
    # ---------------------------
    async def add_analysis(
        self, user: User, case: CaseCenter, body: CaseAnalysisCreate
    ) -> CaseAnalysis:
        data = body.model_dump(exclude_unset=True)
        # 若前端未提交摘要/风险，且有可用 LLM，则自动生成分析结果
        manual = bool(data.get("summary") or data.get("risk"))
        if not manual:
            generated = await self._generate_analysis(case)
            if generated:
                # 仅用 LLM 产出的字段补全；手动字段（若有）保持优先
                for k, v in generated.items():
                    data.setdefault(k, v)
        analysis = await self.analyses.create(
            case_id=case.id, user_id=user.id, **data
        )
        # 分析完成后自动同步：状态采纳 / 下一步生成任务 / 时间线留痕
        await self._auto_sync_after_analysis(user, case, analysis)
        return analysis

    async def _auto_sync_after_analysis(
        self, user: User, case: CaseCenter, analysis: CaseAnalysis
    ) -> None:
        """分析完成后的自动同步（Step 4）。

        - 若分析给出建议状态，自动采纳到卡片状态；
        - 将下一步行动逐条生成为待办任务（按标题去重）；
        - 在时间线记录一次 AI 分析事件。
        任何一步失败都不影响分析本身的保存。
        """
        try:
            # 1) 自动采纳建议状态
            suggested = analysis.suggested_status
            if suggested is not None and suggested != case.status:
                await self.cases.update(case, status=suggested)
            # 2) 下一步 -> 任务（去重）
            steps = analysis.next_steps or []
            if steps:
                existing = {t.title for t in await self.tasks.list_by_case(case.id)}
                for step in steps:
                    if step and step.strip() and step.strip() not in existing:
                        await self.tasks.create(
                            case_id=case.id,
                            user_id=user.id,
                            title=step.strip(),
                            status=TaskStatusEnum.TODO,
                            priority=PriorityEnum.MEDIUM,
                        )
                        existing.add(step.strip())
            # 3) 时间线留痕
            await self.timelines.create(
                case_id=case.id,
                user_id=user.id,
                event_type="ai_analysis",
                title="AI 分析完成",
                detail=(analysis.summary or "")[:200] or None,
                occurred_at=datetime.now(),
            )
        except Exception:
            # 自动同步失败仅记录，不阻断主流程
            pass

    async def _generate_analysis(self, case: CaseCenter) -> dict | None:
        """Step 4：调用 LLM 生成结构化分析。

        以案件描述 + 证据 + 任务 + 时间线 + 备注为上下文，要求模型返回 JSON：
        ``summary`` / ``risk`` / ``risk_level`` / ``suggested_status`` / ``next_steps``。
        无可用 LLM 或解析失败时返回 None（优雅降级，由前端提交结果）。
        """
        from app.services.llm.client import LLMClient

        llm = LLMClient(db=self.session, feature="case_overview")
        if not await llm.available_async():
            return None

        # 收集上下文
        evidences = await self.evidences.list_by_case(case.id)
        tasks = await self.tasks.list_by_case(case.id)
        timelines = await self.timelines.list_by_case(case.id)
        notes = await self.notes.list_by_case(case.id)

        ev_text = "\n".join(
            f"- [{e.category.value}] {e.title}（{'已提供' if e.is_uploaded else '待补充'}）"
            for e in evidences
        ) or "（暂无）"
        task_text = "\n".join(f"- {t.title}（{t.status.value}）" for t in tasks) or "（暂无）"
        tl_text = "\n".join(f"- {t.title}" for t in timelines) or "（暂无）"
        note_text = "\n".join(f"- {n.content}" for n in notes) or "（暂无）"

        valid_status = " / ".join(s.value for s in CaseCenterStatusEnum)
        system = (
            "你是专业的中国法律维权助手。请基于用户提供的案件信息，输出严格 JSON："
            "{\"summary\":\"案情摘要\",\"risk\":\"风险分析\",\"risk_level\":\"low|medium|high\","
            "\"suggested_status\":\"建议的案件状态\",\"next_steps\":[\"下一步1\",\"下一步2\"]}。"
            f"建议状态只能从以下枚举中选择：{valid_status}。不要输出 JSON 之外的任何内容。"
        )
        user_prompt = (
            f"案件名称：{case.title}\n"
            f"案件类型：{case.case_type.value}\n"
            f"当前状态：{case.status.value}\n"
            f"用户描述：{case.description or '（无）'}\n\n"
            f"证据清单：\n{ev_text}\n\n"
            f"已有任务：\n{task_text}\n\n"
            f"时间线：\n{tl_text}\n\n"
            f"备注：\n{note_text}\n"
        )
        result = await llm.complete_json(user_prompt, system=system, temperature=0.2)
        if not result:
            return None

        # 校验并规整字段
        summary = (result.get("summary") or "").strip() or None
        risk = (result.get("risk") or "").strip() or None
        risk_level = (result.get("risk_level") or "").strip().lower()
        if risk_level not in ("low", "medium", "high"):
            risk_level = None
        suggested_raw = (result.get("suggested_status") or "").strip()
        suggested = None
        try:
            suggested = CaseCenterStatusEnum(suggested_raw)
        except ValueError:
            suggested = None
        next_steps = result.get("next_steps") or []
        if isinstance(next_steps, list):
            next_steps = [str(s).strip() for s in next_steps if str(s).strip()]
        else:
            next_steps = []

        return {
            "summary": summary,
            "risk": risk,
            "risk_level": risk_level,
            "suggested_status": suggested,
            "next_steps": next_steps,
        }

    # ---------------------------
    # 证据
    # ---------------------------
    async def add_evidence(self, user: User, case: CaseCenter, body: CaseEvidenceCreate) -> CaseEvidence:
        return await self.evidences.create(case_id=case.id, user_id=user.id, **body.model_dump())

    async def update_evidence(self, ev: CaseEvidence, body) -> CaseEvidence:
        return await self.evidences.update(ev, **body.model_dump(exclude_unset=True))

    async def delete_evidence(self, ev: CaseEvidence) -> None:
        await self.evidences.delete(ev)

    async def get_evidence(self, evidence_id: UUID) -> CaseEvidence | None:
        return await self.evidences.get(evidence_id)

    # ---------------------------
    # 文书
    # ---------------------------
    async def add_document(self, user: User, case: CaseCenter, body: CaseDocumentCreate) -> CaseDocument:
        data = body.model_dump(exclude_unset=True)
        if data.get("status") is None:
            data["status"] = DocStatusEnum.DRAFT
        return await self.documents.create(case_id=case.id, user_id=user.id, **data)

    async def update_document(self, doc: CaseDocument, body) -> CaseDocument:
        return await self.documents.update(doc, **body.model_dump(exclude_unset=True))

    async def delete_document(self, doc: CaseDocument) -> None:
        await self.documents.delete(doc)

    async def get_document(self, doc_id: UUID) -> CaseDocument | None:
        return await self.documents.get(doc_id)

    # ---------------------------
    # 任务
    # ---------------------------
    async def add_task(self, user: User, case: CaseCenter, body: CaseTaskCreate) -> CaseTask:
        data = body.model_dump(exclude_unset=True)
        if data.get("status") is None:
            data["status"] = TaskStatusEnum.TODO
        if data.get("priority") is None:
            data["priority"] = PriorityEnum.MEDIUM
        # 排序追加到末尾
        from sqlalchemy import func, select

        stmt = select(func.max(CaseTask.position)).where(CaseTask.case_id == case.id)
        res = await self.session.execute(stmt)
        max_pos = res.scalar_one_or_none() or 0
        if data.get("position") is None:
            data["position"] = max_pos + 1
        return await self.tasks.create(case_id=case.id, user_id=user.id, **data)

    async def update_task(self, task: CaseTask, body) -> CaseTask:
        return await self.tasks.update(task, **body.model_dump(exclude_unset=True))

    async def delete_task(self, task: CaseTask) -> None:
        await self.tasks.delete(task)

    async def get_task(self, task_id: UUID) -> CaseTask | None:
        return await self.tasks.get(task_id)

    # ---------------------------
    # 时间线
    # ---------------------------
    async def add_timeline(self, user: User, case: CaseCenter, body: CaseTimelineCreate) -> CaseTimeline:
        data = body.model_dump(exclude_unset=True)
        if data.get("occurred_at") is None:
            data["occurred_at"] = datetime.now()
        return await self.timelines.create(case_id=case.id, user_id=user.id, **data)

    async def update_timeline(self, tl: CaseTimeline, body) -> CaseTimeline:
        return await self.timelines.update(tl, **body.model_dump(exclude_unset=True))

    async def delete_timeline(self, tl: CaseTimeline) -> None:
        await self.timelines.delete(tl)

    async def get_timeline(self, tl_id: UUID) -> CaseTimeline | None:
        return await self.timelines.get(tl_id)

    # ---------------------------
    # 备注
    # ---------------------------
    async def add_note(self, user: User, case: CaseCenter, body: CaseNoteCreate) -> CaseNote:
        return await self.notes.create(case_id=case.id, user_id=user.id, **body.model_dump())

    async def update_note(self, note: CaseNote, body) -> CaseNote:
        return await self.notes.update(note, **body.model_dump(exclude_unset=True))

    async def delete_note(self, note: CaseNote) -> None:
        await self.notes.delete(note)

    async def get_note(self, note_id: UUID) -> CaseNote | None:
        return await self.notes.get(note_id)
