"""AI 能力中心：统一 AI 调用管理器（AIManager）。

取代业务代码里散落的 ``AsyncOpenAI()`` / 各 Provider SDK 直连调用，成为
项目内**唯一**的模型调用入口（见「统一调用规范」）。

设计要点
--------
- **路由**：每个 AI 功能（``feature``，见 ``AI_FEATURES``）通过 ``routing_rules``
  映射到 具体的 Provider + 模型 + Prompt + fallback 链；
- **自动选路（auto_route）**：当规则开启 ``auto_route`` 时，在候选模型间按
  策略（lowest_cost / fastest / highest_quality / balanced / custom）择优；
- **降级**：主模型失败（网络抖动 / 限流 / 401）时沿 ``fallback_model_ids``
  链依次尝试；
- **零回归**：数据库为空 / 未配置路由规则时回退到 ``settings`` 里的旧配置
  （llm_* / embedding_* / rerank_*），现有业务开箱即用，无需任何改动；
- **可观测**：需要 db 会话时，调用明细写入 ``model_logs``、按天聚合到
  ``model_usage``；settings 回退模式（无 db）下不记录，行为保持旧样；
- **失败时行为**：``chat`` / ``vision`` / ``rerank`` 在失败时返回 ``None``
  或空结果（优雅降级，由调用方决定后续）；``embedding`` 在不可用时抛出，
  与历史 ``EmbeddingService`` 的契约一致（调用方均以 ``available`` 先行守卫）。

所有对外方法均不向上抛未捕获异常（``embedding`` 除外，因其调用方依赖异常
短路），避免单点故障拖垮整个流程。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

import httpx
from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.crypto import decrypt_secret
from app.core.keys import is_real_key
from app.models.ai_center import (
    AIModel,
    ModelHealth,
    ModelLog,
    ModelUsage,
    PromptTemplate,
    Provider,
    RoutingRule,
)

# BGE-M3 检索场景下对 query 的推荐指令前缀（与旧 EmbeddingService 一致）
BGE_M3_QUERY_INSTRUCTION: str = "为这个句子生成用于检索相关段落的表示："

# 单次批量编码上限，避免超出模型 max_batch 限制
_EMBED_BATCH_SIZE: int = 16

# ---------------------------------------------------------------------------
# 客户端缓存：跨请求复用 AsyncOpenAI 实例（按 base_url + api_key 维度）
# ---------------------------------------------------------------------------
_CLIENT_CACHE: dict[tuple[str, str], AsyncOpenAI] = {}


def _get_client(base_url: str, api_key: str | None, timeout: int) -> AsyncOpenAI:
    """按 (base_url, api_key) 复用 OpenAI 兼容客户端，避免每次调用都重建。"""
    key = (base_url, api_key or "")
    client = _CLIENT_CACHE.get(key)
    if client is None:
        client = AsyncOpenAI(base_url=base_url, api_key=api_key or "", timeout=timeout)
        _CLIENT_CACHE[key] = client
    return client


# ---------------------------------------------------------------------------
# 解析后的路由（一次调用所用的全部信息）
# ---------------------------------------------------------------------------
@dataclass
class ResolvedRoute:
    model_id: UUID | None
    provider_id: UUID | None
    model_name: str
    base_url: str
    api_key: str | None
    temperature: float
    max_tokens: int | None
    top_p: float
    timeout: int
    capabilities: dict
    system_prompt: str | None
    fallbacks: list["ResolvedRoute"] = field(default_factory=list)
    source: str = "settings"  # "db" | "settings"

    @property
    def has_key(self) -> bool:
        return bool(self.base_url) and is_real_key(self.api_key)


def _trunc(s: str, n: int) -> str:
    return s[:n] + ("…" if len(s) > n else "")


@dataclass
class ChatResult:
    """``chat_model`` 的详细返回（含 token / 延迟 / 错误），供 Playground 等需要指标的场景。"""

    content: str | None
    tokens_in: int
    tokens_out: int
    latency_ms: int
    model_name: str | None
    model_id: UUID | None
    provider_name: str | None
    error: str | None


def _settings_route(capability: str) -> ResolvedRoute:
    """无 db / 无路由规则时的回退：复用 settings 里的旧配置（零回归）。"""
    if capability == "embedding":
        return ResolvedRoute(
            model_id=None,
            provider_id=None,
            model_name=settings.embedding_model,
            base_url=settings.embedding_base_url,
            api_key=settings.embedding_api_key,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            top_p=1.0,
            timeout=60,
            capabilities={"embedding": True},
            system_prompt=None,
            source="settings",
        )
    if capability == "rerank":
        return ResolvedRoute(
            model_id=None,
            provider_id=None,
            model_name=settings.rerank_model,
            base_url=settings.rerank_base_url,
            api_key=settings.rerank_api_key,
            temperature=0.0,
            max_tokens=None,
            top_p=1.0,
            timeout=30,
            capabilities={"rerank": True},
            system_prompt=None,
            source="settings",
        )
    # chat / vision / 默认 → llm
    return ResolvedRoute(
        model_id=None,
        provider_id=None,
        model_name=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        top_p=1.0,
        timeout=60,
        capabilities={"chat": True, "vision": True, "json_mode": True},
        system_prompt=None,
        source="settings",
    )


class AIManager:
    """统一 AI 调用管理器。

    典型用法::

        mgr = AIManager(db)                       # db 可为 None（仅 settings 回退）
        text = await mgr.chat("legal_analysis", messages, json_mode=True)
        vec  = await mgr.embed_doc("embedding", text)
    """

    def __init__(self, db: AsyncSession | None = None) -> None:
        self.db = db
        self._health_cache: dict[UUID, ModelHealth] | None = None

    # ===================================================================
    # 公开调用方法
    # ===================================================================
    async def chat(
        self,
        feature: str | None,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
        capability: str = "chat",
        user_id: UUID | None = None,
    ) -> str | None:
        """聊天 / 通用补全。失败返回 ``None``（优雅降级）。"""
        route = await self._resolve(feature, capability)
        chain = [route] + route.fallbacks
        last_err: str | None = None
        for r in chain:
            if not r.has_key:
                last_err = "缺少 base_url / api_key，调用跳过"
                continue
            client = _get_client(r.base_url, r.api_key, r.timeout)
            try:
                content, tin, tout = await self._chat_once(
                    client, r, messages, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode
                )
                await self._log(r, feature, capability, messages, content, None, tin, tout, user_id)
                return content
            except Exception as exc:  # noqa: BLE001
                last_err = _trunc(str(exc), 300)
                continue
        await self._log(route, feature, capability, messages, None, last_err, 0, 0, user_id)
        return None

    async def chat_model(
        self,
        model_id: UUID,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
        capability: str = "chat",
        user_id: UUID | None = None,
    ) -> "ChatResult":
        """按指定 ``model_id`` 调用单个模型（用于 Playground 选模型测试/对比/评测）。

        不走 feature 路由；精确测试该模型。失败返回 ``ChatResult(content=None, error=...)``。
        """
        if self.db is None:
            return ChatResult(None, 0, 0, 0, None, model_id, None, "缺少 db 会话，无法解析模型")
        model = await self.db.get(AIModel, model_id)
        if model is None:
            return ChatResult(None, 0, 0, 0, None, model_id, None, "模型不存在")
        route = await self._route_for_model(model, capability, prompt_key=None)
        if route is None or not route.has_key:
            return ChatResult(
                None, 0, 0, 0, model.name, model_id, None,
                "模型未正确配置（缺少 base_url / api_key）",
            )
        provider_name = None
        if model.provider_id is not None:
            p = await self.db.get(Provider, model.provider_id)
            provider_name = p.name if p else None
        client = _get_client(route.base_url, route.api_key, route.timeout)
        t0 = time.monotonic()
        try:
            content, tin, tout = await self._chat_once(
                client, route, messages, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode
            )
            lat = int((time.monotonic() - t0) * 1000)
            await self._log(route, "playground", capability, messages, content, None, tin, tout, user_id, latency_ms=lat)
            return ChatResult(content, tin, tout, lat, route.model_name, model_id, provider_name, None)
        except Exception as exc:  # noqa: BLE001
            lat = int((time.monotonic() - t0) * 1000)
            await self._log(route, "playground", capability, messages, None, _trunc(str(exc), 300), 0, 0, user_id, latency_ms=lat)
            return ChatResult(None, 0, 0, lat, route.model_name, model_id, provider_name, _trunc(str(exc), 300))

    async def vision(
        self,
        feature: str | None,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        user_id: UUID | None = None,
    ) -> str | None:
        """视觉理解（messages 内已含 image_url 内容块）。失败返回 ``None``。"""
        return await self.chat(
            feature, messages, temperature=temperature, max_tokens=max_tokens, json_mode=False, capability="vision", user_id=user_id
        )

    async def embed_doc(self, feature: str | None, text: str, user_id: UUID | None = None) -> list[float]:
        """编码「文档/知识」文本（不拼接查询指令）。"""
        out = await self._embed(feature, [text], kind="doc", user_id=user_id)
        return out[0]

    async def embed_query(
        self, feature: str | None, text: str, instruction: str | None = None, user_id: UUID | None = None
    ) -> list[float]:
        """编码「查询」文本，默认拼接 BGE-M3 查询指令前缀。"""
        out = await self._embed(feature, [text], kind="query", instruction=instruction, user_id=user_id)
        return out[0]

    async def embed_batch(
        self, feature: str | None, texts: list[str], user_id: UUID | None = None
    ) -> list[list[float]]:
        """批量编码文档文本。"""
        return await self._embed(feature, texts, kind="doc", user_id=user_id)

    async def rerank(
        self,
        feature: str | None,
        query: str,
        documents: list[str],
        *,
        top_n: int | None = None,
        user_id: UUID | None = None,
    ) -> list[dict] | None:
        """调用 Cohere 兼容 /rerank 端点做精排。失败返回 ``None``。"""
        if not documents:
            return []
        route = await self._resolve(feature, "rerank")
        if not route.has_key or not route.model_name:
            return None
        # rerank 走标准 HTTP 接口，无需构造 OpenAI 客户端（历史上曾多造一个未使用的
        # 客户端对象，纯属开销，已移除）
        payload = {
            "model": route.model_name,
            "query": query,
            "documents": documents,
            "top_n": top_n or len(documents),
        }
        headers = {"Authorization": f"Bearer {route.api_key}"} if route.api_key else {}
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=route.timeout) as c:
                resp = await c.post(f"{route.base_url.rstrip('/')}/rerank", json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            results = data.get("results", [])
            await self._log(
                route, feature, "rerank", [{"query": query[:200]}],
                f"{len(results)} ranked", None, 0, 0, user_id,
                latency_ms=int((time.monotonic() - t0) * 1000),
            )
            return results
        except Exception as exc:  # noqa: BLE001
            await self._log(route, feature, "rerank", None, None, _trunc(str(exc), 300), 0, 0, user_id)
            return None

    async def available(self, feature: str | None = None, capability: str = "chat") -> bool:
        """该 feature/capability 是否已配置可用模型（需要 db 才能感知 db 路由）。"""
        route = await self._resolve(feature, capability)
        return route.has_key

    # ===================================================================
    # auto_route：按策略在候选模型间自动选路
    # ===================================================================
    async def auto_route(self, feature: str | None, capability: str = "chat") -> AIModel | None:
        """返回按策略选出的候选模型（供内部 _build_route_from_rule 使用）。

        策略：
        - fastest          → 取最近探测延迟最低且健康的模型
        - highest_quality  → 优先具备 reasoning 能力、其次 is_default
        - balanced         → 优先 healthy，其次 is_default
        - lowest_cost/custom→ 保持主模型优先（无成本字段时退化为 balanced）
        """
        rule = await self._rule_for(feature)
        if rule is None:
            return None
        cap_key = {
            "chat": "chat",
            "vision": "vision",
            "embedding": "embedding",
            "rerank": "rerank",
        }.get(capability, "chat")

        # 候选：主模型 + fallback + 所有 enabled 且具备该能力的模型
        candidates: list[AIModel] = []
        seen: set[UUID] = set()

        async def _add(m: AIModel | None) -> None:
            if m and m.is_enabled and m.id not in seen:
                seen.add(m.id)
                candidates.append(m)

        primary = await self.db.get(AIModel, rule.model_id) if self.db else None
        await _add(primary)
        if rule.fallback_model_ids:
            for fid in rule.fallback_model_ids:
                await _add(await self.db.get(AIModel, fid) if self.db else None)
        if self.db is not None:
            rows = (await self.db.scalars(select(AIModel).where(AIModel.is_enabled == True))).all()  # noqa: E712
            for m in rows:
                await _add(m)

        candidates = [m for m in candidates if (m.capabilities or {}).get(cap_key)]
        if not candidates:
            return None

        health = await self._latest_health_map()
        strategy = rule.strategy

        def _lat(m: AIModel) -> int:
            h = health.get(m.id)
            return h.latency_ms if (h and h.latency_ms) else 10**9

        if strategy == "fastest":
            candidates.sort(key=_lat)
        elif strategy == "highest_quality":
            candidates.sort(
                key=lambda m: (bool((m.capabilities or {}).get("reasoning")), bool(m.is_default)),
                reverse=True,
            )
        elif strategy in ("balanced", "lowest_cost", "custom"):
            candidates.sort(
                key=lambda m: (
                    health.get(m.id) is not None and health.get(m.id).status == "healthy",
                    bool(m.is_default),
                ),
                reverse=True,
            )
        return candidates[0]

    # ===================================================================
    # 内部：路由解析
    # ===================================================================
    async def _resolve(self, feature: str | None, capability: str) -> ResolvedRoute:
        """解析出本次调用使用的路由。无 db 或无规则时回退 settings。"""
        if self.db is None:
            return _settings_route(capability)
        if feature:
            rule = await self._rule_for(feature)
            if rule is not None and rule.enabled:
                route = await self._build_route_from_rule(rule, capability)
                if route is not None:
                    return route
        return _settings_route(capability)

    async def _rule_for(self, feature: str | None) -> RoutingRule | None:
        if feature is None:
            return None
        return (
            await self.db.scalars(
                select(RoutingRule).where(RoutingRule.feature == feature)
            )
        ).first()

    async def _build_route_from_rule(self, rule: RoutingRule, capability: str) -> ResolvedRoute | None:
        model = await self.db.get(AIModel, rule.model_id)
        if model is None or not model.is_enabled:
            return None
        chosen = model
        if rule.auto_route:
            auto = await self.auto_route(rule.feature, capability)
            chosen = auto or model
        route = await self._route_for_model(chosen, capability, prompt_key=rule.prompt_template_key)
        if route is None:
            return None
        # fallback 链
        fallbacks: list[ResolvedRoute] = []
        if rule.fallback_model_ids:
            for fid in rule.fallback_model_ids:
                fm = await self.db.get(AIModel, fid)
                if fm and fm.is_enabled and fm.id != chosen.id:
                    fr = await self._route_for_model(fm, capability, prompt_key=None)
                    if fr is not None:
                        fallbacks.append(fr)
        route.fallbacks = fallbacks
        route.source = "db"
        return route

    async def _route_for_model(
        self, model: AIModel, capability: str, prompt_key: str | None
    ) -> ResolvedRoute | None:
        base_url = model.base_url
        api_key = decrypt_secret(model.api_key)
        provider_type = model.provider_type
        if model.provider_id is not None:
            p = await self.db.get(Provider, model.provider_id)
            if p is not None:
                provider_type = provider_type or p.type
                base_url = base_url or p.base_url
                api_key = api_key or decrypt_secret(p.api_key)
        if not base_url:
            return None
        # 按能力取实际模型名
        model_name = model.model_name
        if capability == "embedding" and model.embedding_model:
            model_name = model.embedding_model
        elif capability == "vision" and model.vision_model:
            model_name = model.vision_model
        elif capability == "rerank" and model.reranker_model:
            model_name = model.reranker_model
        # Prompt 模板（仅主模型套用，fallback 不再叠加）
        system_prompt: str | None = None
        if prompt_key:
            pt = (
                await self.db.scalars(select(PromptTemplate).where(PromptTemplate.key == prompt_key))
            ).first()
            if pt is not None:
                system_prompt = pt.content
        return ResolvedRoute(
            model_id=model.id,
            provider_id=model.provider_id,
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            temperature=model.temperature,
            max_tokens=model.max_tokens,
            top_p=model.top_p,
            timeout=model.timeout,
            capabilities=model.capabilities or {},
            system_prompt=system_prompt,
            source="db",
        )

    async def _latest_health_map(self) -> dict[UUID, ModelHealth]:
        if self._health_cache is not None:
            return self._health_cache
        self._health_cache = {}
        if self.db is None:
            return self._health_cache
        subq = (
            select(ModelHealth.model_id, func.max(ModelHealth.created_at).label("mx"))
            .group_by(ModelHealth.model_id)
            .subquery()
        )
        rows = (
            await self.db.scalars(
                select(ModelHealth).join(
                    subq,
                    (ModelHealth.model_id == subq.c.model_id)
                    & (ModelHealth.created_at == subq.c.mx),
                )
            )
        ).all()
        self._health_cache = {r.model_id: r for r in rows}
        return self._health_cache

    # ===================================================================
    # 内部：实际调用（带重试）
    # ===================================================================
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((APIConnectionError, APITimeoutError, RateLimitError)),
        reraise=True,
    )
    async def _chat_once(
        self,
        client: AsyncOpenAI,
        route: ResolvedRoute,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None,
        max_tokens: int | None,
        json_mode: bool,
    ) -> tuple[str, int, int]:
        # Prompt 模板：仅在未显式给出 system 时套用路由绑定的 system
        msgs = list(messages)
        if route.system_prompt is not None:
            has_system = any(m.get("role") == "system" for m in msgs)
            if not has_system:
                msgs.insert(0, {"role": "system", "content": route.system_prompt})
        use_json = bool(json_mode) and bool(route.capabilities.get("json_mode", True))
        resp = await client.chat.completions.create(
            model=route.model_name,
            messages=msgs,
            temperature=temperature if temperature is not None else route.temperature,
            max_tokens=max_tokens or route.max_tokens,
            response_format={"type": "json_object"} if use_json else None,
        )
        content = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        tin = int(getattr(usage, "prompt_tokens", 0) or 0)
        tout = int(getattr(usage, "completion_tokens", 0) or 0)
        return content, tin, tout

    async def _embed(
        self,
        feature: str | None,
        texts: list[str],
        *,
        kind: str,
        instruction: str | None = None,
        user_id: UUID | None = None,
    ) -> list[list[float]]:
        route = await self._resolve(feature, "embedding")
        if not route.has_key:
            raise RuntimeError("Embedding 未配置：缺少 base_url / api_key（请检查 settings 或 AI 能力中心路由）")
        # 查询场景拼接 BGE-M3 指令前缀（与历史行为一致）
        cleaned: list[str] = []
        for t in texts:
            t = (t or "").strip()
            if not t:
                continue
            if kind == "query":
                prefix = BGE_M3_QUERY_INSTRUCTION if instruction is None else instruction
                t = f"{prefix}{t}" if prefix else t
            cleaned.append(t)
        if not cleaned:
            return []
        client = _get_client(route.base_url, route.api_key, route.timeout)
        out: list[list[float]] = []
        t0 = time.monotonic()
        try:
            for i in range(0, len(cleaned), _EMBED_BATCH_SIZE):
                batch = cleaned[i : i + _EMBED_BATCH_SIZE]
                resp = await client.embeddings.create(model=route.model_name, input=batch)
                ordered = sorted(resp.data, key=lambda d: d.index)
                out.extend([list(d.embedding) for d in ordered])
            await self._log(
                route, feature, "embedding", [{"input": t[:120]} for t in cleaned],
                f"{len(out)} vecs", None, 0, 0, user_id,
                latency_ms=int((time.monotonic() - t0) * 1000),
            )
            return out
        except Exception as exc:  # noqa: BLE001
            await self._log(route, feature, "embedding", None, None, _trunc(str(exc), 300), 0, 0, user_id)
            raise

    # ===================================================================
    # 内部：日志 / 统计
    # ===================================================================
    async def _log(
        self,
        route: ResolvedRoute,
        feature: str | None,
        capability: str,
        messages: Any,
        response_text: str | None,
        error: str | None,
        tokens_in: int,
        tokens_out: int,
        user_id: UUID | None,
        latency_ms: int = 0,
    ) -> None:
        if self.db is None:
            return
        try:
            req_text: str | None = None
            if messages:
                try:
                    req_text = json.dumps(messages, ensure_ascii=False)[:2000]
                except Exception:  # noqa: BLE001
                    req_text = str(messages)[:2000]
            self.db.add(
                ModelLog(
                    model_id=route.model_id,
                    provider_id=route.provider_id,
                    user_id=user_id,
                    feature=feature,
                    capability=capability,
                    endpoint="chat/completions" if capability != "embedding" else "embeddings",
                    request_text=req_text,
                    response_text=(response_text or "")[:2000] if response_text else None,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    latency_ms=latency_ms,
                    status="success" if error is None else "error",
                    error_text=error,
                )
            )
            await self.db.flush()
            if error is None:
                await self._upsert_usage(route, feature, tokens_in, tokens_out, user_id)
        except Exception:  # noqa: BLE001
            # 日志失败绝不影响主流程
            pass

    async def _upsert_usage(
        self,
        route: ResolvedRoute,
        feature: str | None,
        tokens_in: int,
        tokens_out: int,
        user_id: UUID | None,
    ) -> None:
        if self.db is None:
            return
        today = date.today()
        existing = (
            await self.db.scalars(
                select(ModelUsage).where(
                    ModelUsage.date == today,
                    ModelUsage.model_id == route.model_id,
                    ModelUsage.user_id == user_id,
                )
            )
        ).first()
        if existing is not None:
            existing.tokens_in += tokens_in
            existing.tokens_out += tokens_out
            existing.calls += 1
        else:
            self.db.add(
                ModelUsage(
                    date=today,
                    model_id=route.model_id,
                    provider_id=route.provider_id,
                    user_id=user_id,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    calls=1,
                )
            )
        await self.db.flush()
