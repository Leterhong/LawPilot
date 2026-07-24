"""用户仓储。"""
from __future__ import annotations

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """用户数据访问。"""

    model = User

    async def get_by_email(self, email: str) -> User | None:
        return await self.find(email=email)
