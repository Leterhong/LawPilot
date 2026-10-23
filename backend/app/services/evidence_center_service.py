"""智能证据中心服务层：证据文件主记录 CRUD（Step2 范围）。

只负责 ``evidence_files`` 主表的增删查与上传后的状态回写。AI 解析（Step3）、
证据关系 / 时间线（Step4）、报告（Step5）由各自逻辑处理，本服务保持纯净、可复用。
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EvidenceFileCategoryEnum, EvidenceFileStatusEnum
from app.models.evidence_center import EvidenceFile

# 证据中心支持的文件类型（比合同更广：含图片 / 音视频 / 邮件 / 网页截图等）
EVIDENCE_ALLOWED_EXTENSIONS: set[str] = {
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
    ".md",
    ".rtf",
    # 图片（含微信 / 支付宝 / 银行流水截图）
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
    ".heic",
    # 音频
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".ogg",
    # 视频
    ".mp4",
    ".mov",
    ".avi",
    ".webm",
    ".mkv",
    # 邮件 / 网页
    ".eml",
    ".msg",
    ".html",
    ".htm",
}


def is_supported(ext: str) -> bool:
    """是否允许上传的文件扩展名（ext 形如 '.pdf'，已小写）。"""
    return ext.lower() in EVIDENCE_ALLOWED_EXTENSIONS


def _resolve_category(value: str | None) -> EvidenceFileCategoryEnum:
    """将字符串解析为证据类型枚举，非法值降级为 ``other``。"""
    try:
        return EvidenceFileCategoryEnum(value)
    except (ValueError, TypeError):
        return EvidenceFileCategoryEnum.OTHER


# 扩展名 → 初步证据类型（仅作上传时的粗分类，Step3 由 AI 重新判定）
_EXT_CATEGORY: dict[str, EvidenceFileCategoryEnum] = {
    ".pdf": EvidenceFileCategoryEnum.DOCUMENT,
    ".doc": EvidenceFileCategoryEnum.DOCUMENT,
    ".docx": EvidenceFileCategoryEnum.DOCUMENT,
    ".txt": EvidenceFileCategoryEnum.DOCUMENT,
    ".md": EvidenceFileCategoryEnum.DOCUMENT,
    ".rtf": EvidenceFileCategoryEnum.DOCUMENT,
    ".png": EvidenceFileCategoryEnum.PHOTO,
    ".jpg": EvidenceFileCategoryEnum.PHOTO,
    ".jpeg": EvidenceFileCategoryEnum.PHOTO,
    ".gif": EvidenceFileCategoryEnum.PHOTO,
    ".webp": EvidenceFileCategoryEnum.PHOTO,
    ".bmp": EvidenceFileCategoryEnum.PHOTO,
    ".tif": EvidenceFileCategoryEnum.PHOTO,
    ".tiff": EvidenceFileCategoryEnum.PHOTO,
    ".heic": EvidenceFileCategoryEnum.PHOTO,
    ".mp3": EvidenceFileCategoryEnum.AUDIO,
    ".wav": EvidenceFileCategoryEnum.AUDIO,
    ".m4a": EvidenceFileCategoryEnum.AUDIO,
    ".aac": EvidenceFileCategoryEnum.AUDIO,
    ".ogg": EvidenceFileCategoryEnum.AUDIO,
    ".mp4": EvidenceFileCategoryEnum.VIDEO,
    ".mov": EvidenceFileCategoryEnum.VIDEO,
    ".avi": EvidenceFileCategoryEnum.VIDEO,
    ".webm": EvidenceFileCategoryEnum.VIDEO,
    ".mkv": EvidenceFileCategoryEnum.VIDEO,
    ".eml": EvidenceFileCategoryEnum.EMAIL,
    ".msg": EvidenceFileCategoryEnum.EMAIL,
    ".html": EvidenceFileCategoryEnum.WEBPAGE,
    ".htm": EvidenceFileCategoryEnum.WEBPAGE,
}


def guess_category(ext: str) -> EvidenceFileCategoryEnum:
    """依扩展名粗分类（上传阶段用，非 AI 判定）。"""
    return _EXT_CATEGORY.get(ext.lower(), EvidenceFileCategoryEnum.OTHER)


class EvidenceCenterService:
    """证据文件主记录 CRUD。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        user_id: UUID | None,
        name: str,
        category: EvidenceFileCategoryEnum,
        status: EvidenceFileStatusEnum = EvidenceFileStatusEnum.UPLOADED,
        file_url: str | None = None,
        file_type: str | None = None,
        mime_type: str | None = None,
        size_bytes: int | None = None,
        case_id: UUID | None = None,
        source: str | None = None,
        tags: list | None = None,
    ) -> EvidenceFile:
        ef = EvidenceFile(
            user_id=user_id,
            name=name,
            category=category,
            status=status,
            file_url=file_url,
            file_type=file_type,
            mime_type=mime_type,
            size_bytes=size_bytes,
            case_id=case_id,
            source=source,
            tags=tags,
        )
        self.db.add(ef)
        await self.db.flush()
        return ef

    async def update(
        self, evidence: EvidenceFile, **fields: object
    ) -> EvidenceFile:
        """按字段回写（OCR / 分析 / 关联等步骤复用）。None 表示不更新。"""
        allowed = {
            "name",
            "category",
            "status",
            "file_url",
            "file_type",
            "mime_type",
            "size_bytes",
            "ocr_text",
            "meta",
            "formed_at",
            "source",
            "tags",
            "case_id",
        }
        for k, v in fields.items():
            if k in allowed and v is not None:
                if k == "category" and not isinstance(v, EvidenceFileCategoryEnum):
                    v = _resolve_category(str(v))
                setattr(evidence, k, v)
        self.db.add(evidence)
        await self.db.flush()
        return evidence

    async def get(self, evidence_id: UUID) -> EvidenceFile | None:
        return await self.db.get(EvidenceFile, evidence_id)

    async def list_for_user(
        self,
        user_id: UUID | None = None,
        *,
        category: str | None = None,
        status: str | None = None,
        case_id: UUID | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[EvidenceFile], int]:
        """列出证据文件。

        - 普通用户只看自己的（``user_id`` 匹配）；传入 ``None`` 视为管理员视角。
        - 支持按类型 / 状态 / 案件筛选，按名称模糊搜索（``q``）。
        """
        conds = []
        if user_id is not None:
            conds.append(EvidenceFile.user_id == user_id)
        if category:
            conds.append(EvidenceFile.category == category)
        if status:
            conds.append(EvidenceFile.status == status)
        if case_id is not None:
            conds.append(EvidenceFile.case_id == case_id)
        if q:
            conds.append(EvidenceFile.name.ilike(f"%{q}%"))

        total = await self.db.scalar(
            select(func.count()).select_from(EvidenceFile).where(*conds)
        )
        total = int(total or 0)

        stmt = (
            select(EvidenceFile)
            .where(*conds)
            .order_by(EvidenceFile.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.db.scalars(stmt)).all()
        return list(rows), total

    async def delete(self, evidence: EvidenceFile) -> None:
        await self.db.delete(evidence)
        await self.db.flush()
