"""AI Playground 后端冒烟验证（Step 2）。

验证项：
[A] 所有 playground 模块 + schema 可导入
[B] app.main 导入无循环依赖，且 /api/playground/* 路由已注册
[C] Base.metadata 含 9 张新表
[D] AIManager 暴露 chat_model
[E] 路由端点签名基本正确（通过 app.routes 路径清单断言）
"""
from __future__ import annotations

import app.main as main_mod  # noqa: F401  (触发全部路由注册)
from app.models.base import Base
from app.playground import benchmark, evaluator, history, router, scorer, service
from app.playground.router import router as pg_router
from app.schemas import playground as pg_schemas
from app.services.ai.manager import AIManager


def main() -> None:
    # [C] 9 张新表
    expected = {
        "playground_sessions",
        "model_comparisons",
        "evaluation_datasets",
        "evaluation_items",
        "evaluation_tasks",
        "evaluation_results",
        "prompt_library",
        "model_pricing",
        "playground_publishes",
    }
    missing = expected - set(Base.metadata.tables.keys())
    assert not missing, f"缺失表: {missing}"
    print(f"[C] 新表齐全（{len(expected)} 张）✅")

    # [D] AIManager.chat_model
    assert hasattr(AIManager, "chat_model"), "AIManager 缺少 chat_model"
    print("[D] AIManager.chat_model 存在 ✅")

    # [B/E] 路由注册（用 OpenAPI schema 扁平化路径，避免 _IncludedRouter 嵌套问题）
    paths = set(main_mod.app.openapi()["paths"].keys())
    need = {
        "/api/playground/models",
        "/api/playground/test",
        "/api/playground/compare",
        "/api/playground/evaluate",
        "/api/playground/history",
        "/api/playground/publish",
        "/api/playground/routing",
        "/api/playground/prompts",
        "/api/playground/datasets",
        "/api/playground/evaluations",
    }
    miss_paths = need - paths
    assert not miss_paths, f"缺失路由: {miss_paths}"
    print(f"[B/E] Playground 路由注册齐全（{len(need)} 个）✅")

    # [A] 模块导入已在顶部完成
    print("[A] playground 模块 + schema 导入成功 ✅")

    print("\nALL GREEN ✅ AI Playground 后端 Step 2 验证通过")


if __name__ == "__main__":
    main()
