"""案例搜索路由（Legal Case Search 模块）。

挂载前缀 ``/api/legal-cases``（规范原写 /api/cases，但已被案件中心占用，故独立前缀）。
- ``/search`` ``/filter`` ``/{id}`` 公开（无需登录，便于搜索引擎式体验）；
- ``/similar`` ``/favorites`` 及收藏写操作需登录（归属当前用户）。
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.legal_case import (
    CaseFilterFacets,
    LegalCaseDetail,
    LegalCaseSearchResult,
    SimilarCaseRequest,
)
from app.services.legal_case_search_service import LegalCaseSearchService

router = APIRouter(prefix="/api/legal-cases", tags=["legal-cases"])

# 匿名可搜索：可选用户依赖
oauth2_scheme_opt = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_v1_prefix}/auth/login", auto_error=False
)


async def optional_current_user(
    token: str = Depends(oauth2_scheme_opt),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if not token:
        return None
    try:
        from app.core.security import decode_access_token
        from app.repositories.user_repo import UserRepository
        from jose import JWTError

        payload = decode_access_token(token)
        subject = payload.get("sub")
        if not subject:
            return None
        user = await UserRepository(db).get(UUID(subject))
        return user if (user and user.is_active) else None
    except (JWTError, ValueError, Exception):
        return None


@router.get("/search", response_model=LegalCaseSearchResult)
async def search(
    q: str = Query(..., min_length=1, description="搜索词（关键词/案由/自然语言）"),
    province: str | None = Query(None, description="省份过滤"),
    city: str | None = Query(None, description="城市过滤"),
    court_level: str | None = Query(None, description="法院级别：basic/intermediate/advanced/supreme"),
    case_type: str | None = Query(None, description="案件类型：civil/labor/contract/consumer/other"),
    time_range: str | None = Query(None, description="时间范围：1y/5y/all"),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> LegalCaseSearchResult:
    """案例搜索：关键词 / 语义 / 条件过滤 + 重排。"""
    return await LegalCaseSearchService(db).search(
        q,
        province=province,
        city=city,
        court_level=court_level,
        case_type=case_type,
        time_range=time_range,
        limit=limit,
        offset=offset,
    )


@router.get("/filter", response_model=CaseFilterFacets)
async def filter_facets(
    db: AsyncSession = Depends(get_db),
) -> CaseFilterFacets:
    """返回可过滤面（省份 / 城市 / 法院级别 / 案件类型 / 时间范围）。"""
    return await LegalCaseSearchService(db).filter_facets()


@router.get("/{case_id}", response_model=LegalCaseDetail)
async def detail(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> LegalCaseDetail:
    """案例详情：事实 / 法院观点 / 裁判结果 / 关联法条。"""
    result = await LegalCaseSearchService(db).detail(case_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="案例不存在")
    return result


@router.post("/similar", response_model=LegalCaseSearchResult)
async def similar(
    body: SimilarCaseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LegalCaseSearchResult:
    """查找类似案例：根据用户案件自动提取关键词（或查询文本）返回 TOP N。"""
    return await LegalCaseSearchService(db).similar(body, current_user)


@router.get("/user/favorites", response_model=LegalCaseSearchResult)
async def list_favorites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LegalCaseSearchResult:
    """当前用户收藏的案例。"""
    return await LegalCaseSearchService(db).list_favorites(current_user)


@router.post("/{case_id}/favorite", status_code=status.HTTP_200_OK)
async def add_favorite(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """收藏案例。"""
    ok = await LegalCaseSearchService(db).add_favorite(current_user, case_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="案例不存在")
    return {"ok": True}


@router.delete("/{case_id}/favorite", status_code=status.HTTP_200_OK)
async def remove_favorite(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """取消收藏案例。"""
    ok = await LegalCaseSearchService(db).remove_favorite(current_user, case_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="案例不存在")
    return {"ok": True}
