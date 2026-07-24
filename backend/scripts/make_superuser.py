"""创建/确保一个超级管理员账号（幂等）。仅用于本地验证 AI 能力中心。

用法：
  PYTHONPATH=F:/falv/backend .venv_clean/Scripts/python.exe scripts/make_superuser.py
"""
import asyncio
from uuid import uuid4

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User


async def main() -> None:
    email = "admin@lawpilot.dev"
    password = "admin1234"
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(select(User).where(User.email == email))
        if existing:
            existing.is_superuser = True
            existing.is_active = True
            await db.commit()
            print(f"已存在，已设为超管：{email}")
            return
        u = User(
            id=uuid4(),
            email=email,
            hashed_password=hash_password(password),
            display_name="Admin",
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        db.add(u)
        await db.commit()
        print(f"已创建超管：{email} / {password}")


if __name__ == "__main__":
    asyncio.run(main())
