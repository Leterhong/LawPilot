"""AI 能力中心业务逻辑。

职责：
- Provider / AIModel / RoutingRule / PromptTemplate 的增删改查
- API Key 加密存储、脱敏回显（明文不落库、不暴露）
- ``test_connection`` 真实调用 Provider（Chat/Embedding/Vision/Streaming）
- Token 统计、调用日志、模型健康检测（手动触发，后台定时见后续步骤）
"""
from __future__ import annotations

import time
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import httpx
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import decrypt_secret, encrypt_secret, mask_secret
from app.core.keys import is_real_key
from app.models.ai_center import (
    AIModel,
    ModelHealth,
    ModelLog,
    ModelUsage,
    PromptTemplate,
    PromptVersion,
    Provider,
    RoutingRule,
)
from app.models.user import User
from app.schemas.ai_center import (
    AIModelCreate,
    AIModelOut,
    AIModelUpdate,
    ModelHealthOut,
    ModelLogOut,
    ModelUsageRow,
    PromptTemplateCreate,
    PromptTemplateOut,
    PromptTemplateUpdate,
    PromptVersionOut,
    ProviderCreate,
    ProviderOut,
    ProviderUpdate,
    RoutingRuleCreate,
    RoutingRuleOut,
    RoutingRuleUpdate,
    TestConnectionRequest,
    TestConnectionResult,
)

_ONE_PX_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)


