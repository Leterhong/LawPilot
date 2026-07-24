"""案件中心路由（Case Center 模块）。

挂载前缀 ``/api/cases``（与 Phase 1 ``/api/v1/cases`` 相互独立，互不冲突）。
核心 9 个 API 按产品规范实现；另补充证据及子资源的 PATCH/DELETE，使详情页各
Tab 可完整编辑（模型已在 7 张表规范内）。全部接口需登录，归属校验失败返回 404。
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.case_center import CaseCenter
from app.models.enums import CaseCenterStatusEnum, CaseTypeEnum
from app.models.user import User
from app.schemas.case_center import (
    CaseAnalysisCreate,
    CaseAnalysisOut,
    CaseCenterCreate,
    CaseCenterDetailOut,
    CaseCenterOut,
    CaseCenterUpdate,
    CaseDocumentCreate,
    CaseDocumentOut,
    CaseDocumentUpdate,
    CaseEvidenceCreate,
    CaseEvidenceOut,
    CaseEvidenceUpdate,
    CaseNoteCreate,
    CaseNoteOut,
    CaseNoteUpdate,
    CaseTaskCreate,
    CaseTaskOut,
    CaseTaskUpdate,
    CaseTimelineCreate,
    CaseTimelineOut,
    CaseTimelineUpdate,
)
from app.schemas.common import Page
from app.services.case_center_service import CaseCenterService

router = APIRouter(prefix="/api/cases", tags=["cases-center"])


# ---------------------------
# 归属校验依赖
# ---------------------------
async def get_owned_case_center(
    case_id: UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseCenter:
    case = await CaseCenterService(db).get_owned(case_id, current)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="案件不存在或无权访问",
        )
    return case


def _svc(db: AsyncSession) -> CaseCenterService:
    return CaseCenterService(db)


# ---------------------------
# 案件卡片 CRUD
# ---------------------------
@router.post("", response_model=CaseCenterOut, status_code=status.HTTP_201_CREATED)
async def create_case(
    body: CaseCenterCreate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseCenterOut:
    """创建案件卡片。"""
    case = await _svc(db).create_case(current, body)
    return CaseCenterOut.model_validate(case)


@router.get("", response_model=Page[CaseCenterOut])
async def list_cases(
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    q: str | None = Query(None, description="按名称搜索"),
    status_filter: CaseCenterStatusEnum | None = Query(None, alias="status", description="状态过滤"),
    case_type: CaseTypeEnum | None = Query(None, description="类型过滤"),
    tag: str | None = Query(None, description="标签过滤"),
    starred: bool | None = Query(None, description="仅星标"),
    favorite: bool | None = Query(None, description="仅收藏"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
) -> Page[CaseCenterOut]:
    """分页列出当前用户的案件卡片，支持搜索/状态/类型/标签/收藏过滤。"""
    return await _svc(db).list_cases(
        current,
        q=q, status=status_filter, case_type=case_type, tag=tag,
        starred=starred, favorite=favorite, page=page, page_size=page_size,
    )


@router.get("/{case_id}", response_model=CaseCenterDetailOut)
async def get_case(
    case: CaseCenter = Depends(get_owned_case_center),
    db: AsyncSession = Depends(get_db),
) -> CaseCenterDetailOut:
    """获取案件详情（聚合全部子资源）。"""
    return await _svc(db).get_detail(case)


@router.put("/{case_id}", response_model=CaseCenterOut)
async def update_case(
    body: CaseCenterUpdate,
    case: CaseCenter = Depends(get_owned_case_center),
    db: AsyncSession = Depends(get_db),
) -> CaseCenterOut:
    """更新案件卡片（部分更新）。"""
    updated = await _svc(db).update_case(case, body)
    return CaseCenterOut.model_validate(updated)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case: CaseCenter = Depends(get_owned_case_center),
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除案件卡片（级联删除子资源）。"""
    await _svc(db).delete_case(case)


# ---------------------------
# AI 分析
# ---------------------------
@router.post("/{case_id}/analysis", response_model=CaseAnalysisOut, status_code=status.HTTP_201_CREATED)
async def add_analysis(
    body: CaseAnalysisCreate,
    case: CaseCenter = Depends(get_owned_case_center),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseAnalysisOut:
    """新增一条 AI 分析；若提交结果则回写卡片概览（Step 4 接入 LLM 自动生成）。"""
    analysis = await _svc(db).add_analysis(current, case, body)
    return CaseAnalysisOut.model_validate(analysis)


# ---------------------------
# 证据（规范 7 表之一，补充 CRUD 使 Tab 可用）
# ---------------------------
@router.post("/{case_id}/evidence", response_model=CaseEvidenceOut, status_code=status.HTTP_201_CREATED)
async def add_evidence(
    body: CaseEvidenceCreate,
    case: CaseCenter = Depends(get_owned_case_center),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseEvidenceOut:
    ev = await _svc(db).add_evidence(current, case, body)
    return CaseEvidenceOut.model_validate(ev)


@router.patch("/{case_id}/evidence/{evidence_id}", response_model=CaseEvidenceOut)
async def update_evidence(
    evidence_id: UUID,
    body: CaseEvidenceUpdate,
    case: CaseCenter = Depends(get_owned_case_center),
    db: AsyncSession = Depends(get_db),
) -> CaseEvidenceOut:
    ev = await _svc(db).get_evidence(evidence_id)
    if ev is None or ev.case_id != case.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="证据不存在")
    ev = await _svc(db).update_evidence(ev, body)
    return CaseEvidenceOut.model_validate(ev)


@router.delete("/{case_id}/evidence/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evidence(
    evidence_id: UUID,
    case: CaseCenter = Depends(get_owned_case_center),
    db: AsyncSession = Depends(get_db),
) -> None:
    ev = await _svc(db).get_evidence(evidence_id)
    if ev is None or ev.case_id != case.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="证据不存在")
    await _svc(db).delete_evidence(ev)


