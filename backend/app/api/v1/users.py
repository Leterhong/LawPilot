"""用户路由：当前用户资料。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserOut, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def get_me(current: User = Depends(get_current_user)) -> UserOut:
    """获取当前登录用户信息。"""
    return current


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UserUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    """更新当前用户资料。"""
    return await UserService(db).update_profile(
        current, body.display_name, body.avatar_url
    )