# ===========================================================================
# Service
# ===========================================================================
class AICenterService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------------- Provider ----------------------
    async def list_providers(self) -> list[ProviderOut]:
        rows = (await self.db.scalars(select(Provider).order_by(Provider.name))).all()
        return [
            ProviderOut(
                **{k: v for k, v in _orm_to_dict(r).items() if k != "api_key"},
                api_key=mask_secret(decrypt_secret(r.api_key)),
            )
            for r in rows
        ]

    async def create_provider(self, data: ProviderCreate) -> ProviderOut:
        obj = Provider(
            name=data.name,
            type=data.type,
            base_url=data.base_url,
            api_key=encrypt_secret(data.api_key) if data.api_key else None,
            enabled=data.enabled,
            description=data.description,
        )
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return await self._provider_out(obj)

    async def update_provider(self, pid: UUID, data: ProviderUpdate) -> ProviderOut | None:
        obj = await self.db.get(Provider, pid)
        if obj is None:
            return None
        if data.name is not None:
            obj.name = data.name
        if data.type is not None:
            obj.type = data.type
        if data.base_url is not None:
            obj.base_url = data.base_url
        if data.api_key is not None and data.api_key != "":
            obj.api_key = encrypt_secret(data.api_key)
        if data.enabled is not None:
            obj.enabled = data.enabled
        if data.description is not None:
            obj.description = data.description
        await self.db.commit()
        await self.db.refresh(obj)
        return await self._provider_out(obj)

    async def delete_provider(self, pid: UUID) -> bool:
        obj = await self.db.get(Provider, pid)
        if obj is None:
            return False
        # 关联模型设为独立（provider_id -> NULL），不级联删除模型
        models = (await self.db.scalars(select(AIModel).where(AIModel.provider_id == pid))).all()
        for m in models:
            m.provider_id = None
        await self.db.delete(obj)
        await self.db.commit()
        return True

    # ---------------------- 全局 AI 配置状态（供前端门控） ----------------------
    async def get_ai_status(self) -> dict:
        """返回全局是否已配置真实可用的模型。

        供前端判断「是否展示 AI 分析能力」。判定逻辑：
        - 任一 **启用** 的 Provider 持有真实 Key → 已配置；
        - 任一 **启用** 的模型持有真实 Key，或其所属 Provider 持有真实 Key → 已配置；
        - 或在 ``settings`` 里配置了真实 ``llm_api_key`` / ``embedding_api_key`` → 已配置。

        只返回布尔 / 计数，不泄露任何密钥明文。
        """
        provider_count = 0
        model_count = 0
        configured = False

        providers = (
            await self.db.scalars(select(Provider).where(Provider.enabled == True))  # noqa: E712
        ).all()
        provider_real: dict[str, bool] = {}
        for p in providers:
            if is_real_key(decrypt_secret(p.api_key)):
                configured = True
                provider_count += 1
                provider_real[str(p.id)] = True
            else:
                provider_real[str(p.id)] = False

        models = (
            await self.db.scalars(select(AIModel).where(AIModel.is_enabled == True))  # noqa: E712
        ).all()
        for m in models:
            own_key = is_real_key(decrypt_secret(m.api_key))
            inherited = bool(m.provider_id) and provider_real.get(str(m.provider_id), False)
            if own_key or inherited:
                configured = True
                model_count += 1

        if is_real_key(settings.llm_api_key) or is_real_key(settings.embedding_api_key):
            configured = True

        return {
            "ai_configured": configured,
            "provider_count": provider_count,
            "model_count": model_count,
        }

    async def _provider_out(self, obj: Provider) -> ProviderOut:
        return ProviderOut(
            id=obj.id,
            name=obj.name,
            type=obj.type,
            base_url=obj.base_url,
            api_key=mask_secret(decrypt_secret(obj.api_key)),
            enabled=obj.enabled,
            description=obj.description,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )

    # ---------------------- AIModel ----------------------
    async def list_models(self) -> list[AIModelOut]:
        rows = (await self.db.scalars(select(AIModel).order_by(AIModel.is_default.desc(), AIModel.name))).all()
        provider_names = await self._provider_name_map()
        out = []
        for r in rows:
            out.append(await self._model_out(r, provider_names))
        return out

    async def create_model(self, data: AIModelCreate) -> AIModelOut:
        provider_type = data.provider_type
        if data.provider_id is not None and not provider_type:
            p = await self.db.get(Provider, data.provider_id)
            provider_type = p.type if p else None
        if data.is_default:
            await self._clear_defaults()
        obj = AIModel(
            name=data.name,
            provider_id=data.provider_id,
            provider_type=provider_type,
            api_key=encrypt_secret(data.api_key) if data.api_key else None,
            base_url=data.base_url,
            model_name=data.model_name,
            embedding_model=data.embedding_model,
            vision_model=data.vision_model,
            reranker_model=data.reranker_model,
            embedding_dim=data.embedding_dim,
            temperature=data.temperature,
            top_p=data.top_p,
            timeout=data.timeout,
            max_tokens=data.max_tokens,
            is_default=data.is_default,
            is_enabled=data.is_enabled,
            capabilities=data.capabilities or _default_capabilities(),
            advanced=data.advanced or _default_advanced(),
        )
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return await self._model_out(obj)

    async def update_model(self, mid: UUID, data: AIModelUpdate) -> AIModelOut | None:
        obj = await self.db.get(AIModel, mid)
        if obj is None:
            return None
        if data.name is not None:
            obj.name = data.name
        if data.provider_id is not None:
            obj.provider_id = data.provider_id
        if data.provider_type is not None:
            obj.provider_type = data.provider_type
        elif data.provider_id is not None and obj.provider_type is None:
            p = await self.db.get(Provider, data.provider_id)
            obj.provider_type = p.type if p else None
        if data.api_key is not None and data.api_key != "":
            obj.api_key = encrypt_secret(data.api_key)
        if data.base_url is not None:
            obj.base_url = data.base_url
        if data.model_name is not None:
            obj.model_name = data.model_name
        if data.embedding_model is not None:
            obj.embedding_model = data.embedding_model
        if data.vision_model is not None:
            obj.vision_model = data.vision_model
        if data.reranker_model is not None:
            obj.reranker_model = data.reranker_model
        if data.embedding_dim is not None:
            obj.embedding_dim = data.embedding_dim
        if data.temperature is not None:
            obj.temperature = data.temperature
        if data.top_p is not None:
            obj.top_p = data.top_p
        if data.timeout is not None:
            obj.timeout = data.timeout
        if data.max_tokens is not None:
            obj.max_tokens = data.max_tokens
        if data.is_default is not None and data.is_default:
            await self._clear_defaults(except_id=mid)
            obj.is_default = True
        if data.is_enabled is not None:
            obj.is_enabled = data.is_enabled
        if data.capabilities is not None:
            obj.capabilities = data.capabilities
        if data.advanced is not None:
            obj.advanced = data.advanced
        await self.db.commit()
        await self.db.refresh(obj)
        return await self._model_out(obj)

    async def delete_model(self, mid: UUID) -> bool:
        obj = await self.db.get(AIModel, mid)
        if obj is None:
            return False
        await self.db.delete(obj)
        await self.db.commit()
        return True

    async def _clear_defaults(self, except_id: UUID | None = None) -> None:
        stmt = select(AIModel).where(AIModel.is_default == True)  # noqa: E712
        for m in (await self.db.scalars(stmt)).all():
            if except_id is not None and m.id == except_id:
                continue
            m.is_default = False

    async def _model_out(self, obj: AIModel, provider_names: dict | None = None) -> AIModelOut:
        if provider_names is None:
            provider_names = await self._provider_name_map()
        provider_name = provider_names.get(str(obj.provider_id)) if obj.provider_id else None
        return AIModelOut(
            id=obj.id,
            name=obj.name,
            provider_id=obj.provider_id,
            provider_name=provider_name,
            provider_type=obj.provider_type,
            api_key=mask_secret(decrypt_secret(obj.api_key)),
            base_url=obj.base_url,
            model_name=obj.model_name,
            embedding_model=obj.embedding_model,
            vision_model=obj.vision_model,
            reranker_model=obj.reranker_model,
            embedding_dim=obj.embedding_dim,
            temperature=obj.temperature,
            top_p=obj.top_p,
            timeout=obj.timeout,
            max_tokens=obj.max_tokens,
            is_default=obj.is_default,
            is_enabled=obj.is_enabled,
            capabilities=obj.capabilities or _default_capabilities(),
            advanced=obj.advanced or _default_advanced(),
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )

    async def _provider_name_map(self) -> dict:
        rows = (await self.db.scalars(select(Provider))).all()
        return {str(p.id): p.name for p in rows}

    # ---------------------- Routing ----------------------
    async def list_routing(self) -> list[RoutingRuleOut]:
        rows = (
            await self.db.scalars(select(RoutingRule).order_by(RoutingRule.priority, RoutingRule.feature))
        ).all()
        model_names = await self._model_name_map()
        return [
            RoutingRuleOut(
                id=r.id,
                feature=r.feature,
                model_id=r.model_id,
                model_name=model_names.get(str(r.model_id)),
                fallback_model_ids=r.fallback_model_ids,
                strategy=r.strategy,
                auto_route=r.auto_route,
                prompt_template_key=r.prompt_template_key,
                priority=r.priority,
                enabled=r.enabled,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    async def create_routing(self, data: RoutingRuleCreate) -> RoutingRuleOut:
        obj = RoutingRule(
            feature=data.feature,
            model_id=data.model_id,
            fallback_model_ids=data.fallback_model_ids,
            strategy=data.strategy,
            auto_route=data.auto_route,
            prompt_template_key=data.prompt_template_key,
            priority=data.priority,
            enabled=data.enabled,
        )
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return await self._routing_out(obj)

    async def update_routing(self, rid: UUID, data: RoutingRuleUpdate) -> RoutingRuleOut | None:
        obj = await self.db.get(RoutingRule, rid)
        if obj is None:
            return None
        if data.feature is not None:
            obj.feature = data.feature
        if data.model_id is not None:
            obj.model_id = data.model_id
        if data.fallback_model_ids is not None:
            obj.fallback_model_ids = data.fallback_model_ids
        if data.strategy is not None:
            obj.strategy = data.strategy
        if data.auto_route is not None:
            obj.auto_route = data.auto_route
        if data.prompt_template_key is not None:
            obj.prompt_template_key = data.prompt_template_key
        if data.priority is not None:
            obj.priority = data.priority
        if data.enabled is not None:
            obj.enabled = data.enabled
        await self.db.commit()
        await self.db.refresh(obj)
        return await self._routing_out(obj)

    async def _routing_out(self, obj: RoutingRule) -> RoutingRuleOut:
        model_names = await self._model_name_map()
        return RoutingRuleOut(
            id=obj.id,
            feature=obj.feature,
            model_id=obj.model_id,
            model_name=model_names.get(str(obj.model_id)),
            fallback_model_ids=obj.fallback_model_ids,
            strategy=obj.strategy,
            auto_route=obj.auto_route,
            prompt_template_key=obj.prompt_template_key,
            priority=obj.priority,
            enabled=obj.enabled,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )

    async def _model_name_map(self) -> dict:
        rows = (await self.db.scalars(select(AIModel))).all()
        return {str(m.id): m.name for m in rows}

    # ---------------------- Prompt ----------------------
    async def list_prompts(self) -> list[PromptTemplateOut]:
        rows = (await self.db.scalars(select(PromptTemplate).order_by(PromptTemplate.key))).all()
        model_names = await self._model_name_map()
        return [
            PromptTemplateOut(
                id=p.id,
                key=p.key,
                name=p.name,
                content=p.content,
                variables=p.variables,
                enabled=p.enabled,
                current_version=p.current_version,
                model_id=p.model_id,
                model_name=model_names.get(str(p.model_id)) if p.model_id else None,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in rows
        ]

    async def create_prompt(self, data: PromptTemplateCreate, user: User | None = None) -> PromptTemplateOut:
        obj = PromptTemplate(
            key=data.key,
            name=data.name,
            content=data.content,
            variables=data.variables,
            enabled=data.enabled,
            current_version=1,
            model_id=data.model_id,
        )
        self.db.add(obj)
        await self.db.flush()
        # 初始版本
        self.db.add(
            PromptVersion(
                template_id=obj.id,
                version=1,
                content=data.content,
                variables=data.variables,
                note="初始版本",
                created_by=user.id if user else None,
            )
        )
        await self.db.commit()
        await self.db.refresh(obj)
        return await self._prompt_out(obj)

    async def update_prompt(self, pid: UUID, data: PromptTemplateUpdate, user: User | None = None) -> PromptTemplateOut | None:
        obj = await self.db.get(PromptTemplate, pid)
        if obj is None:
            return None
        if data.key is not None:
            obj.key = data.key
        if data.name is not None:
            obj.name = data.name
        if data.enabled is not None:
            obj.enabled = data.enabled
        if data.model_id is not None:
            obj.model_id = data.model_id
        if data.variables is not None:
            obj.variables = data.variables
        # 内容变更 -> 新增版本
        if data.content is not None and data.content != obj.content:
            obj.current_version += 1
            self.db.add(
                PromptVersion(
                    template_id=obj.id,
                    version=obj.current_version,
                    content=data.content,
                    variables=obj.variables,
                    note=f"更新至 v{obj.current_version}",
                    created_by=user.id if user else None,
                )
            )
            obj.content = data.content
        await self.db.commit()
        await self.db.refresh(obj)
        return await self._prompt_out(obj)

    async def delete_prompt(self, pid: UUID) -> bool:
        obj = await self.db.get(PromptTemplate, pid)
        if obj is None:
            return False
        await self.db.delete(obj)
        await self.db.commit()
        return True

    async def list_prompt_versions(self, pid: UUID) -> list[PromptVersionOut]:
        rows = (
            await self.db.scalars(
                select(PromptVersion)
                .where(PromptVersion.template_id == pid)
                .order_by(desc(PromptVersion.version))
            )
        ).all()
        return [
            PromptVersionOut(
                id=v.id,
                template_id=v.template_id,
                version=v.version,
                content=v.content,
                variables=v.variables,
                note=v.note,
                created_by=v.created_by,
                created_at=v.created_at,
            )
            for v in rows
        ]

    async def _prompt_out(self, obj: PromptTemplate) -> PromptTemplateOut:
        model_names = await self._model_name_map()
        return PromptTemplateOut(
            id=obj.id,
            key=obj.key,
            name=obj.name,
            content=obj.content,
            variables=obj.variables,
            enabled=obj.enabled,
            current_version=obj.current_version,
            model_id=obj.model_id,
            model_name=model_names.get(str(obj.model_id)) if obj.model_id else None,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )

    # ---------------------- 测试连接（真实调用） ----------------------
    async def test_connection(self, req: TestConnectionRequest) -> TestConnectionResult:
        provider_type, base_url, api_key, model_name = await self._resolve_test_config(req)
        if not base_url or not model_name:
            return TestConnectionResult(
                status="fail",
                capability=req.capability,
                model=model_name,
                provider_type=provider_type,
                error="缺少 base_url 或 model_name，无法发起测试",
            )
        ok, latency, error, detected = await self._probe(
            base_url, api_key, model_name, req.capability
        )
        # 写一条 ModelLog（测试连接也计入日志中心）
        self.db.add(
            ModelLog(
                model_id=req.model_id,
                capability=req.capability,
                status="success" if ok else "error",
                latency_ms=latency or 0,
                error_text=error,
                request_text=f"[test] {req.capability} -> {model_name}",
                response_text=None if ok else (error or "")[:500],
            )
        )
        await self.db.commit()
        return TestConnectionResult(
            status="ok" if ok else "fail",
            capability=req.capability,
            latency_ms=latency,
            capabilities_detected=detected,
            model=model_name,
            provider_type=provider_type,
            error=error,
        )

    async def _resolve_test_config(self, req: TestConnectionRequest):
        if req.model_id is not None:
            m = await self.db.get(AIModel, req.model_id)
            if m is None:
                return None, None, None, None
            provider_type = m.provider_type
            base_url = m.base_url
            api_key = decrypt_secret(m.api_key)
            model_name = m.model_name
            if m.provider_id is not None and (not base_url or not api_key):
                p = await self.db.get(Provider, m.provider_id)
                if p:
                    provider_type = provider_type or p.type
                    base_url = base_url or p.base_url
                    api_key = api_key or decrypt_secret(p.api_key)
            return provider_type, base_url, api_key, model_name
        # 内联配置
        return req.provider_type, req.base_url, req.api_key, req.model_name

    async def _probe(
        self, base_url: str, api_key: str | None, model_name: str, capability: str
    ) -> tuple[bool, int | None, str | None, list[str]]:
        base = base_url.rstrip("/")
        headers = {
            "Authorization": f"Bearer {api_key or ''}",
            "Content-Type": "application/json",
        }
        detected: list[str] = []
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if capability in ("chat", "vision", "streaming", "json_mode", "function_calling"):
                    payload: dict = {
                        "model": model_name,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 8,
                    }
                    if capability == "vision":
                        payload["messages"] = [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "ping"},
                                    {"type": "image_url", "image_url": {"url": _ONE_PX_PNG}},
                                ],
                            }
                        ]
                    if capability == "streaming":
                        async with client.stream(
                            "POST", f"{base}/chat/completions", headers=headers, json=payload
                        ) as resp:
                            ok = resp.status_code == 200
                            async for _ in resp.aiter_lines():
                                break
                    else:
                        resp = await client.post(
                            f"{base}/chat/completions", headers=headers, json=payload
                        )
                        ok = resp.status_code == 200
                    if ok:
                        detected.append(capability)
                elif capability == "embedding":
                    resp = await client.post(
                        f"{base}/embeddings",
                        headers=headers,
                        json={"model": model_name, "input": "ping"},
                    )
                    ok = resp.status_code == 200
                    if ok:
                        detected.append("embedding")
                else:
                    return False, None, f"不支持的 capability: {capability}", detected
            latency = int((time.monotonic() - t0) * 1000)
            return ok, latency, (None if ok else f"HTTP {resp.status_code}: {_trunc(resp.text, 200)}"), detected
        except Exception as exc:  # noqa: BLE001
            latency = int((time.monotonic() - t0) * 1000)
            return False, latency, _trunc(str(exc), 300), detected

    # ---------------------- 健康检测（手动触发） ----------------------
    async def check_health(self, mid: UUID) -> ModelHealthOut | None:
        m = await self.db.get(AIModel, mid)
        if m is None:
            return None
        provider_type, base_url, api_key, model_name = await self._resolve_test_config(
            TestConnectionRequest(model_id=mid)
        )
        caps = m.capabilities or _default_capabilities()
        results = {}
        latency_sum = 0
        any_ok = False
        for cap in ("chat", "vision", "embedding", "streaming", "json_mode", "function_calling", "web_search"):
            if not caps.get(cap):
                continue
            ok, lat, err, _ = await self._probe(base_url or "", api_key, model_name or "", cap)
            results[f"{cap}_ok"] = ok
            if lat:
                latency_sum += lat
            any_ok = any_ok or ok
        status = "healthy" if any_ok else "down"
        rec = ModelHealth(
            model_id=mid,
            provider_id=m.provider_id,
            last_checked=datetime.utcnow(),
            chat_ok=results.get("chat_ok"),
            vision_ok=results.get("vision_ok"),
            embedding_ok=results.get("embedding_ok"),
            streaming_ok=results.get("streaming_ok"),
            json_ok=results.get("json_mode_ok"),
            function_calling_ok=results.get("function_calling_ok"),
            web_ok=results.get("web_search_ok"),
            status=status,
            latency_ms=latency_sum,
            error_text=None if any_ok else "所有已启用能力探测失败",
        )
        self.db.add(rec)
        await self.db.commit()
        await self.db.refresh(rec)
        return await self._health_out(rec)

    async def list_health(self) -> list[ModelHealthOut]:
        # 每个 model 取最新一条
        subq = (
            select(ModelHealth.model_id, func.max(ModelHealth.created_at).label("mx"))
            .group_by(ModelHealth.model_id)
            .subquery()
        )
        rows = (
            await self.db.scalars(
                select(ModelHealth)
                .join(
                    subq,
                    (ModelHealth.model_id == subq.c.model_id)
                    & (ModelHealth.created_at == subq.c.mx),
                )
                .order_by(ModelHealth.model_id)
            )
        ).all()
        model_names = await self._model_name_map()
        return [await self._health_out(r, model_names) for r in rows]

    async def _health_out(self, obj: ModelHealth, model_names: dict | None = None) -> ModelHealthOut:
        if model_names is None:
            model_names = await self._model_name_map()
        return ModelHealthOut(
            id=obj.id,
            model_id=obj.model_id,
            model_name=model_names.get(str(obj.model_id)),
            provider_id=obj.provider_id,
            last_checked=obj.last_checked,
            chat_ok=obj.chat_ok,
            vision_ok=obj.vision_ok,
            embedding_ok=obj.embedding_ok,
            streaming_ok=obj.streaming_ok,
            json_ok=obj.json_ok,
            function_calling_ok=obj.function_calling_ok,
            web_ok=obj.web_ok,
            status=obj.status,
            latency_ms=obj.latency_ms,
            error_text=obj.error_text,
            created_at=obj.created_at,
        )

    # ---------------------- 统计 / 日志 ----------------------
    async def get_statistics(self, days: int = 30) -> dict:
        since = date.today().replace(day=1)  # 简化：本月起
        rows = (
            await self.db.scalars(select(ModelUsage).where(ModelUsage.date >= since))
        ).all()
        model_names = await self._model_name_map()
        per_day: dict[str, ModelUsageRow] = {}
        per_model: dict[str, ModelUsageRow] = {}
        totals = {
            "tokens_in": 0,
            "tokens_out": 0,
            "cost": Decimal("0"),
            "calls": 0,
            "failures": 0,
        }
        for r in rows:
            dkey = r.date.isoformat()
            if dkey not in per_day:
                per_day[dkey] = ModelUsageRow(date=r.date, model_id=None, model_name="ALL")
            _add(per_day[dkey], r)
            mkey = str(r.model_id)
            if mkey not in per_model:
                per_model[mkey] = ModelUsageRow(
                    date=r.date, model_id=r.model_id, model_name=model_names.get(mkey)
                )
            _add(per_model[mkey], r)
            _add_totals(totals, r)
        for row in list(per_day.values()) + list(per_model.values()):
            row.failure_rate = round(row.failures / row.calls, 4) if row.calls else 0.0
        totals["failure_rate"] = round(totals["failures"] / totals["calls"], 4) if totals["calls"] else 0.0
        return {
            "per_day": sorted(per_day.values(), key=lambda x: x.date),
            "per_model": list(per_model.values()),
            "totals": totals,
            "range": {"from": since.isoformat(), "to": date.today().isoformat()},
        }

    async def list_logs(self, limit: int = 100, offset: int = 0, feature: str | None = None) -> tuple[list[ModelLogOut], int]:
        stmt = select(ModelLog)
        count_stmt = select(func.count()).select_from(ModelLog)
        if feature:
            stmt = stmt.where(ModelLog.feature == feature)
            count_stmt = count_stmt.where(ModelLog.feature == feature)
        total = (await self.db.scalar(count_stmt)) or 0
        rows = (
            await self.db.scalars(
                stmt.order_by(desc(ModelLog.created_at)).limit(limit).offset(offset)
            )
        ).all()
        model_names = await self._model_name_map()
        out = [
            ModelLogOut(
                id=log.id,
                model_id=log.model_id,
                model_name=model_names.get(str(log.model_id)) if log.model_id else None,
                provider_id=log.provider_id,
                user_id=log.user_id,
                feature=log.feature,
                endpoint=log.endpoint,
                capability=log.capability,
                tokens_in=log.tokens_in,
                tokens_out=log.tokens_out,
                cost=log.cost,
                latency_ms=log.latency_ms,
                status=log.status,
                error_text=log.error_text,
                created_at=log.created_at,
            )
            for log in rows
        ]
        return out, total


# ---------------------------------------------------------------------------
# 模块级辅助
# ---------------------------------------------------------------------------
def _default_capabilities() -> dict:
    return {
        "chat": True,
        "embedding": False,
        "vision": False,
        "streaming": True,
        "json_mode": True,
        "function_calling": True,
        "web_search": False,
        "reasoning": False,
    }


def _default_advanced() -> dict:
    return {"auto_retry": 3, "max_concurrency": 4, "rate_limit_rpm": 0, "rate_limit_tpm": 0}


def _orm_to_dict(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def _trunc(s: str, n: int) -> str:
    return s[:n] + ("…" if len(s) > n else "")


def _add(row: ModelUsageRow, r: ModelUsage) -> None:
    row.tokens_in += r.tokens_in
    row.tokens_out += r.tokens_out
    row.cost += r.cost
    row.calls += r.calls
    row.failures += r.failures
    row.avg_latency_ms = max(row.avg_latency_ms, r.avg_latency_ms)


def _add_totals(t: dict, r: ModelUsage) -> None:
    t["tokens_in"] += r.tokens_in
    t["tokens_out"] += r.tokens_out
    t["cost"] += r.cost
    t["calls"] += r.calls
    t["failures"] += r.failures
