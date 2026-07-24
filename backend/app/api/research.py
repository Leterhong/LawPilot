"""法律研究中心路由（Legal Research Center）。

挂载前缀 ``/api/research``：
- ``/search``   公开：关键词/语义/布尔高级检索；
- ``/document/{id}`` 公开：文档详情（全文 + 关联 + AI 解读）；
- ``/recommend`` 公开：相关推荐（按文档或查询）。
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.research import (
    ResearchDocDetail,
    ResearchRecommendResult,
    ResearchSearchResult,
)
from app.services.research_service import ResearchService

router = APIRouter(prefix="/api/research", tags=["research"])


@router.get("/search", response_model=ResearchSearchResult)
async def search(
    q: str = Query("", description="检索词（支持 合同 AND 租赁 / 合同 NOT 仲裁 等布尔式）"),
    doc_type: str | None = Query(None, description="文档类型：legal_document/judicial_interpretation/department_rule/local_regulation/guideline/policy"),
    category: str | None = Query(None, description="UI 分类：法律/行政法规/指导性案例/典型案例/司法解释/部门规章/地方性法规/办事指南/政策文件"),
    level: str | None = Query(None, description="法律层级过滤"),
    region: str | None = Query(None, description="地区过滤（地方规定/部门规则适用）"),
    issuing_authority: str | None = Query(None, description="发文机关过滤"),
    is_current: bool | None = Query(None, description="是否现行有效（true/false）"),
    publish_from: date | None = Query(None, description="发布日期下限（YYYY-MM-DD）"),
    publish_to: date | None = Query(None, description="发布日期上限（YYYY-MM-DD）"),
    effective_from: date | None = Query(None, description="实施日期下限（YYYY-MM-DD）"),
    effective_to: date | None = Query(None, description="实施日期上限（YYYY-MM-DD）"),
    expiry_from: date | None = Query(None, description="失效日期下限（YYYY-MM-DD）"),
    expiry_to: date | None = Query(None, description="失效日期上限（YYYY-MM-DD）"),
    search_mode: str = Query("auto", description="检索模式：auto(混合)/full_text(仅全文)/semantic(仅语义)"),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ResearchSearchResult:
    """法律研究检索：全文 / 语义 / 布尔高级检索 + 过滤 + 重排。"""
    return await ResearchService(db).search(
        q,
        doc_type=doc_type,
        category=category,
        level=level,
        region=region,
        issuing_authority=issuing_authority,
        is_current=is_current,
        publish_from=publish_from,
        publish_to=publish_to,
        effective_from=effective_from,
        effective_to=effective_to,
        expiry_from=expiry_from,
        expiry_to=expiry_to,
        search_mode=search_mode,
        limit=limit,
        offset=offset,
    )


@router.get("/document/{doc_id}", response_model=ResearchDocDetail)
async def detail(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ResearchDocDetail:
    """文档详情：全文 / 时效 / 关联文档 / AI 通俗解释与摘要。"""
    result = await ResearchService(db).detail(doc_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    return result


@router.get("/recommend", response_model=ResearchRecommendResult)
async def recommend(
    doc_id: UUID | None = Query(None, description="基于该文档做相关推荐"),
    q: str | None = Query(None, description="基于查询文本做相关推荐"),
    limit: int = Query(10, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
) -> ResearchRecommendResult:
    """相关推荐：传入 doc_id 或 q 其一即可。"""
    return await ResearchService(db).recommend(doc_id=doc_id, q=q, limit=limit)
