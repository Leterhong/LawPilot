"""数据访问基类（Repository 模式）。

提供通用 CRUD 与过滤查询，具体仓储继承后按需扩展。所有写操作在方法内
完成 ``commit``，调用方无需关心事务边界细节（单一写操作场景）。
"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

ModelType = TypeVar("ModelType", bound=DeclarativeBase)


class BaseRepository(Generic[ModelType]):
    """通用仓储。"""

    model: type[ModelType]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, **kwargs: Any) -> ModelType:
        """插入一条记录并返回带主键的实例。"""
        obj = self.model(**kwargs)  # type: ignore[call-arg]
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def get(self, obj_id: Any) -> ModelType | None:
        """按主键查询。"""
        stmt = select(self.model).where(self.model.id == obj_id)  # type: ignore[attr-defined]
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find(self, **filters: Any) -> ModelType | None:
        """按相等条件查询单条。"""
        stmt = select(self.model)
        for key, value in filters.items():
            stmt = stmt.where(getattr(self.model, key) == value)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self, *, skip: int = 0, limit: int = 50, order_by=None, **filters: Any
    ) -> list[ModelType]:
        """按相等条件分页查询。"""
        stmt = select(self.model)
        for key, value in filters.items():
            if value is not None:
                stmt = stmt.where(getattr(self.model, key) == value)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, **filters: Any) -> int:
        """统计满足条件的记录数。"""
        stmt = select(func.count()).select_from(self.model)
        for key, value in filters.items():
            if value is not None:
                stmt = stmt.where(getattr(self.model, key) == value)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def update(self, obj: ModelType, **kwargs: Any) -> ModelType:
        """就地更新非空字段并提交。"""
        for key, value in kwargs.items():
            if value is not None:
                setattr(obj, key, value)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def delete(self, obj: ModelType) -> None:
        """删除记录。"""
        await self.session.delete(obj)
        await self.session.commit()
