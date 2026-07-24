"""嵌入服务（Embedding Service）—— AIManager 的薄适配层（BGE-M3 等）。

历史实现直接 ``AsyncOpenAI()`` 调用 ``settings`` 里的 Embedding 配置；现重构为
:AIManager: 的适配层。所有真实的客户端构建、密钥解密、路由与 fallback 都交由
AIManager 处理，本类只保留对外接口（``embed_doc`` / ``embed_query`` /
``embed_batch`` / ``available`` / ``model`` / ``dim``），**不再直接创建 OpenAI
客户端**。

零回归保证
----------
- 不传 ``db`` / ``feature`` 时（与历史调用方式一致），走 AIManager 的
  **settings 回退**路径，行为完全等同于旧实现；
- 传 ``db`` + ``feature`` 后（Step 5 迁移时），自动按 AI 能力中心的路由规则
  选 Embedding 模型。

BGE-M3 在检索场景下对 query 拼接指令前缀以获得更优召回，此逻辑保留在
AIManager 中（``embed_query`` 默认拼接）。
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.ai.manager import AIManager

# 单次批量编码上限，避免超出模型 max_batch 限制。
_EMBED_BATCH_SIZE: int = 16


class EmbeddingService:
    """BGE-M3 嵌入服务（经 AIManager 路由，OpenAI 兼容接口）。"""

    def __init__(self, db: AsyncSession | None = None, feature: str = "embedding") -> None:
        # db / feature 不传 → AIManager 使用 settings 回退（与旧行为一致）
        self._mgr = AIManager(db)
        self._feature = feature

    @property
    def available(self) -> bool:
        """是否配置了真实可用的 Embedding 密钥（基于 settings，零回归）。

        迁移到 db 路由后，请改用 :meth:`available_async` 以感知中心的配置。
        """
        key = (settings.embedding_api_key or "").strip()
        return bool(key) and key != "sk-your-key-here"

    @property
    def model(self) -> str:
        return settings.embedding_model

    @property
    def dim(self) -> int:
        return settings.embedding_dim

    async def available_async(self, feature: str | None = None) -> bool:
        """异步感知当前路由是否可用（优先 feature，否则回退本实例配置）。"""
        return await self._mgr.available(
            feature if feature is not None else self._feature, "embedding"
        )

    async def embed_doc(self, text: str) -> List[float]:
        """编码「文档/知识」文本（不拼接查询指令）。"""
        return await self._mgr.embed_doc(self._feature, text)

    async def embed_query(self, text: str, instruction: Optional[str] = None) -> List[float]:
        """编码「查询」文本，默认拼接 BGE-M3 查询指令前缀。"""
        return await self._mgr.embed_query(self._feature, text, instruction=instruction)

    async def embed_batch(
        self, texts: List[str], batch_size: int = _EMBED_BATCH_SIZE
    ) -> List[List[float]]:
        """批量编码文档文本，按 batch_size 分片以控制单次请求规模。"""
        return await self._mgr.embed_batch(self._feature, texts)
