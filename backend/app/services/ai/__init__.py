"""AI 能力中心：统一 AI 调用层。

对外暴露 :class:`AIManager`，作为项目内**唯一**的模型调用入口
（统一调用规范：禁止业务代码直接 ``AsyncOpenAI()`` / 各 Provider SDK）。
"""
from __future__ import annotations

from app.services.ai.manager import AIManager, ResolvedRoute

__all__ = ["AIManager", "ResolvedRoute"]
