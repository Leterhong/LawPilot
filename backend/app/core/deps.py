"""FastAPI 依赖注入。

提供：
- ``get_current_user``：从 Bearer 令牌解析并校验当前用户（保护路由）。
"""
from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.case import Case
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.case_service import CaseService

# tokenUrl 指向登录接口，供 Swagger "Authorize" 使用密码流
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_v1_prefix}/auth/login", auto_error=True
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """解析 Bearer 令牌并返回当前用户，失败返回 401。"""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效或过期的凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if not subject:
            raise credentials_exc
        user_id = UUID(subject)
    except (JWTError, ValueError):
        raise credentials_exc

    user = await UserRepository(db).get(user_id)
    if user is None or not user.is_active:
        raise credentials_exc
    return user


async def get_owned_case(
    case_id: UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Case:
    """解析路径中的 case_id 并校验归属，非本人或无则 404。"""
    case = await CaseService(db).get_owned(case_id, current)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="案件不存在或无权访问",
        )
    return case


async def require_superuser(
    current: User = Depends(get_current_user),
) -> User:
    """仅超级管理员可访问（AI 能力中心后台）。

    非超管返回 403。
    """
    if not current.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要超级管理员权限",
        )
    return current
