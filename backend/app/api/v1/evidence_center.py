"""智能证据中心（Evidence Intelligence Center）API 路由。

Step2 端点（文件上传系统）：
- POST /api/v1/evidence-center/upload  批量上传：校验类型/大小 → 落盘 → 建记录（状态 uploaded）
- GET  /api/v1/evidence-center         列表（当前用户，支持类型/状态/案件筛选 + 名称搜索 + 分页）
- GET  /api/v1/evidence-center/{id}    详情（含 OCR 文本 / 结构化元数据，未分析时为 None）
- GET  /api/v1/evidence-center/{id}/file  取回原件（预览 / 下载）
- DELETE /api/v1/evidence-center/{id} 删除（仅本人或超管，连带删除本地文件）

Step3 端点（OCR & AI 分析）：
- POST /api/v1/evidence-center/analyze          批量分析（body: evidence_ids）
- POST /api/v1/evidence-center/{id}/analyze     单条分析（OCR/提取 → AI 理解 → 落库）
- GET  /api/v1/evidence-center/{id}/analysis    读取分析结果

Step4 端点（证据链 / Evidence Graph）：
- POST   /api/v1/evidence-center/relations            手动建立证据关系（幂等）
- GET    /api/v1/evidence-center/relations            查询关系（按案件 / 按单证据）
- DELETE /api/v1/evidence-center/relations/{id}       删除关系
- POST   /api/v1/evidence-center/chain/build          构建证据链（AI 推断关系 + 重建时间线）
- GET    /api/v1/evidence-center/chain/timeline       案件时间线
- GET    /api/v1/evidence-center/chain/graph          Evidence Graph（节点+边+时间线）

Step5 端点（报告生成，声明在 /{evidence_id} 之前以免被 UUID 通配拦截）：
- POST   /api/v1/evidence-center/reports                        生成报告（directory/score/missing/strategy/full）
- GET    /api/v1/evidence-center/reports?case_id=              报告列表
- GET    /api/v1/evidence-center/reports/{report_id}           报告详情
- GET    /api/v1/evidence-center/reports/{report_id}/download  导出（fmt=word|pdf|markdown）
"""
from __future__ import annotations

import os
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.enums import EvidenceFileStatusEnum
from app.models.evidence_center import EvidenceAnalysis, EvidenceFile, EvidenceReport
from app.models.user import User
from app.schemas.common import Page
from app.schemas.evidence_center import (
    EvidenceAnalysisOut,
    EvidenceAnalyzeItem,
    EvidenceAnalyzeRequest,
    EvidenceAnalyzeResponse,
    EvidenceChainBuildRequest,
    EvidenceChainBuildResponse,
    EvidenceDetailOut,
    EvidenceFileOut,
    EvidenceGraphNode,
    EvidenceGraphOut,
    EvidenceRelationCreate,
    EvidenceRelationOut,
    EvidenceReportGenerateRequest,
    EvidenceReportOut,
    EvidenceTimelineNodeOut,
    EvidenceUploadItem,
    EvidenceUploadResponse,
)
from app.services.ai.manager import AIManager
from app.services.case_service import CaseService
from app.services.evidence_center_analyzer import analyze_evidence
from app.services.evidence_center_chain import EvidenceChainService
from app.services.evidence_center_report import (
    EvidenceReportService,
    generate_evidence_report,
    render_docx,
    render_pdf,
)
from app.services.evidence_center_service import (
    EvidenceCenterService,
    guess_category,
    is_supported,
)
from app.utils.storage import StorageError, delete_file, resolve_path, save_upload

router = APIRouter(prefix="/evidence-center", tags=["evidence-center"])


