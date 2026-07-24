"""认证路由：注册 / 登录。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    body: UserCreate, db: AsyncSession = Depends(get_db)
) -> UserOut:
    """注册新用户。邮箱已存在返回 409。"""
    service = AuthService(db)
    try:
        user = await service.register(body.email, body.password, body.display_name)
    except ValueError as exc:  # 语义错误码
        if exc.args and exc.args[0] == "EMAIL_EXISTS":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="该邮箱已注册"
            )
        raise
    return user


@router.post("/login", response_model=Token)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    """登录获取访问令牌（Swagger Authorize 使用此密码流）。"""
    service = AuthService(db)
    user = await service.authenticate(form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误"
        )
    return Token(access_token=service.issue_token(user))
