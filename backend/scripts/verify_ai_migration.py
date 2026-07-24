"""Step 5 迁移验证：确认现有 AI 调用已接到 AIManager，且无回归。

验证内容：
A) 全部改动模块可导入（含 app.main，无循环导入；await 守卫语法正确）；
B) 无 db 时，适配层同步 ``available`` 仍基于 settings（零回归）；
C) ``available_async`` 在无 db 时回退 settings 并返回 bool（守卫可安全 await）；
D) 构造带 db 的实例，feature/capability 正确透传到 AIManager（db 路由接线正确）。
"""
from __future__ import annotations

import asyncio
import importlib


def _import_all() -> None:
    mods = [
        "app.main",
        "app.services.law_search_service",
        "app.services.research_service",
        "app.services.legal_case_search_service",
        "app.services.case_center_service",
        "app.services.agent.engine",
        "app.repositories.law_repo",
        "app.repositories.legal_case_repo",
        "app.repositories.research_repo",
        "app.services.rag.retriever",
        "app.services.rag.ingest",
        "app.services.llm.client",
        "app.services.rag.embedder",
    ]
    for m in mods:
        importlib.import_module(m)


def _smoke() -> None:
    from app.services.llm.client import LLMClient
    from app.services.rag.embedder import EmbeddingService
    from app.core.config import settings

    # B) 同步 available 基于 settings（零回归）
    llm = LLMClient(feature="legal_analysis")
    emb = EmbeddingService(feature="embedding")
    llm_expected = bool(settings.llm_api_key) and settings.llm_api_key != "sk-your-key-here"
    emb_expected = bool(settings.embedding_api_key) and settings.embedding_api_key != "sk-your-key-here"
    assert llm.available == llm_expected, f"LLMClient.available={llm.available} 期望 {llm_expected}"
    assert emb.available == emb_expected, f"EmbeddingService.available={emb.available} 期望 {emb_expected}"

    # C) available_async 无 db 时回退 settings，返回 bool
    assert isinstance(asyncio.run(llm.available_async()), bool)
    assert isinstance(asyncio.run(emb.available_async()), bool)

    # D) db/feature 透传
    llm2 = LLMClient(db="FAKE_SESSION", feature="case_overview")
    emb2 = EmbeddingService(db="FAKE_SESSION", feature="embedding")
    assert llm2._feature == "case_overview", llm2._feature
    assert llm2._capability == "chat"
    assert emb2._feature == "embedding"
    # AIManager 拿到了 db 引用（路由解析依赖它）
    assert llm2._mgr.db == "FAKE_SESSION"
    assert emb2._mgr.db == "FAKE_SESSION"


def main() -> None:
    _import_all()
    print("[OK] A) 全部改动模块导入成功（含 app.main，无循环导入）")
    _smoke()
    print("[OK] B) 无 db：同步 available 基于 settings（零回归）")
    print("[OK] C) 无 db：available_async 可 await 且返回 bool（守卫安全）")
    print("[OK] D) 带 db：feature/capability 正确透传到 AIManager（db 路由接线正确）")
    print("\nStep 5 迁移基础验证全部通过。")


if __name__ == "__main__":
    main()