# ---------------------------------------------------------------------------
# 上传（批量：落盘 + 建记录）
# ---------------------------------------------------------------------------
@router.post(
    "/upload",
    response_model=EvidenceUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_evidence(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
    files: list[UploadFile] = File(..., description="一个或多个证据文件（支持批量）"),
    case_id: UUID | None = Query(None, description="可选：归属案件（须是当前用户案件）"),
    source: str | None = Query(None, description="证据来源说明（如：微信截图 / 银行流水）"),
    tags: list[str] | None = Query(None, description="用户标签，如 ['借款','转账']"),
) -> EvidenceUploadResponse:
    """批量上传证据文件。

    流程：逐个校验扩展名 / 大小 → 落盘 ``upload_dir/evidence/<user_id>/``
    → 写入 ``evidence_files``（status: uploaded，类型依扩展名粗分类）。
    单个文件失败不影响其余文件；返回每条结果。
    """
    if not files:
        raise HTTPException(status_code=400, detail="未接收到文件")

    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    # 案件归属校验（可选）
    resolved_case_id: UUID | None = None
    if case_id is not None:
        owned = await CaseService(db).get_owned(case_id, current)
        if owned is None:
            raise HTTPException(
                status_code=404, detail="案件不存在或无权访问"
            )
        resolved_case_id = case_id

    items: list[EvidenceUploadItem] = []
    orm_list: list[EvidenceFile] = []
    svc = EvidenceCenterService(db)
    for f in files:
        filename = f.filename or "unnamed"
        ext = os.path.splitext(filename)[1].lower()
        try:
            if not is_supported(ext):
                items.append(
                    EvidenceUploadItem(
                        file=_empty_out(filename),
                        stored=False,
                        note=f"不支持的文件类型：{ext or '（无扩展名）'}",
                    )
                )
                continue
            content = await f.read()
            if len(content) > max_bytes:
                items.append(
                    EvidenceUploadItem(
                        file=_empty_out(filename),
                        stored=False,
                        note=f"文件超过大小限制（{settings.max_upload_size_mb}MB）",
                    )
                )
                continue

            # 复位读取指针（save_upload 内部会再次 read），再落盘。
            # 注意：UploadFile.seek 是 async 方法，必须 await，否则指针不复位 → 写入空文件。
            await f.seek(0)
            stored_path, file_url, size = await save_upload(
                f, module="evidence", owner_id=current.id
            )
            ef = await svc.create(
                user_id=current.id,
                name=filename,
                category=guess_category(ext),
                status=EvidenceFileStatusEnum.UPLOADED,
                file_url=file_url,
                file_type=ext.lstrip("."),
                mime_type=f.content_type,
                size_bytes=size,
                case_id=resolved_case_id,
                source=source,
                tags=tags,
            )
            await db.flush()
            orm_list.append(ef)
            items.append(
                EvidenceUploadItem(
                    file=EvidenceFileOut.model_validate(ef),
                    stored=True,
                    note=None,
                )
            )
        except StorageError as exc:
            items.append(
                EvidenceUploadItem(file=_empty_out(filename), stored=False, note=str(exc))
            )
        except Exception as exc:  # 极端降级：记录失败原因，不阻断批量
            items.append(
                EvidenceUploadItem(
                    file=_empty_out(filename), stored=False, note=f"上传失败：{exc}"
                )
            )

    await db.commit()
    # 刷新以载入服务端生成的 id / 时间戳（server default）
    for ef in orm_list:
        await db.refresh(ef)
    # 用刷新后的 ORM 重建成功项的响应，确保时间字段非空
    succeeded = [it for it in items if it.stored]
    for it, ef in zip(succeeded, orm_list):
        it.file = EvidenceFileOut.model_validate(ef)
    return EvidenceUploadResponse(
        items=items,
        total=len(items),
        succeeded=len(succeeded),
    )


def _empty_out(name: str) -> EvidenceFileOut:
    """构造一个仅含名称的占位响应（上传失败时返回，便于前端展示）。"""
    return EvidenceFileOut(
        id=UUID(int=0),
        name=name,
        category="other",  # type: ignore[arg-type]
        status=EvidenceFileStatusEnum.UPLOADED,
    )


# ---------------------------------------------------------------------------
# 列表
# ---------------------------------------------------------------------------
@router.get("", response_model=Page[EvidenceFileOut])
async def list_evidence(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
    category: str | None = Query(None, description="按证据类型筛选"),
    status_filter: str | None = Query(None, alias="status", description="按状态筛选"),
    case_id: UUID | None = Query(None, description="按案件筛选"),
    q: str | None = Query(None, description="按文件名模糊搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[EvidenceFileOut]:
    """列出当前用户的证据（支持类型/状态/案件筛选 + 名称搜索 + 分页）。"""
    svc = EvidenceCenterService(db)
    rows, total = await svc.list_for_user(
        current.id,
        category=category,
        status=status_filter,
        case_id=case_id,
        q=q,
        page=page,
        page_size=page_size,
    )
    return Page[EvidenceFileOut].create(
        items=[EvidenceFileOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Step3：OCR & AI 分析
# ---------------------------------------------------------------------------
@router.post("/analyze", response_model=EvidenceAnalyzeResponse)
async def analyze_evidence_batch(
    payload: EvidenceAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> EvidenceAnalyzeResponse:
    """批量分析证据：逐条执行 OCR/文本提取 → AI 理解 → 写入分析结果。

    单条失败不阻断其余；AI 未配置时启发式兜底（``ai_available=false``）。
    """
    if not payload.evidence_ids:
        raise HTTPException(status_code=400, detail="evidence_ids 不能为空")
    if len(payload.evidence_ids) > 20:
        raise HTTPException(status_code=400, detail="单次最多分析 20 条证据")

    svc = EvidenceCenterService(db)
    mgr = AIManager(db)
    items: list[EvidenceAnalyzeItem] = []
    for eid in payload.evidence_ids:
        ef = await svc.get(eid)
        if ef is None or (ef.user_id != current.id and not current.is_superuser):
            items.append(
                EvidenceAnalyzeItem(evidence_id=eid, ok=False, note="证据不存在或无权访问")
            )
            continue
        try:
            result = await analyze_evidence(
                ef, db, mgr, user_id=current.id, force_reparse=payload.force_reparse
            )
            items.append(
                EvidenceAnalyzeItem(
                    evidence_id=eid,
                    ok=True,
                    ai_available=result["ai_available"],
                    ocr_kind=result["ocr_kind"],
                    text_len=result["text_len"],
                    proof_strength=result["proof_strength"],
                    status=result["status"],
                    latency_ms=result["latency_ms"],
                    note=None if result["ai_available"] else "AI 未配置，已用启发式兜底",
                )
            )
        except Exception as exc:  # 单条失败不阻断批量
            items.append(
                EvidenceAnalyzeItem(evidence_id=eid, ok=False, note=f"分析失败：{exc}")
            )
    await db.commit()
    succeeded = sum(1 for it in items if it.ok)
    return EvidenceAnalyzeResponse(items=items, total=len(items), succeeded=succeeded)


@router.post("/{evidence_id}/analyze", response_model=EvidenceAnalyzeItem)
async def analyze_evidence_single(
    evidence_id: UUID,
    force_reparse: bool = Query(False, description="是否强制重新 OCR/提取文本"),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> EvidenceAnalyzeItem:
    """单条证据分析（可重入：重复调用覆盖旧结果）。"""
    ef = await EvidenceCenterService(db).get(evidence_id)
    if ef is None:
        raise HTTPException(status_code=404, detail="证据不存在")
    if ef.user_id != current.id and not current.is_superuser:
        raise HTTPException(status_code=404, detail="证据不存在")
    mgr = AIManager(db)
    try:
        result = await analyze_evidence(
            ef, db, mgr, user_id=current.id, force_reparse=force_reparse
        )
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"分析失败：{exc}")
    await db.commit()
    return EvidenceAnalyzeItem(
        evidence_id=evidence_id,
        ok=True,
        ai_available=result["ai_available"],
        ocr_kind=result["ocr_kind"],
        text_len=result["text_len"],
        proof_strength=result["proof_strength"],
        status=result["status"],
        latency_ms=result["latency_ms"],
        note=None if result["ai_available"] else "AI 未配置，已用启发式兜底",
    )


@router.get("/{evidence_id}/analysis", response_model=EvidenceAnalysisOut)
async def get_evidence_analysis(
    evidence_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> EvidenceAnalysisOut:
    """读取证据的 AI 分析结果（未分析返回 404）。"""
    ef = await EvidenceCenterService(db).get(evidence_id)
    if ef is None:
        raise HTTPException(status_code=404, detail="证据不存在")
    if ef.user_id != current.id and not current.is_superuser:
        raise HTTPException(status_code=404, detail="证据不存在")
    analysis = (
        await db.scalars(
            select(EvidenceAnalysis).where(EvidenceAnalysis.evidence_id == evidence_id)
        )
    ).first()
    if analysis is None:
        raise HTTPException(status_code=404, detail="该证据尚未分析")
    return EvidenceAnalysisOut.model_validate(analysis)


# ---------------------------------------------------------------------------
# Step4：证据链（关系 / 时间线 / 图谱）
# 注意：固定路径（/relations、/chain/*）必须声明在 /{evidence_id} 之前。
# ---------------------------------------------------------------------------
@router.post(
    "/relations",
    response_model=EvidenceRelationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_relation(
    payload: EvidenceRelationCreate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> EvidenceRelationOut:
    """手动建立证据关系（幂等：同向同类型重复创建返回已有关系）。"""
    svc = EvidenceChainService(db)
    rel, _is_new, err = await svc.create_relation(
        current,
        source_id=payload.source_id,
        target_id=payload.target_id,
        relation_type=payload.relation_type,
        note=payload.note,
    )
    if err is not None or rel is None:
        raise HTTPException(status_code=400, detail=err or "建立关系失败")
    await db.commit()
    await db.refresh(rel)
    return EvidenceRelationOut.model_validate(rel)


@router.get("/relations", response_model=list[EvidenceRelationOut])
async def list_relations(
    case_id: UUID | None = Query(None, description="按案件查（案件下证据的全部关系）"),
    evidence_id: UUID | None = Query(None, description="按单证据查（出边+入边）"),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[EvidenceRelationOut]:
    """查询证据关系。"""
    rels = await EvidenceChainService(db).list_relations(
        current, case_id=case_id, evidence_id=evidence_id
    )
    return [EvidenceRelationOut.model_validate(r) for r in rels]


@router.delete("/relations/{relation_id}")
async def delete_relation(
    relation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    """删除证据关系（关系两端任一证据归当前用户即可）。"""
    ok = await EvidenceChainService(db).delete_relation(relation_id, current)
    if not ok:
        raise HTTPException(status_code=404, detail="关系不存在或无权访问")
    await db.commit()
    return {"deleted": True}


@router.post("/chain/build", response_model=EvidenceChainBuildResponse)
async def build_chain(
    payload: EvidenceChainBuildRequest,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> EvidenceChainBuildResponse:
    """构建证据链：AI 推断证据关系 +（指定案件时）自动重建时间线。

    - ``infer_relations=true``：LLM 推断 support/contradict/sequence 等关系，
      无 AI key 时启发式兜底（时间先后 → sequence；金额重合 → support）；
    - ``build_timeline=true`` 且给了 ``case_id``：按证据时间重建案件时间线。
    """
    svc = EvidenceChainService(db)

    # 案件归属校验（可选）
    if payload.case_id is not None:
        owned = await CaseService(db).get_owned(payload.case_id, current)
        if owned is None:
            raise HTTPException(status_code=404, detail="案件不存在或无权访问")

    evidences = await svc.pick_evidences(
        current, case_id=payload.case_id, evidence_ids=payload.evidence_ids
    )
    if not evidences:
        raise HTTPException(status_code=400, detail="没有可用于构建证据链的证据")

    created, ai_available, note = 0, False, None
    if payload.infer_relations:
        created, ai_available, note = await EvidenceChainService(db).infer_relations(
            current, AIManager(db), evidences
        )

    timeline_count = 0
    if payload.build_timeline and payload.case_id is not None:
        nodes = await svc.build_timeline(payload.case_id, evidences)
        timeline_count = len(nodes)

    await db.commit()
    return EvidenceChainBuildResponse(
        evidence_count=len(evidences),
        relations_created=created,
        timeline_nodes=timeline_count,
        ai_available=ai_available,
        note=note,
    )


@router.get("/chain/timeline", response_model=list[EvidenceTimelineNodeOut])
async def get_timeline(
    case_id: UUID = Query(..., description="案件 id"),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[EvidenceTimelineNodeOut]:
    """读取案件证据时间线（按 order_index 升序）。"""
    owned = await CaseService(db).get_owned(case_id, current)
    if owned is None:
        raise HTTPException(status_code=404, detail="案件不存在或无权访问")
    nodes = await EvidenceChainService(db).list_timeline(case_id)
    return [EvidenceTimelineNodeOut.model_validate(n) for n in nodes]


@router.get("/chain/graph", response_model=EvidenceGraphOut)
async def get_graph(
    case_id: UUID | None = Query(None, description="按案件组图"),
    evidence_ids: list[UUID] | None = Query(None, description="或显式指定证据集合"),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> EvidenceGraphOut:
    """Evidence Graph：节点（证据+分析摘要/证明力）+ 边（关系）+ 时间线。"""
    if case_id is not None:
        owned = await CaseService(db).get_owned(case_id, current)
        if owned is None:
            raise HTTPException(status_code=404, detail="案件不存在或无权访问")
    graph = await EvidenceChainService(db).build_graph(
        current, case_id=case_id, evidence_ids=evidence_ids
    )
    return EvidenceGraphOut(
        nodes=[EvidenceGraphNode(**n) for n in graph["nodes"]],
        edges=[EvidenceRelationOut.model_validate(e) for e in graph["edges"]],
        timeline=[
            EvidenceTimelineNodeOut.model_validate(t) for t in graph["timeline"]
        ],
    )


# ---------------------------------------------------------------------------
# Step5：报告生成
# ---------------------------------------------------------------------------
@router.post(
    "/reports",
    response_model=EvidenceReportOut,
    status_code=status.HTTP_201_CREATED,
)
async def generate_report(
    payload: EvidenceReportGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> EvidenceReportOut:
    """生成证据报告（目录 / 评分 / 缺失分析 / 策略 / 综合）。

    可指定 ``case_id``（案件下全部证据）或显式 ``evidence_ids``。同一案件同类型报告
    只保留最新一份（``regenerate=true`` 或首次生成会重新计算）。
    """
    if payload.case_id is None and not payload.evidence_ids:
        raise HTTPException(status_code=400, detail="必须提供 case_id 或 evidence_ids")
    mgr = AIManager(db)
    try:
        report, _generated = await generate_evidence_report(
            current=current,
            db=db,
            mgr=mgr,
            case_id=payload.case_id,
            evidence_ids=payload.evidence_ids,
            report_type=payload.report_type.value,
            regenerate=payload.regenerate,
            user_id=current.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    await db.refresh(report)
    return EvidenceReportOut.model_validate(report)


@router.get("/reports", response_model=list[EvidenceReportOut])
async def list_reports(
    case_id: UUID | None = Query(None, description="按案件筛选；不传则返回当前用户的全部报告"),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[EvidenceReportOut]:
    """报告列表（按案件或按当前用户）。"""
    svc = EvidenceReportService(db)
    if case_id is not None:
        owned = await CaseService(db).get_owned(case_id, current)
        if owned is None:
            raise HTTPException(status_code=404, detail="案件不存在或无权访问")
        reports = await svc.list_reports(case_id)
    else:
        reports = await svc.list_for_user(current)
    return [EvidenceReportOut.model_validate(r) for r in reports]


@router.get("/reports/{report_id}", response_model=EvidenceReportOut)
async def get_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> EvidenceReportOut:
    """报告详情。"""
    report = await EvidenceReportService(db).get_by_id(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="报告不存在")
    ok = await _report_access(report, current, db)
    if not ok:
        raise HTTPException(status_code=404, detail="报告不存在")
    return EvidenceReportOut.model_validate(report)


@router.get("/reports/{report_id}/download", response_model=None)
async def download_report(
    report_id: UUID,
    fmt: str = Query("word", description="导出格式：word / pdf / markdown"),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> FileResponse | dict:
    """导出报告为 Word / PDF / Markdown。

    - word：零依赖 OOXML（始终可用，中文正常）；
    - pdf：reportlab + 中文字体（无字体/无库时返回 501，建议改用 word/markdown）；
    - markdown：原始 Markdown 文本。
    """
    report = await EvidenceReportService(db).get_by_id(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="报告不存在")
    if not await _report_access(report, current, db):
        raise HTTPException(status_code=404, detail="报告不存在")

    content = report.content or {}
    blocks = content.get("blocks") or []
    title = report.title or "证据报告"
    markdown = content.get("markdown") or ""

    if fmt == "markdown":
        return FileResponse(
            _to_temp(markdown.encode("utf-8"), f"{title}.md"),
            media_type="text/markdown; charset=utf-8",
            filename=f"{title}.md",
        )
    if fmt == "word":
        data = render_docx(blocks, title)
        return FileResponse(
            _to_temp(data, f"{title}.docx"),
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            filename=f"{title}.docx",
        )
    if fmt == "pdf":
        data = render_pdf(blocks, title)
        if data is None:
            raise HTTPException(
                status_code=501,
                detail="当前环境不支持 PDF 导出（缺少 reportlab 或中文字体），请改用 word 或 markdown。",
            )
        return FileResponse(
            _to_temp(data, f"{title}.pdf"),
            media_type="application/pdf",
            filename=f"{title}.pdf",
        )
    raise HTTPException(status_code=400, detail="不支持的导出格式")


async def _report_access(report: EvidenceReport, current: User, db: AsyncSession) -> bool:
    """报告访问权限：案件归属 或 创建人本人（超管放行）。"""
    if current.is_superuser:
        return True
    if report.case_id is not None:
        owned = await CaseService(db).get_owned(report.case_id, current)
        return owned is not None
    return report.created_by == current.id


def _to_temp(data: bytes, name: str) -> str:
    """把字节写入临时文件并返回路径（导出下载用）。"""
    import tempfile

    fd, path = tempfile.mkstemp(suffix="_" + name)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path


# ---------------------------------------------------------------------------
# 详情
# ---------------------------------------------------------------------------
@router.get("/{evidence_id}", response_model=EvidenceDetailOut)
async def get_evidence(
    evidence_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> EvidenceDetailOut:
    """证据详情（含 OCR 文本 / 结构化元数据 / 分析结果；未分析时为 None）。"""
    ef = await EvidenceCenterService(db).get(evidence_id)
    if ef is None:
        raise HTTPException(status_code=404, detail="证据不存在")
    if ef.user_id != current.id and not current.is_superuser:
        raise HTTPException(status_code=404, detail="证据不存在")
    out = EvidenceDetailOut.model_validate(ef)
    analysis = (
        await db.scalars(
            select(EvidenceAnalysis).where(EvidenceAnalysis.evidence_id == evidence_id)
        )
    ).first()
    if analysis is not None:
        out.analysis = EvidenceAnalysisOut.model_validate(analysis)
    return out


# ---------------------------------------------------------------------------
# 取回原件（预览 / 下载）
# ---------------------------------------------------------------------------
@router.get("/{evidence_id}/file")
async def get_evidence_file(
    evidence_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> FileResponse:
    """取回证据原件（用于前端预览 / 下载）。"""
    ef = await EvidenceCenterService(db).get(evidence_id)
    if ef is None:
        raise HTTPException(status_code=404, detail="证据不存在")
    if ef.user_id != current.id and not current.is_superuser:
        raise HTTPException(status_code=404, detail="证据不存在")
    path = resolve_path(ef.file_url)
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在或未落盘")
    return FileResponse(path, filename=ef.name)


# ---------------------------------------------------------------------------
# 删除
# ---------------------------------------------------------------------------
@router.delete("/{evidence_id}", response_model=EvidenceFileOut)
async def delete_evidence(
    evidence_id: UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> EvidenceFileOut:
    """删除证据（仅本人或超管），连带删除本地文件。"""
    svc = EvidenceCenterService(db)
    ef = await svc.get(evidence_id)
    if ef is None:
        raise HTTPException(status_code=404, detail="证据不存在")
    if ef.user_id != current.id and not current.is_superuser:
        raise HTTPException(status_code=404, detail="证据不存在")
    out = EvidenceFileOut.model_validate(ef)
    # 先删本地文件，再删记录（避免异常导致孤儿文件）
    delete_file(resolve_path(ef.file_url))
    await svc.delete(ef)
    await db.commit()
    return out
