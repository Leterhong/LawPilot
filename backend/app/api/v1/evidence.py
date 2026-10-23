"""证据路由：上传证据（含 OCR）与添加规划证据。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, get_owned_case
from app.models.case import Case
from app.models.user import User
from app.repositories.case_repo import EvidenceRepository
from app.schemas.evidence import EvidenceOut, EvidencePlannedCreate
from app.services.evidence_service import EvidenceService

router = APIRouter(prefix="/cases/{case_id}/evidence", tags=["evidence"])


@router.post("", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    case: Case = Depends(get_owned_case),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    category: str = Form(...),
    title: str | None = Form(None),
    description: str | None = Form(None),
) -> EvidenceOut:
    """上传证据文件（PDF/DOCX/TXT/PNG/JPG），自动落库并尝试 OCR/文本提取。"""
    from app.models.enums import EvidenceCategoryEnum

    try:
        cat = EvidenceCategoryEnum(category)
    except ValueError:
        raise HTTPException(status_code=400, detail="证据类别无效")
    service = EvidenceService(db)
    try:
        return await service.add_uploaded(case, current, file, cat, title, description)
    except ValueError as exc:
        code = exc.args[0] if exc.args else ""
        if code == "BAD_EXTENSION":
            raise HTTPException(status_code=400, detail="不支持的文件类型")
        if code == "FILE_TOO_LARGE":
            raise HTTPException(status_code=400, detail="文件超过大小限制")
        raise


@router.post(
    "/planned", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED
)
async def add_planned_evidence(
    body: EvidencePlannedCreate,
    case: Case = Depends(get_owned_case),
    db: AsyncSession = Depends(get_db),
) -> EvidenceOut:
    """添加「规划中但尚未提供」的证据项（由 AI 建议、用户尚未上传）。"""
    return await EvidenceService(db).add_planned(
        case, body.category, body.title, body.description, body.ai_note
    )


@router.get("", response_model=list[EvidenceOut])
async def list_evidence(
    case: Case = Depends(get_owned_case),
    db: AsyncSession = Depends(get_db),
) -> list[EvidenceOut]:
    """列出案件全部证据。"""
    return await EvidenceRepository(db).list(case_id=case.id)
