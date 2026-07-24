"""合同解析工具：文本提取、OCR、自动分类。

设计要点（与证据模块一致，但 **独立实现，不改动 evidence 业务**）：
- 文本类（pdf/docx/txt/md）直接提取纯文本；
- 图片类（png/jpg/jpeg）优先走 ``AIManager.vision(feature="ocr_analysis")``
  多模态 OCR（对中文扫描件更稳），回退到 ``pytesseract``；两者都不可用则返回 None；
- 自动分类优先走 AI（``contract_review`` feature，json_mode），回退关键词启发式；
- **任何异常都优雅降级为 None / 兜底值**，绝不阻断上传。
"""
from __future__ import annotations

import base64
import json
import os
import re

from app.models.contract import CONTRACT_ALLOWED_EXTENSIONS, CONTRACT_TYPES

# 图片扩展名
_IMAGE_EXTS = {".png", ".jpg", ".jpeg"}
# OCR / 文本提取支持的全部扩展名（来自共享常量）
_SUPPORTED = set(CONTRACT_ALLOWED_EXTENSIONS)


def is_supported(ext: str) -> bool:
    """判断扩展名是否在合同模块允许列表内。"""
    return ext.lower() in _SUPPORTED


def is_image(ext: str) -> bool:
    """是否为图片（需 OCR）。"""
    return ext.lower() in _IMAGE_EXTS


# ---------------------------------------------------------------------------
# 文本提取（非图片）
# ---------------------------------------------------------------------------
def extract_text(path: str, ext: str) -> str | None:
    """从 pdf/docx/txt/md 文件中提取纯文本。失败返回 None。"""
    try:
        ext = ext.lower()
        if ext == ".txt":
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().strip() or None
        if ext == ".md":
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
        # 解析失败不应阻断上传，仅留空
        return None
    return None


# ---------------------------------------------------------------------------
# OCR（图片）
# ---------------------------------------------------------------------------
def _image_to_data_url(path: str, ext: str) -> str:
    """将本地图片读为 base64 data URL（供 vision 接口）。"""
    subtype = "jpeg" if ext.lower() in (".jpg", ".jpeg") else "png"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/{subtype};base64,{b64}"


async def ocr_with_vision(path: str, ext: str, mgr) -> str | None:
    """多模态 OCR：通过 AIManager.vision(feature="ocr_analysis") 提取图片文字。

    失败（无 key / 调用异常 / 返回空）返回 None。
    """
    if mgr is None:
        return None
    data_url = _image_to_data_url(path, ext)
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "这是一份合同或法律文件的扫描图片。请完整、准确地识别并提取"
                        "其中所有文字内容，保留原有段落与条款编号结构，直接输出纯文本，"
                        "不要添加任何解释或 Markdown 代码块。"
                    ),
                },
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]
    try:
        text = await mgr.vision(feature="ocr_analysis", messages=messages)  # type: ignore[call-arg]
    except Exception:
        return None
    return text.strip() if text else None


def ocr_with_tesseract(path: str) -> str | None:
    """回退 OCR：pytesseract。未安装 / 失败返回 None。"""
    try:
        from PIL import Image
        import pytesseract

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
# 自动分类
# ---------------------------------------------------------------------------
# 关键词启发式（AI 不可用时的兜底），按优先级从高到低
# 注意：nda（保密）通常只是合同里的一个条款，而非合同整体类型，故放在最后，
# 避免正文含「保密」就让整份租赁合同被误判为保密协议。
_KEYWORD_RULES: list[tuple[str, list[str]]] = [
    ("labor", ["劳动", "雇佣", "员工", "用人单位", "劳动合同", "employment"]),
    ("rent", ["租赁", "出租", "承租", "租房", "房租", "lease", "tenant"]),
    ("loan", ["借款", "借贷", "贷款", "出借人", "借款人", "loan"]),
    ("purchase", ["采购", "供货", "供应商", "purchase"]),
    ("sales", ["买卖", "购销", "销售合同", "出卖人", "买受人", "sales"]),
    ("service", ["服务", "咨询", "技术服务", "委托服务", "service"]),
    ("cooperation", ["合作", "联营", "合伙", "cooperation"]),
    ("nda", ["保密", "机密", "confidential", "non-disclosure", "不披露"]),
]


def classify_heuristic(title: str, text: str) -> str:
    """关键词启发式分类。"""
    blob = f"{title or ''}\n{text or ''}".lower()
    for ctype, kws in _KEYWORD_RULES:
        for kw in kws:
            if kw.lower() in blob:
                return ctype
    return "other"


_CLASSIFY_SYSTEM = (
    "你是专业的合同分类助手。用户会给你一份合同的标题与正文片段，"
    "你需要判断它属于哪种合同类型。只能从给定的类型列表中选一个，"
    "并以严格的 JSON 格式返回：{\"contract_type\": \"<类型键>\"}，不要输出多余内容。"
)


def _build_classify_user(title: str, text: str) -> str:
    labels = "、".join(CONTRACT_TYPES)
    snippet = (text or "")[:3000]
    return (
        f"可选合同类型（必须择一）：{labels}\n"
        f"标题：{title or '（无标题）'}\n"
        f"正文片段：\n{snippet}"
    )


async def classify_contract(title: str, text: str, mgr=None) -> str:
    """合同自动分类：优先 AI（contract_review feature, json_mode），回退启发式。"""
    if mgr is not None and text:
        messages = [
            {"role": "system", "content": _CLASSIFY_SYSTEM},
            {"role": "user", "content": _build_classify_user(title, text)},
        ]
        try:
            raw = await mgr.chat(  # type: ignore[call-arg]
                "contract_review", messages, json_mode=True
            )
        except Exception:
            raw = None
        if raw:
            try:
                data = json.loads(raw)
                ctype = data.get("contract_type")
                if ctype in CONTRACT_TYPES:
                    return ctype
            except Exception:
                # 尝试从文本中截取 JSON
                m = re.search(r"\{.*\}", raw, re.DOTALL)
                if m:
                    try:
                        data = json.loads(m.group(0))
                        if data.get("contract_type") in CONTRACT_TYPES:
                            return data["contract_type"]
                    except Exception:
                        pass
    return classify_heuristic(title, text)


# ---------------------------------------------------------------------------
# 便捷入口：给定本地路径，返回 (full_text, ocr_text, contract_type)
# ---------------------------------------------------------------------------
async def parse_contract_file(
    path: str,
    ext: str,
    title: str | None,
    mgr=None,
) -> tuple[str | None, str | None, str]:
    """解析一个已落盘的合同文件。

    返回 ``(full_text, ocr_text, contract_type)``。
    - 图片：ocr_text 为 OCR 结果，full_text 与 ocr_text 相同（便于统一检索）。
    - 文本类：full_text 为提取文本，ocr_text 为 None。
    - contract_type 始终有值（启发式兜底）。
    """
    ext = ext.lower()
    if is_image(ext):
        ocr_text = await ocr_image(path, ext, mgr)
        full_text = ocr_text  # 图片全文即 OCR 文本
        ctype = await classify_contract(title, ocr_text or "", mgr)
        return full_text, ocr_text, ctype
    full_text = extract_text(path, ext)
    ctype = await classify_contract(title, full_text or "", mgr)
    return full_text, None, ctype
