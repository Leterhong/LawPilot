"""法律检索路由（Phase 5：混合检索 + Rerank + 引用来源）。

对外契约向后兼容：``/legal/search`` 仍返回 references / knowledge 列表，
并新增 ``results``（融合排序结果）、``citations``（引用元数据）、
``used_hybrid`` / ``used_rerank`` 标记。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.enums import LegalSourceEnum
from app.schemas.legal import LegalSearchResult
from app.services.legal_service import LegalService

router = APIRouter(prefix="/legal", tags=["legal"])


@router.get("/search", response_model=LegalSearchResult)
async def search(
    db: AsyncSession = Depends(get_db),
    q: str = Query(..., min_length=1, description="检索关键词"),
    source: LegalSourceEnum | None = Query(None, description="限定法律渊源"),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    use_rerank: bool = Query(True, description="是否进行重排精排"),
) -> LegalSearchResult:
    """检索法律条文与知识库（混合检索）。"""
    from app.schemas.legal import LegalSearchQuery

    query = LegalSearchQuery(
        q=q, source=source, limit=limit, offset=offset, use_rerank=use_rerank
    )
    svc = LegalService(db)

    # 混合检索主结果
    results, citations, used_hybrid, used_rerank = await svc.hybrid_search(query)

    # 关键词检索填充原始列表（向后兼容契约）
    refs, refs_total, know, know_total = await svc.search(query)

    return LegalSearchResult(
        query=q,
        results=results,
        citations=citations,
        references=list(refs),
        references_total=refs_total,
        knowledge=list(know),
        knowledge_total=know_total,
        used_hybrid=used_hybrid,
        used_rerank=used_rerank,
    )
