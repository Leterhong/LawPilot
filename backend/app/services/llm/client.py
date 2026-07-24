"""大模型客户端（LLM Client）—— AIManager 的薄适配层。

历史实现直接 ``AsyncOpenAI()`` 调用 ``settings`` 里的 LLM 配置；现重构为
:AIManager: 的适配层：所有真实的客户端构建、密钥解密、路由与 fallback 都交由
AIManager 处理，本类只保留对外接口（``complete`` / ``complete_json`` /
``available`` / ``model`` / ``reasoning_model``），**不再直接创建 OpenAI 客户端**。

零回归保证
----------
- 不传 ``db`` / ``feature`` 时（与历史调用方式一致），走 AIManager 的
  **settings 回退**路径，行为完全等同于旧实现；
- 传 ``db`` + ``feature`` 后（Step 5 迁移时），自动按 AI 能力中心的路由规则
  选模型，无需改动业务内部逻辑。

调用失败时 ``complete`` / ``complete_json`` 返回 ``None``，由调用方决定降级。
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.keys import is_real_key
from app.services.ai.manager import AIManager


class LLMClient:
    """OpenAI 兼容聊天补全客户端（经 AIManager 路由）。"""

    def __init__(
        self,
        db: AsyncSession | None = None,
        feature: str | None = None,
        capability: str = "chat",
    ) -> None:
        # db / feature 不传 → AIManager 使用 settings 回退（与旧行为一致）
        self._mgr = AIManager(db)
        self._feature = feature
        self._capability = capability

    # --------------------------- 同步接口（兼容旧代码） ---------------------------
    @property
    def available(self) -> bool:
        """是否配置了真实可用的 LLM 密钥（基于 settings，零回归）。

        迁移到 db 路由后，请改用 :meth:`available_async` 以感知中心的配置。
        """
        key = (settings.llm_api_key or "").strip()
        return is_real_key(key)

    @property
    def model(self) -> str:
        return settings.llm_model

    @property
    def reasoning_model(self) -> str:
        return settings.llm_reasoning_model

    async def available_async(self, feature: str | None = None, capability: str | None = None) -> bool:
        """异步感知当前路由是否可用（优先 feature，否则回退本实例配置）。"""
        return await self._mgr.available(
            feature if feature is not None else self._feature,
            capability if capability is not None else self._capability,
        )

    # --------------------------- 调用 ---------------------------
    async def complete(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> Optional[str]:
        """通用补全。失败返回 None。"""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self._mgr.chat(
            self._feature,
            messages,
            temperature=temperature if temperature is not None else settings.llm_temperature,
            max_tokens=max_tokens or settings.llm_max_tokens,
            json_mode=json_mode,
            capability=self._capability,
        )

    async def complete_json(
        self, prompt: str, *, system: Optional[str] = None, temperature: float = 0.2
    ) -> Optional[dict]:
        """返回 JSON 对象；解析失败返回 None。"""
        text = await self.complete(prompt, system=system, temperature=temperature, json_mode=True)
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 兼容模型在 JSON 外包裹多余文本的情况
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    return None
            return None
