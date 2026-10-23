"""证据服务：上传落库 + OCR / 文本提取。

- 校验扩展名与体积（来自配置）。
- 保存文件到 upload_dir，文件名随机化避免冲突。
- 对图片执行 OCR（pytesseract，缺失则跳过）；对 txt/docx/pdf 尝试文本提取。
- 同时支持「规划中但未提供」的证据项（is_uploaded=False）。
"""
from __future__ import annotations

import os
import uuid

from fastapi import UploadFile

from app.core.config import settings
from app.models.case import Case
from app.models.enums import EventTypeEnum, EvidenceCategoryEnum
from app.models.evidence import Evidence
from app.models.user import User
from app.repositories.case_repo import EvidenceRepository
from app.repositories.task_repo import HistoryRepository


class EvidenceService:
    def __init__(self, session) -> None:
        self.repo = EvidenceRepository(session)
        self.history = HistoryRepository(session)

    async def add_uploaded(
        self,
        case: Case,
        user: User,
        file: UploadFile,
        category: EvidenceCategoryEnum,
        title: str | None,
        description: str | None = None,
    ) -> Evidence:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in settings.allowed_extensions_list:
            raise ValueError("BAD_EXTENSION")

        content = await file.read()
        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise ValueError("FILE_TOO_LARGE")

        os.makedirs(settings.upload_dir, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}{ext}"
        stored_path = os.path.join(settings.upload_dir, stored_name)
        with open(stored_path, "wb") as f:
            f.write(content)

        ocr_text = self._extract_text(stored_path, ext)
        evidence = await self.repo.create(
            case_id=case.id,
            user_id=user.id,
            category=category,
            title=title or (file.filename or "未命名证据"),
            description=description,
            file_path=stored_path,
            file_type=ext.lstrip("."),
            ocr_text=ocr_text,
            is_uploaded=True,
        )
        await self.history.create(
            case_id=case.id,
            user_id=user.id,
            event_type=EventTypeEnum.EVIDENCE_ADDED,
            title="上传证据",
            detail=evidence.title,
        )
        return evidence

    async def add_planned(
        self,
        case: Case,
        category: EvidenceCategoryEnum,
        title: str,
        description: str | None = None,
        ai_note: str | None = None,
    ) -> Evidence:
        """添加尚未提供、但案件需要的证据项（规划用）。"""
        return await self.repo.create(
            case_id=case.id,
            category=category,
            title=title,
            description=description,
            ai_note=ai_note,
            is_uploaded=False,
        )

    @staticmethod
    def _extract_text(path: str, ext: str) -> str | None:
        """从文件中提取文本（图片 OCR / 文本类文件）。失败返回 None。"""
        try:
            if ext in (".png", ".jpg", ".jpeg"):
                import pytesseract
                from PIL import Image

                return pytesseract.image_to_string(Image.open(path)).strip() or None
            if ext == ".txt":
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read().strip() or None
            if ext == ".docx":
                from docx import Document as DocxDocument

                doc = DocxDocument(path)
                return "\n".join(p.text for p in doc.paragraphs).strip() or None
            if ext == ".pdf":
                # 优先 pdfminer.six，回退 PyPDF2
                try:
                    from pdfminer.high_level import extract_text as pdf_text

                    return pdf_text(path).strip() or None
                except Exception:
                    from PyPDF2 import PdfReader

                    reader = PdfReader(path)
                    return "\n".join(p.extract_text() or "" for p in reader.pages).strip() or None
        except Exception:
            # OCR/解析失败不应阻断上传，仅留空
            return None
        return None
