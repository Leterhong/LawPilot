"""Step 5 DB 路由接线证明：用 FakeSession 让调用方走 AIManager 的 db 路由。

证明：传 db+feature 的 LLMClient / EmbeddingService，其 available_async 能
正确解析到「已启用模型 + 解密后的真实 key」并返回 True（与 settings 回退无关）。
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

from sqlalchemy import select

from app.core.crypto import encrypt_secret
from app.models.ai_center import AIModel, PromptTemplate, Provider, RoutingRule
from app.services.llm.client import LLMClient
from app.services.rag.embedder import EmbeddingService


class FakeScalars:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class FakeSession:
    _TABLE_MAP = {
        "routing_rules": "rules",
        "prompt_templates": "prompts",
        "ai_models": "models",
        "providers": "providers",
    }

    def __init__(self, model, provider, rule, prompt):
        self._models = {model.id: model}
        self._providers = {provider.id: provider}
        self._rules = [rule]
        self._prompts = [prompt]

    async def scalars(self, stmt):
        for c in getattr(stmt, "_raw_columns", ()):
            tname = getattr(c, "name", None)
            bucket = self._TABLE_MAP.get(tname)
            if bucket == "rules":
                return FakeScalars(self._rules)
            if bucket == "prompts":
                return FakeScalars(self._prompts)
            if bucket == "models":
                return FakeScalars(list(self._models.values()))
            if bucket == "providers":
                return FakeScalars(list(self._providers.values()))
        return FakeScalars([])

    async def get(self, cls, pk):
        if cls is AIModel:
            return self._models.get(pk)
        if cls is Provider:
            return self._providers.get(pk)
        return None

    async def flush(self):
        pass

    async def add(self, obj):
        pass


def main() -> None:
    mid, pid = uuid4(), uuid4()
    provider = Provider(
        id=pid, name="P", type="siliconflow",
        base_url="https://api.siliconflow.cn/v1",
        api_key=encrypt_secret("sk-real-xxxx"), enabled=True,
    )
    model = AIModel(
        id=mid, provider_id=pid, model_name="deepseek-chat",
        api_key=encrypt_secret("sk-real-xxxx"),
        base_url="https://api.siliconflow.cn/v1", is_enabled=True,
        capabilities={"chat": True, "embedding": True},
        temperature=0.3, top_p=1.0, timeout=60, max_tokens=None, embedding_dim=1024,
    )
    rule = RoutingRule(
        feature="legal_analysis", model_id=mid, enabled=True,
        strategy="balanced", auto_route=False, fallback_model_ids=[],
        prompt_template_key="legal_analysis",
    )
    prompt = PromptTemplate(key="legal_analysis", name="x", content="sys", enabled=True)

    db = FakeSession(model, provider, rule, prompt)

    llm = LLMClient(db=db, feature="legal_analysis")
    emb = EmbeddingService(db=db, feature="embedding")

    av_llm = asyncio.run(llm.available_async())
    av_emb = asyncio.run(emb.available_async())

    print("available_async(legal_analysis, db) =", av_llm)
    print("available_async(embedding, db)     =", av_emb)

    assert av_llm is True, "db 路由应解析到启用模型+真实 key → True"
    assert av_emb is True, "db 路由(embedding)应解析到启用模型+真实 key → True"

    # 反向：关闭规则 → 无路由 → 回退 settings（本环境 settings 无真 key）→ False
    rule.enabled = False
    db2 = FakeSession(model, provider, rule, prompt)
    llm_off = LLMClient(db=db2, feature="legal_analysis")
    assert asyncio.run(llm_off.available_async()) is False, "规则禁用应回退 settings → False"
    print("规则禁用 → available_async 回退 settings =", asyncio.run(llm_off.available_async()))

    print("\n[OK] DB 路由接线证明通过：调用方 feature 已驱动 AIManager 路由解析。")


if __name__ == "__main__":
    main()
