"""Playground 历史 / 收藏 / 发布 数据访问层。

提供：
- 测试历史（playground_sessions）分页查询
- Prompt 收藏（prompt_library）CRUD
- 一键发布审计（playground_publishes）查询
- 模型选择器列表（复用 ai_models，带 provider 显示名）
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_center import AIModel, Provider
from app.models.playground import (
    PlaygroundPublish,
    PlaygroundSession,
    PromptLibrary,
)
from app.schemas.playground import (
    PlaygroundModelOut,
    PlaygroundSessionOut,
    PlaygroundPublishOut,
    PromptLibraryCreate,
    PromptLibraryOut,
    PromptLibraryUpdate,
)


async def list_models_for_picker(db: AsyncSession) -> list[PlaygroundModelOut]:
    """返回全部模型（含 provider 显示名），供前端模型选择器使用。"""
    models = (await db.scalars(select(AIModel))).all()
    provider_names: dict[UUID, str] = {}
    if models:
        pids = {m.provider_id for m in models if m.provider_id is not None}
        if pids:
            provs = (await db.scalars(select(Provider).where(Provider.id.in_(pids)))).all()
            provider_names = {p.id: p.name for p in provs}
    out = []
    for m in models:
        out.append(
            PlaygroundModelOut(
                id=m.id,
                name=m.name,
                provider_id=m.provider_id,
                provider_name=provider_names.get(m.provider_id) if m.provider_id else None,
                capabilities=m.capabilities or {},
                is_enabled=m.is_enabled,
            )
        )
    return out


async def list_sessions(
    db: AsyncSession,
    user_id: UUID | None,
    *,
    type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[PlaygroundSessionOut]:
    stmt = select(PlaygroundSession)
    if type:
        stmt = stmt.where(PlaygroundSession.type == type)
    # 普通用户只看自己的；超管看全部（调用方已过滤 user_id）
    if user_id is not None:
        stmt = stmt.where(PlaygroundSession.user_id == user_id)
    stmt = stmt.order_by(desc(PlaygroundSession.created_at)).limit(limit).offset(offset)
    rows = (await db.scalars(stmt)).all()
    return [PlaygroundSessionOut.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# Prompt 收藏
# ---------------------------------------------------------------------------
async def list_prompt_library(
    db: AsyncSession,
    user_id: UUID | None,
    *,
    category: str | None = None,
    include_public: bool = True,
) -> list[PromptLibraryOut]:
    stmt = select(PromptLibrary)
    if category:
        stmt = stmt.where(PromptLibrary.category == category)
    if user_id is not None and include_public:
        stmt = stmt.where(
            (PromptLibrary.user_id == user_id) | (PromptLibrary.is_public == True)  # noqa: E712
        )
    elif user_id is not None:
        stmt = stmt.where(PromptLibrary.user_id == user_id)
    stmt = stmt.order_by(desc(PromptLibrary.updated_at))
    rows = (await db.scalars(stmt)).all()
    return [PromptLibraryOut.model_validate(r) for r in rows]


async def create_prompt(
    db: AsyncSession, user_id: UUID | None, data: PromptLibraryCreate
) -> PromptLibraryOut:
    obj = PromptLibrary(user_id=user_id, **data.model_dump())
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return PromptLibraryOut.model_validate(obj)


async def update_prompt(
    db: AsyncSession, pid: UUID, user_id: UUID | None, data: PromptLibraryUpdate
) -> PromptLibraryOut | None:
    obj = (await db.scalars(select(PromptLibrary).where(PromptLibrary.id == pid))).first()
    if obj is None:
        return None
    # 权限：作者本人或被收藏者本人；公开模板仅作者可改
    if user_id is not None and obj.user_id is not None and obj.user_id != user_id:
        return None
    for k, v in data.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(obj, k, v)
    await db.flush()
    await db.refresh(obj)
    return PromptLibraryOut.model_validate(obj)


async def delete_prompt(db: AsyncSession, pid: UUID, user_id: UUID | None) -> bool:
    obj = (await db.scalars(select(PromptLibrary).where(PromptLibrary.id == pid))).first()
    if obj is None:
        return False
    if user_id is not None and obj.user_id is not None and obj.user_id != user_id:
        return False
    await db.delete(obj)
    await db.flush()
    return True


async def list_publishes(
    db: AsyncSession, user_id: UUID | None, *, limit: int = 50
) -> list[PlaygroundPublishOut]:
    stmt = select(PlaygroundPublish).order_by(desc(PlaygroundPublish.created_at)).limit(limit)
    if user_id is not None:
        stmt = stmt.where(PlaygroundPublish.user_id == user_id)
    rows = (await db.scalars(stmt)).all()
    return [PlaygroundPublishOut.model_validate(r) for r in rows]