# ---------------------------
# 文书
# ---------------------------
@router.post("/{case_id}/document", response_model=CaseDocumentOut, status_code=status.HTTP_201_CREATED)
async def add_document(
    body: CaseDocumentCreate,
    case: CaseCenter = Depends(get_owned_case_center),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseDocumentOut:
    doc = await _svc(db).add_document(current, case, body)
    return CaseDocumentOut.model_validate(doc)


@router.patch("/{case_id}/document/{document_id}", response_model=CaseDocumentOut)
async def update_document(
    document_id: UUID,
    body: CaseDocumentUpdate,
    case: CaseCenter = Depends(get_owned_case_center),
    db: AsyncSession = Depends(get_db),
) -> CaseDocumentOut:
    doc = await _svc(db).get_document(document_id)
    if doc is None or doc.case_id != case.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文书不存在")
    doc = await _svc(db).update_document(doc, body)
    return CaseDocumentOut.model_validate(doc)


@router.delete("/{case_id}/document/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    case: CaseCenter = Depends(get_owned_case_center),
    db: AsyncSession = Depends(get_db),
) -> None:
    doc = await _svc(db).get_document(document_id)
    if doc is None or doc.case_id != case.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文书不存在")
    await _svc(db).delete_document(doc)


# ---------------------------
# 任务
# ---------------------------
@router.post("/{case_id}/task", response_model=CaseTaskOut, status_code=status.HTTP_201_CREATED)
async def add_task(
    body: CaseTaskCreate,
    case: CaseCenter = Depends(get_owned_case_center),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseTaskOut:
    task = await _svc(db).add_task(current, case, body)
    return CaseTaskOut.model_validate(task)


@router.patch("/{case_id}/task/{task_id}", response_model=CaseTaskOut)
async def update_task(
    task_id: UUID,
    body: CaseTaskUpdate,
    case: CaseCenter = Depends(get_owned_case_center),
    db: AsyncSession = Depends(get_db),
) -> CaseTaskOut:
    task = await _svc(db).get_task(task_id)
    if task is None or task.case_id != case.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    task = await _svc(db).update_task(task, body)
    return CaseTaskOut.model_validate(task)


@router.delete("/{case_id}/task/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    case: CaseCenter = Depends(get_owned_case_center),
    db: AsyncSession = Depends(get_db),
) -> None:
    task = await _svc(db).get_task(task_id)
    if task is None or task.case_id != case.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    await _svc(db).delete_task(task)


# ---------------------------
# 时间线
# ---------------------------
@router.post("/{case_id}/timeline", response_model=CaseTimelineOut, status_code=status.HTTP_201_CREATED)
async def add_timeline(
    body: CaseTimelineCreate,
    case: CaseCenter = Depends(get_owned_case_center),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseTimelineOut:
    tl = await _svc(db).add_timeline(current, case, body)
    return CaseTimelineOut.model_validate(tl)


@router.patch("/{case_id}/timeline/{timeline_id}", response_model=CaseTimelineOut)
async def update_timeline(
    timeline_id: UUID,
    body: CaseTimelineUpdate,
    case: CaseCenter = Depends(get_owned_case_center),
    db: AsyncSession = Depends(get_db),
) -> CaseTimelineOut:
    tl = await _svc(db).get_timeline(timeline_id)
    if tl is None or tl.case_id != case.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="时间线事件不存在")
    tl = await _svc(db).update_timeline(tl, body)
    return CaseTimelineOut.model_validate(tl)


@router.delete("/{case_id}/timeline/{timeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timeline(
    timeline_id: UUID,
    case: CaseCenter = Depends(get_owned_case_center),
    db: AsyncSession = Depends(get_db),
) -> None:
    tl = await _svc(db).get_timeline(timeline_id)
    if tl is None or tl.case_id != case.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="时间线事件不存在")
    await _svc(db).delete_timeline(tl)


# ---------------------------
# 备注
# ---------------------------
@router.post("/{case_id}/note", response_model=CaseNoteOut, status_code=status.HTTP_201_CREATED)
async def add_note(
    body: CaseNoteCreate,
    case: CaseCenter = Depends(get_owned_case_center),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseNoteOut:
    note = await _svc(db).add_note(current, case, body)
    return CaseNoteOut.model_validate(note)


@router.patch("/{case_id}/note/{note_id}", response_model=CaseNoteOut)
async def update_note(
    note_id: UUID,
    body: CaseNoteUpdate,
    case: CaseCenter = Depends(get_owned_case_center),
    db: AsyncSession = Depends(get_db),
) -> CaseNoteOut:
    note = await _svc(db).get_note(note_id)
    if note is None or note.case_id != case.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="备注不存在")
    note = await _svc(db).update_note(note, body)
    return CaseNoteOut.model_validate(note)


@router.delete("/{case_id}/note/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: UUID,
    case: CaseCenter = Depends(get_owned_case_center),
    db: AsyncSession = Depends(get_db),
) -> None:
    note = await _svc(db).get_note(note_id)
    if note is None or note.case_id != case.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="备注不存在")
    await _svc(db).delete_note(note)
