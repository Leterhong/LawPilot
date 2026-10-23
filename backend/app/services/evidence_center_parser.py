"""智能证据中心：文本提取 / OCR（Step3）。

与合同模块 ``app/contract/parser.py`` 思路一致，但**独立实现，不改动合同模块**，
且支持证据中心更广的文件类型（图片截图 / 邮件 / 网页 / 音视频占位）。

设计要点：
- 文本类（pdf/docx/txt/md/rtf/html/eml）直接提取纯文本；
- 图片类（png/jpg/...）优先 ``AIManager.vision(feature="ocr_analysis")`` 多模态
  OCR（对微信/支付宝/银行流水截图更稳），回退 ``pytesseract``；都不可用返回 None；
- 音视频暂不做转写（后续可接 ASR），返回 None 但不报错；
- **任何异常都优雅降级为 None**，绝不阻断分析流程。
"""
from __future__ import annotations

import base64
import email
import email.policy
import re

# 图片扩展名（可送 OCR）
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
# 音视频（暂不转写）
_MEDIA_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".mp4", ".mov", ".avi", ".webm", ".mkv"}

# vision 接口不支持的图片子类型统一按 png 声明
_MIME_SUBTYPE = {
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".png": "png",
    ".gif": "gif",
    ".webp": "webp",
    ".bmp": "bmp",
}


def is_image(ext: str) -> bool:
    """是否为图片（需 OCR）。"""
    return ext.lower() in _IMAGE_EXTS


def is_media(ext: str) -> bool:
    """是否为音视频（暂不支持转写）。"""
    return ext.lower() in _MEDIA_EXTS


# ---------------------------------------------------------------------------
# 文本提取（非图片）
# ---------------------------------------------------------------------------
def extract_text(path: str, ext: str) -> str | None:
    """从文本类证据文件中提取纯文本。失败返回 None。"""
    try:
        ext = ext.lower()
        if ext in (".txt", ".md"):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().strip() or None
        if ext == ".rtf":
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()
            # 朴素去除 RTF 控制字：足够供 AI 理解，不追求完美排版
            text = re.sub(r"\\[a-zA-Z]+-?\d*\s?|[{}]", "", raw)
            return text.strip() or None
        if ext in (".html", ".htm"):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()
            text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text)
            return text.strip() or None
        if ext == ".eml":
            with open(path, "rb") as f:
                msg = email.message_from_binary_file(f, policy=email.policy.default)
            parts = [
                f"发件人: {msg.get('From', '')}",
                f"收件人: {msg.get('To', '')}",
                f"主题: {msg.get('Subject', '')}",
                f"日期: {msg.get('Date', '')}",
                "",
            ]
            body = msg.get_body(preferencelist=("plain", "html"))
            if body is not None:
                content = body.get_content()
                if body.get_content_type() == "text/html":
                    content = re.sub(r"<[^>]+>", " ", content)
                    content = re.sub(r"\s+", " ", content)
                parts.append(content.strip())
            return "\n".join(parts).strip() or None
        if ext == ".docx":
            from docx import Document as DocxDocument

            doc = DocxDocument(path)
            return "\n".join(p.text for p in doc.paragraphs).strip() or None
        if ext == ".doc":
            # 旧版 .doc 无纯 Python 稳定解析方案，返回 None 由调用方降级
            return None
        if ext == ".pdf":
            try:
                from pdfminer.high_level import extract_text as pdf_text

                return pdf_text(path).strip() or None
            except Exception:
                from PyPDF2 import PdfReader

                reader = PdfReader(path)
                return "\n".join(p.extract_text() or "" for p in reader.pages).strip() or None
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# OCR（图片）
# ---------------------------------------------------------------------------
def _image_to_data_url(path: str, ext: str) -> str:
    """将本地图片读为 base64 data URL（供 vision 接口）。"""
    subtype = _MIME_SUBTYPE.get(ext.lower(), "png")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/{subtype};base64,{b64}"


async def ocr_with_vision(path: str, ext: str, mgr) -> str | None:
    """多模态 OCR：``AIManager.vision(feature="ocr_analysis")`` 提取图片文字。

    针对证据场景（微信/支付宝截图、银行流水、票据）优化提示词。
    失败（无 key / 调用异常 / 返回空）返回 None。
    """
    if mgr is None:
        return None
    try:
        data_url = _image_to_data_url(path, ext)
    except Exception:
        return None
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "这是一张作为法律证据的图片（可能是微信/支付宝聊天或转账截图、"
                        "银行流水、票据、合同扫描件等）。请完整、准确地识别并提取其中"
                        "所有文字内容：聊天记录请保留「昵称: 内容」的对话结构与时间戳；"
                        "转账/流水请保留金额、时间、单号、双方账户信息；表格按行输出。"
                        "直接输出纯文本，不要添加任何解释或 Markdown 代码块。"
                    ),
                },
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]
    try:
        text = await mgr.vision(feature="ocr_analysis", messages=messages)
    except Exception:
        return None
    return text.strip() if text else None


def ocr_with_tesseract(path: str) -> str | None:
    """回退 OCR：pytesseract。未安装 / 失败返回 None。"""
    try:
        import pytesseract
        from PIL import Image

        text = pytesseract.image_to_string(Image.open(path), lang="chi_sim+eng")
        return text.strip() or None
    except Exception:
        try:
            import pytesseract
            from PIL import Image

            return pytesseract.image_to_string(Image.open(path)).strip() or None
        except Exception:
            return None


async def ocr_image(path: str, ext: str, mgr=None) -> str | None:
    """图片 OCR：优先 AIManager.vision，回退 pytesseract。"""
    text = await ocr_with_vision(path, ext, mgr)
    if text:
        return text
    return ocr_with_tesseract(path)


# ---------------------------------------------------------------------------
# 便捷入口：给定本地路径，返回提取文本
# ---------------------------------------------------------------------------
async def parse_evidence_file(path: str, ext: str, mgr=None) -> tuple[str | None, str]:
    """解析一个已落盘的证据文件。

    返回 ``(text, kind)``：
    - 图片 → OCR 文本，kind="ocr"
    - 文本类 → 提取文本，kind="text"
    - 音视频 → None，kind="media"（暂不转写，AI 分析退化为基于文件名/元信息）
    """
    ext = ext.lower()
    if is_image(ext):
        return await ocr_image(path, ext, mgr), "ocr"
    if is_media(ext):
        return None, "media"
    return extract_text(path, ext), "text"
