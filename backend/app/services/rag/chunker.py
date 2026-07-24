"""文本切块（Chunking）。

将长文本切分为语义相对完整的片段，供后续 Embedding 与检索。
策略：优先按句末标点（中英文句号/问号/感叹号/换行）切分，再按字符窗口
累加，并保留重叠（overlap）以避免边界信息丢失。适配中文无空格文本。
"""
from __future__ import annotations

import re
from typing import List

# 句末切分正则：在 。！？ ! ? . \n 之后断句
_SENT_SPLIT = re.compile(r"(?<=[。！？!?\.\n])")


def chunk_text(
    text: str, chunk_size: int = 600, overlap: int = 80
) -> List[str]:
    """将文本切分为若干片段。

    :param text: 原始文本
    :param chunk_size: 单片段目标字符数
    :param overlap: 相邻片段重叠字符数
    """
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    sentences = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
    chunks: List[str] = []
    cur = ""

    for sent in sentences:
        if len(cur) + len(sent) <= chunk_size:
            cur = cur + sent if cur else sent
        else:
            if cur:
                chunks.append(cur)
            cur = (cur[-overlap:] + sent) if overlap else sent
            # 单句超长则强制按窗口截断
            while len(cur) > chunk_size:
                chunks.append(cur[:chunk_size])
                cur = cur[chunk_size - overlap :] if overlap else cur[chunk_size:]

    if cur:
        chunks.append(cur)
    return chunks


def chunk_document(text: str, **kwargs) -> List[str]:
    """文档级切块（与 chunk_text 同义，便于语义区分）。"""
    return chunk_text(text, **kwargs)
