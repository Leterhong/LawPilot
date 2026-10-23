"""法律搜索引擎路由（Law Search 模块）。

挂载前缀 ``/api/laws``，自动进入 Swagger。
``search`` / ``detail`` / ``recommend`` 公开；``history`` 需登录（归属当前用户）。
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
from app.schemas.law import (
    LawDetail,
    LawHistoryOut,
    LawOut,
    LawSearchResult,
)
from app.services.law_search_service import LawSearchService

router = APIRouter(prefix="/api/laws", tags=["laws"])

# 匿名可搜索：可选用户依赖（登录则记录归属历史）
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
        from jose import JWTError

        from app.core.security import decode_access_token
        from app.repositories.user_repo import UserRepository

        payload = decode_access_token(token)
        subject = payload.get("sub")
        if not subject:
            return None
        user = await UserRepository(db).get(UUID(subject))
        return user if (user and user.is_active) else None
    except (JWTError, ValueError, Exception):
        return None


@router.get("/search", response_model=LawSearchResult)
async def search(
    q: str = Query(..., min_length=1, description="搜索词（法律名/条款号/关键词/组合/自然语言）"),
    status: str | None = Query(None, description="按现状过滤：effective/amended/repealed/pending"),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(optional_current_user),
) -> LawSearchResult:
    """法律搜索：支持法律名 / 条款号 / 全文 / 组合检索。"""
    return await LawSearchService(db).search(
        q, current_user=current_user, status=status, limit=limit, offset=offset
    )


@router.get("/detail/{law_id}", response_model=LawDetail)
async def detail(
    law_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> LawDetail:
    """法条详情：完整正文 + 上/下条 + 相关法条 + 司法解释 + 案例 + 推荐。"""
    result = await LawSearchService(db).detail(law_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="法条不存在")
    return result


@router.get("/recommend", response_model=list[LawOut])
async def recommend(
    law_id: UUID | None = Query(None, description="基于某法条推荐；缺省返回最新录入"),
    limit: int = Query(6, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
) -> list[LawOut]:
    """相关推荐（同法其它条优先，关键词相似补足；缺省返回最新）。"""
    return await LawSearchService(db).recommend(law_id, limit)


@router.get("/history", response_model=list[LawHistoryOut])
async def history(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LawHistoryOut]:
    """当前用户的最近搜索历史。"""
    return await LawSearchService(db).history(current_user, limit)
