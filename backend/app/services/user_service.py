"""用户服务：资料更新等。"""
from __future__ import annotations

from app.models.user import User
from app.repositories.user_repo import UserRepository


class UserService:
    def __init__(self, session) -> None:
        self.repo = UserRepository(session)

    async def update_profile(
        self, user: User, display_name: str | None, avatar_url: str | None
    ) -> User:
        return await self.repo.update(
            user, display_name=display_name, avatar_url=avatar_url
        )
