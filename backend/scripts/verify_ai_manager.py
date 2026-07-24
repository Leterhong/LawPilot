"""Step 4 验证：AIManager + LLMClient/EmbeddingService 适配层冒烟。

验证项：
A) 全部相关模块可导入（含业务调用方 research_service / rag.retriever）；
B) 无 key 场景：chat 返回 None（不崩溃），embed 抛 RuntimeError（与旧契约一致）；
C) DB 路由解析：用轻量 FakeDB 验证「按 routing_rules 选模型 + Prompt + fallback」
   与「数据库为空 / 无规则 → settings 回退」两条核心路径。

运行：PYTHONPATH=F:/falv/backend backend/.venv_clean/Scripts/python.exe backend/scripts/verify_ai_manager.py
"""
from __future__ import annotations

import asyncio
import operator
import sys
from uuid import uuid4

from sqlalchemy import BinaryExpression
from sqlalchemy.sql.elements import BindParameter

# ---------- A) 导入冒烟 ----------
try:
    from app.core.crypto import encrypt_secret
    from app.models.ai_center import AIModel, PromptTemplate, Provider, RoutingRule
    from app.services.ai.manager import AIManager, ResolvedRoute
    from app.services.llm.client import LLMClient
    from app.services.rag.embedder import EmbeddingService

    # 业务调用方是否仍能正常导入（确保未破坏既有 import）
    import app.services.research_service  # noqa: F401
    import app.services.rag.retriever  # noqa: F401
    import app.services.agent.engine  # noqa: F401

    print("[A] import smoke .................... OK")
except Exception as exc:  # noqa: BLE001
    print(f"[A] import smoke .................... FAIL: {exc}")
    sys.exit(1)


# ---------- B) 无 key 优雅降级 ----------
async def test_no_key() -> None:
    llm = LLMClient()  # 无 db → settings 回退（placeholder key）
    assert llm.available is False, "settings placeholder key 应判定为不可用"
    out = await llm.complete("你好")
    assert out is None, "无 key 时 chat 应返回 None 而非抛错"
    j = await llm.complete_json("{}")
    assert j is None, "无 key 时 complete_json 应返回 None"

    emb = EmbeddingService()
    assert emb.available is False
    try:
        await emb.embed_doc("测试文本")
        raise AssertionError("embed 未配置时应抛 RuntimeError（与旧契约一致）")
    except RuntimeError:
        pass
    print("[B] no-key graceful ................ OK")


# ---------- C) FakeDB 路由解析 ----------
class _Result:
    def __init__(self, objs):
        self.objs = objs

    def first(self):
        return self.objs[0] if self.objs else None

    def all(self):
        return self.objs


def _eval(expr, obj):
    if isinstance(expr, BinaryExpression):
        left = expr.left
        name = getattr(left, "name", None) or getattr(left, "key", None)
        right = expr.right
        rval = right.value if isinstance(right, BindParameter) else right
        if expr.operator is operator.eq:
            return getattr(obj, name, None) == rval
    return True


class FakeDB:
    """极简异步会话桩，仅满足 AIManager 路由解析所需的 get/scalars/add/flush。"""

    def __init__(self, store: dict):
        self._store = store  # {Model: {id: obj}}
        self.added = []

    async def get(self, model, id):
        return self._store.get(model, {}).get(id)

    async def scalars(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        objs = list(self._store.get(entity, {}).values())
        if getattr(stmt, "whereclause", None) is not None:
            objs = [o for o in objs if _eval(stmt.whereclause, o)]
        return _Result(objs)

    async def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


async def test_routing() -> None:
    pid = uuid4()
    mid = uuid4()
    rid = uuid4()
    ptid = uuid4()

    p = Provider(
        id=pid,
        name="硅基流动",
        type="siliconflow",
        base_url="https://api.siliconflow.cn/v1",
        api_key=encrypt_secret("sk-real-abc123"),
    )
    m = AIModel(
        id=mid,
        name="SF-Qwen",
        provider_id=pid,
        provider_type="siliconflow",
        model_name="Qwen/Qwen2.5-7B-Instruct",
        is_enabled=True,
        temperature=0.3,
        capabilities={"chat": True, "json_mode": True},
    )
    pt = PromptTemplate(
        id=ptid,
        key="legal_analysis",
        name="法律分析Prompt",
        content="系统：你是严谨的中国法律分析助手。",
        current_version=1,
        enabled=True,
    )
    r = RoutingRule(
        id=rid,
        feature="legal_analysis",
        model_id=mid,
        fallback_model_ids=None,
        auto_route=False,
        prompt_template_key="legal_analysis",
        enabled=True,
    )
    store = {Provider: {pid: p}, AIModel: {mid: m}, PromptTemplate: {ptid: pt}, RoutingRule: {rid: r}}
    mgr = AIManager(FakeDB(store))

    route = await mgr._resolve("legal_analysis", "chat")
    assert route.source == "db", route.source
    assert route.model_name == "Qwen/Qwen2.5-7B-Instruct", route.model_name
    assert route.base_url == "https://api.siliconflow.cn/v1", route.base_url
    assert route.api_key == "sk-real-abc123", "api_key 应解密为明文"
    assert route.system_prompt == "系统：你是严谨的中国法律分析助手。", route.system_prompt
    assert route.fallbacks == []
    assert route.has_key is True
    assert await mgr.available("legal_analysis") is True
    print("[C1] db routing resolve ............. OK")

    # fallback 链
    mid2 = uuid4()
    m2 = AIModel(
        id=mid2, name="SF-Fallback", provider_id=pid, provider_type="siliconflow",
        model_name="Qwen/Qwen2.5-3B", is_enabled=True, temperature=0.2,
        capabilities={"chat": True},
    )
    store[AIModel][mid2] = m2
    r.fallback_model_ids = [mid2]
    route2 = await mgr._resolve("legal_analysis", "chat")
    assert len(route2.fallbacks) == 1
    assert route2.fallbacks[0].model_name == "Qwen/Qwen2.5-3B"
    print("[C2] fallback chain ................. OK")

    # 数据库为空 / 无规则 → settings 回退
    mgr_settings = AIManager(None)
    rs = await mgr_settings._resolve("legal_analysis", "chat")
    assert rs.source == "settings"
    assert rs.has_key is False  # placeholder key
    print("[C3] settings fallback (no db) ...... OK")

    # 有 db 但 feature 无规则 → settings 回退
    mgr_empty = AIManager(FakeDB(store))
    re = await mgr_empty._resolve("nonexistent_feature", "chat")
    assert re.source == "settings"
    print("[C4] settings fallback (no rule) .... OK")


async def main() -> None:
    await test_no_key()
    await test_routing()
    print("\nALL PASS ✅")


if __name__ == "__main__":
    asyncio.run(main())
