"""引用来源构建（Citations）。

将检索结果转换为结构化引用，供「案件报告 / 涉及法律」章节与前端展示使用。
所有引用均指向知识库中的真实条目（legal_reference / knowledge），
确保 AI 输出可被溯源、可被核验，避免凭空编造法律条文。
"""
from __future__ import annotations

from typing import List

from app.services.rag.retriever import RetrievedChunk


def build_citation(chunk: RetrievedChunk) -> dict:
    """将单个检索结果转换为引用字典。

    字段说明（与前端约定一致）：
    - id / source_table / source：用于回链与过滤
    - label：面向用户的可读引用（如「《民法典》 第577条」）
    - snippet：正文摘要
    - score：最终排序得分（用于可信度标注）
    """
    return {
        "id": str(chunk.id),
        "source_table": chunk.source_table,
        "source": chunk.source.value,
        "label": chunk.citation or chunk.title,
        "title": chunk.title,
        "article": chunk.article,
        "snippet": chunk.to_snippet(),
        "score": round(chunk.score, 4),
    }


def build_citations(chunks: List[RetrievedChunk]) -> List[dict]:
    """批量构建引用。"""
    return [build_citation(c) for c in chunks]


def format_legal_basis(chunks: List[RetrievedChunk], max_items: int = 5) -> str:
    """生成报告「涉及法律」章节的 Markdown 列表。"""
    lines: List[str] = []
    for c in chunks[:max_items]:
        label = c.citation or c.title
        snippet = c.to_snippet(120)
        lines.append(f"- **{label}**：{snippet}")
    return "\n".join(lines)
