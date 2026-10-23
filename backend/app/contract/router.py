"""合同智能中心（Contract Intelligence Center）API 路由。

Step2 端点（OCR 与文件解析落地）：
- POST /api/contracts/upload       上传合同：落盘 + 文本提取/OCR + AI 自动分类 + 落库
- GET  /api/contracts              列表（当前用户，支持类型/状态筛选 + 分页）
- GET  /api/contracts/{id}         详情（含全文 / OCR 文本 / risks / clauses）
- DELETE /api/contracts/{id}       删除（仅本人或超管）

Step3 端点（AI 分析落地）：
- POST /api/contracts/{id}/analyze 触发 AI 分析（风险/评分/摘要/条款解释），可重入
- GET  /api/contracts/{id}/risks   风险清单（Risk Dashboard 数据源）
- GET  /api/contracts/{id}/clauses 逐条款（Clause Analyzer 数据源）

Step5 端点（报告生成落地）：
- GET  /api/contracts/{id}/report    生成/取回审查报告（report_type=review/summary/full/checklist，支持 regenerate）
- GET  /api/contracts/{id}/reports   已生成报告列表

Step6 端点（提醒中心落地）：
- GET    /api/contracts/{id}/tasks        列出合同下的提醒 / 待办
- POST   /api/contracts/{id}/tasks        创建提醒 / 待办
- PATCH  /api/contracts/{id}/tasks/{task_id}  更新（标题/日期/完成状态等）
- DELETE /api/contracts/{id}/tasks/{task_id}  删除
- GET    /api/contracts/tasks/upcoming    提醒中心聚合（当前用户即将到期/逾期提醒）

Step7（模板中心）端点将在后续步骤追加。
"""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contract.analyzer import analyze_contract
from app.contract.parser import is_supported, parse_contract_file
from app.contract.report import generate_report
from app.contract.service import ContractService
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.contract import CONTRACT_ALLOWED_EXTENSIONS, Contract
from app.models.user import User
from app.schemas.common import Page
from app.schemas.contract import (
    ContractClauseOut,
    ContractDetailOut,
    ContractOut,
    ContractReportOut,
    ContractRiskOut,
    ContractTaskCreate,
    ContractTaskOut,
    ContractTaskUpdate,
    ContractUploadResponse,
)
from app.services.ai.manager import AIManager

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


def _mgr(db: AsyncSession) -> AIManager:
    return AIManager(db=db)


def _build_detail(contract: Contract, risks: list, clauses: list) -> ContractDetailOut:
    """组装详情响应（含子表 risks / clauses）。"""
    data = ContractDetailOut.model_validate(contract)
    data.risks = [ContractRiskOut.model_validate(r) for r in risks]
    data.clauses = [ContractClauseOut.model_validate(c) for c in clauses]
    return data


