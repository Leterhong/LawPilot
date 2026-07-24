"""认证服务：注册、登录、签发令牌。

保持框架无关：领域错误以 ``ValueError`` 抛出（带语义码），
由路由层映射为对应的 HTTP 状态码。
"""
from __future__ import annotations

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repo import UserRepository


class AuthService:
    def __init__(self, session) -> None:
        self.repo = UserRepository(session)

    async def register(
        self, email: str, password: str, display_name: str | None = None
    ) -> User:
        if await self.repo.get_by_email(email):
            raise ValueError("EMAIL_EXISTS")
        return await self.repo.create(
            email=email,
            hashed_password=hash_password(password),
            display_name=display_name,
        )

    async def authenticate(self, email: str, password: str) -> User | None:
        user = await self.repo.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            return None
        return user

    def issue_token(self, user: User) -> str:
        return create_access_token(subject=str(user.id))
