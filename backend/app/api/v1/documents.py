"""文书路由：生成与列出法律文书。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, get_owned_case
from app.models.case import Case
from app.models.user import User
from app.schemas.document import DocumentGenerate, DocumentOut
from app.services.document_service import DocumentService

router = APIRouter(prefix="/cases/{case_id}/documents", tags=["documents"])


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def generate_document(
    body: DocumentGenerate,
    case: Case = Depends(get_owned_case),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    """按类型生成法律文书（催告函/律师函/投诉书/仲裁申请书/起诉状/答辩状/证据目录）。"""
    try:
        return await DocumentService(db).generate(case, current, body.doc_type, body.extra)
    except ValueError as exc:
        if exc.args and exc.args[0] == "UNSUPPORTED_DOC_TYPE":
            raise HTTPException(status_code=400, detail="不支持的文书类型")
        raise


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    case: Case = Depends(get_owned_case),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentOut]:
    """列出案件全部文书。"""
    return await DocumentService(db).list_by_case(case)