# ---------------------------------------------------------------------------
# 上传（落盘 + 提取/OCR + 分类 + 落库）
# ---------------------------------------------------------------------------
@router.post(
    "/upload",
    response_model=ContractUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_contract(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
    file: UploadFile = File(...),
    title: str | None = Form(None),
) -> ContractUploadResponse:
    """上传合同文件。

    流程：校验类型/大小 → 落盘 upload_dir/contracts → 文本提取或 OCR → AI 自动分类
    → 写入 contracts 表（status: parsing → uploaded）。AI 不可用时全部优雅降级。
    """
    filename = file.filename or "unnamed"
    ext = os.path.splitext(filename)[1].lower()
    if not is_supported(ext):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型：{ext or '（无扩展名）'}。允许：{', '.join(CONTRACT_ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"文件超过大小限制（{settings.max_upload_size_mb}MB）",
        )

    # 落盘（独立子目录，避免与证据模块混淆）
    contract_dir = os.path.join(settings.upload_dir, "contracts")
    os.makedirs(contract_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(contract_dir, stored_name)
    with open(stored_path, "wb") as f:
        f.write(content)

    # 先建 parsing 记录，便于前端展示进度
    svc = ContractService(db)
    contract = await svc.create(
        user_id=current.id,
        title=title or filename,
        status="parsing",
        file_path=stored_path,
        file_type=ext.lstrip("."),
        file_size=len(content),
    )
    await db.commit()

    # 解析（提取 / OCR / 分类），任何异常均降级，不阻断落库
    full_text: str | None = None
    ocr_text: str | None = None
    ctype: str = "other"
    ocr_used = ext.lower() in (".png", ".jpg", ".jpeg")
    try:
        full_text, ocr_text, ctype = await parse_contract_file(
            stored_path, ext, title or filename, _mgr(db)
        )
        await svc.update_after_parse(
            contract,
            contract_type=ctype,
            full_text=full_text,
            ocr_text=ocr_text,
            status="uploaded",
        )
    except Exception:
        # 极端情况下仍保留记录，标记为 error 便于排查
        contract.status = "error"
        await db.flush()
    await db.commit()

    parsed = bool(full_text)
    # 刷新以载入服务端生成的 created_at / updated_at，避免异步 ORM 惰性加载
    await db.refresh(contract)
    return ContractUploadResponse(
        contract=ContractOut.model_validate(contract),
        parsed=parsed,
        text_length=len(full_text or ""),
        ocr_used=ocr_used and bool(ocr_text),
    )


# ---------------------------------------------------------------------------
# 列表
# ---------------------------------------------------------------------------
@router.get("", response_model=Page[ContractOut])
async def list_contracts(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
    contract_type: str | None = Query(None, description="按合同类型筛选"),
    status_filter: str | None = Query(None, alias="status", description="按状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[ContractOut]:
    """列出当前用户的合同（支持类型/状态筛选与分页）。"""
    svc = ContractService(db)
    rows, total = await svc.list_for_user(
        current.id,
        contract_type=contract_type,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return Page[ContractOut].create(
        items=[ContractOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# 详情
# ---------------------------------------------------------------------------
@router.get("/{contract_id}", response_model=ContractDetailOut)
async def get_contract(
    contract_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> ContractDetailOut:
    """合同详情（含全文 / OCR 文本 / AI 分析明细 / risks / clauses）。"""
    svc = ContractService(db)
    contract = await svc.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="合同不存在")
    if contract.user_id != current.id and not current.is_superuser:
        raise HTTPException(status_code=404, detail="合同不存在")
    risks = await svc.get_risks(contract_id)
    clauses = await svc.get_clauses(contract_id)
    return _build_detail(contract, risks, clauses)


# ---------------------------------------------------------------------------
# AI 分析（Step3）
# ---------------------------------------------------------------------------
@router.post("/{contract_id}/analyze", response_model=ContractDetailOut)
async def analyze_contract_endpoint(
    contract_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> ContractDetailOut:
    """触发 AI 分析（风险识别 / 评分 / 摘要 / 逐条款解释）。

    可重入：重复调用会清空旧 risks / clauses 后重新写入。AI 不可用时优雅降级
    （结构化解 + 空结果），合同仍标记为 analyzed。
    """
    svc = ContractService(db)
    contract = await svc.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="合同不存在")
    if contract.user_id != current.id and not current.is_superuser:
        raise HTTPException(status_code=404, detail="合同不存在")

    result = await analyze_contract(contract, db, _mgr(db), user_id=current.id)
    await db.commit()
    await db.refresh(contract)

    risks = await svc.get_risks(contract_id)
    clauses = await svc.get_clauses(contract_id)
    detail = _build_detail(contract, risks, clauses)
    # 把分析元信息附到响应里（便于前端提示 AI 是否可用）
    detail.analysis_meta = {
        **(detail.analysis_meta or {}),
        "ai_available": result["ai_available"],
        "risks_count": result["risks_count"],
        "clauses_count": result["clauses_count"],
        "latency_ms": result["latency_ms"],
        "error": result["error"],
    }
    return detail


@router.get("/{contract_id}/risks", response_model=list[ContractRiskOut])
async def list_risks(
    contract_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[ContractRiskOut]:
    """合同风险清单（Risk Dashboard 数据源）。"""
    svc = ContractService(db)
    contract = await svc.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="合同不存在")
    if contract.user_id != current.id and not current.is_superuser:
        raise HTTPException(status_code=404, detail="合同不存在")
    risks = await svc.get_risks(contract_id)
    return [ContractRiskOut.model_validate(r) for r in risks]


@router.get("/{contract_id}/clauses", response_model=list[ContractClauseOut])
async def list_clauses(
    contract_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[ContractClauseOut]:
    """合同逐条款（Clause Analyzer 数据源）。"""
    svc = ContractService(db)
    contract = await svc.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="合同不存在")
    if contract.user_id != current.id and not current.is_superuser:
        raise HTTPException(status_code=404, detail="合同不存在")
    clauses = await svc.get_clauses(contract_id)
    return [ContractClauseOut.model_validate(c) for c in clauses]


# ---------------------------------------------------------------------------
# 报告生成（Step5）
# ---------------------------------------------------------------------------
@router.get("/{contract_id}/report", response_model=ContractReportOut)
async def get_contract_report(
    contract_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
    report_type: str = Query("review", description="报告类型：review/summary/full/checklist"),
    regenerate: bool = Query(False, description="是否强制重新生成（忽略已存报告）"),
) -> ContractReportOut:
    """生成或取回合同审查报告。

    - 未指定 ``regenerate`` 且同类型报告已存在 → 直接返回已存报告（不重复消耗 AI）。
    - ``regenerate=true`` 或尚无报告 → 调用 ``generate_report``：拼装 Markdown 正文，
      可选 AI 叙事（feature ``case_summary``，不可用则降级为规则生成），写入
      ``contract_reports`` 并返回。
    """
    svc = ContractService(db)
    contract = await svc.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="合同不存在")
    if contract.user_id != current.id and not current.is_superuser:
        raise HTTPException(status_code=404, detail="合同不存在")

    report, _generated = await generate_report(
        contract, db, _mgr(db), user_id=current.id, report_type=report_type, regenerate=regenerate
    )
    await db.commit()
    await db.refresh(report)
    return ContractReportOut.model_validate(report)


@router.get("/{contract_id}/reports", response_model=list[ContractReportOut])
async def list_contract_reports(
    contract_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[ContractReportOut]:
    """列出该合同已生成的全部报告（按生成时间倒序）。"""
    svc = ContractService(db)
    contract = await svc.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="合同不存在")
    if contract.user_id != current.id and not current.is_superuser:
        raise HTTPException(status_code=404, detail="合同不存在")
    reports = await svc.list_reports(contract_id)
    return [ContractReportOut.model_validate(r) for r in reports]


# ---------------------------------------------------------------------------
# 提醒 / 待办（Step6 提醒中心）
# ---------------------------------------------------------------------------
@router.get("/{contract_id}/tasks", response_model=list[ContractTaskOut])
async def list_contract_tasks(
    contract_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
    type_filter: str | None = Query(None, alias="type", description="reminder / checklist"),
) -> list[ContractTaskOut]:
    """列出合同下的提醒 / 待办。"""
    svc = ContractService(db)
    contract = await svc.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="合同不存在")
    if contract.user_id != current.id and not current.is_superuser:
        raise HTTPException(status_code=404, detail="合同不存在")
    tasks = await svc.list_tasks(contract_id, type=type_filter)
    return [ContractTaskOut.model_validate(t) for t in tasks]


@router.post("/{contract_id}/tasks", response_model=ContractTaskOut, status_code=status.HTTP_201_CREATED)
async def create_contract_task(
    contract_id: uuid.UUID,
    body: ContractTaskCreate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> ContractTaskOut:
    """为合同创建一条提醒 / 待办（提醒中心数据源）。"""
    svc = ContractService(db)
    contract = await svc.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="合同不存在")
    if contract.user_id != current.id and not current.is_superuser:
        raise HTTPException(status_code=404, detail="合同不存在")
    task = await svc.create_task(
        contract_id,
        type=body.type,
        title=body.title,
        category=body.category,
        due_date=body.due_date,
        remind_before_days=body.remind_before_days,
        done=body.done,
        priority=body.priority,
        note=body.note,
    )
    await db.commit()
    await db.refresh(task)
    out = ContractTaskOut.model_validate(task)
    out.contract_title = contract.title
    return out


@router.patch("/{contract_id}/tasks/{task_id}", response_model=ContractTaskOut)
async def update_contract_task(
    contract_id: uuid.UUID,
    task_id: uuid.UUID,
    body: ContractTaskUpdate,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> ContractTaskOut:
    """更新提醒 / 待办（标题、日期、优先级、完成状态等）。"""
    svc = ContractService(db)
    contract = await svc.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="合同不存在")
    if contract.user_id != current.id and not current.is_superuser:
        raise HTTPException(status_code=404, detail="合同不存在")
    task = await svc.get_task(task_id)
    if task is None or task.contract_id != contract_id:
        raise HTTPException(status_code=404, detail="提醒不存在")
    await svc.update_task(
        task,
        type=body.type,
        title=body.title,
        category=body.category,
        due_date=body.due_date,
        remind_before_days=body.remind_before_days,
        done=body.done,
        priority=body.priority,
        note=body.note,
    )
    await db.commit()
    await db.refresh(task)
    out = ContractTaskOut.model_validate(task)
    out.contract_title = contract.title
    return out


@router.delete("/{contract_id}/tasks/{task_id}", response_model=ContractTaskOut)
async def delete_contract_task(
    contract_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> ContractTaskOut:
    """删除提醒 / 待办。"""
    svc = ContractService(db)
    contract = await svc.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="合同不存在")
    if contract.user_id != current.id and not current.is_superuser:
        raise HTTPException(status_code=404, detail="合同不存在")
    task = await svc.get_task(task_id)
    if task is None or task.contract_id != contract_id:
        raise HTTPException(status_code=404, detail="提醒不存在")
    out = ContractTaskOut.model_validate(task)
    out.contract_title = contract.title
    await svc.delete_task(task)
    await db.commit()
    return out


@router.get("/tasks/upcoming", response_model=list[ContractTaskOut])
async def list_upcoming_tasks(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365, description="未来 N 天内到期的提醒"),
) -> list[ContractTaskOut]:
    """提醒中心聚合：当前用户所有「未完成」且 due_date 在 [今天, 今天+N天] 的提醒。

    含已逾期（due_date < 今天）项，按 due_date 升序。返回结果带 ``contract_title``。
    """
    svc = ContractService(db)
    rows = await svc.list_upcoming(current.id, days=days)
    result: list[ContractTaskOut] = []
    for task, title in rows:
        out = ContractTaskOut.model_validate(task)
        out.contract_title = title
        result.append(out)
    return result


# ---------------------------------------------------------------------------
# 删除
# ---------------------------------------------------------------------------
@router.delete("/{contract_id}", response_model=ContractOut)
async def delete_contract(
    contract_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> ContractOut:
    """删除合同（仅本人或超管）。"""
    svc = ContractService(db)
    contract = await svc.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="合同不存在")
    if contract.user_id != current.id and not current.is_superuser:
        raise HTTPException(status_code=404, detail="合同不存在")
    # 先序列化（删除后对象会被过期，无法再惰性加载属性）
    out = ContractOut.model_validate(contract)
    await svc.delete(contract)
    await db.commit()
    return out
