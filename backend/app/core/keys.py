"""API Key 真实性判定。

区分「真实用户 Key」与「占位 / 演示 Key」。

为什么需要它：``scripts/seed_ai_center.py`` 历史上会植入演示 Key
``sk-demo-placeholder``，而旧的 ``has_key`` 判断只排除了默认占位
``sk-your-key-here``，导致系统「以为」已配置好模型 → 实际请求必然 401 →
各业务模块显示「演示降级」空面板，给用户「分析跑过但没结果」的错觉。

统一用 :func:`is_real_key` 过滤所有占位 / 演示 Key，是消除「虚拟数据感」的根因修复。
"""
from __future__ import annotations

# 这些前缀一律视为「未配置」，避免误判
_PLACEHOLDER_PREFIXES: tuple[str, ...] = (
    "sk-demo",
    "sk-fake",
    "sk-test",
    "sk-your-",
    "test-",
    "demo-",
    "placeholder",
)

# 完全相等的占位串（不区分大小写）
_PLACEHOLDER_EXACT: frozenset[str] = frozenset(
    {
        "sk-your-key-here",
        "sk-demo-placeholder",
        "your-api-key",
        "none",
        "null",
    }
)


def is_real_key(key: str | None) -> bool:
    """判断给定的 API Key 是否为「真实可用的用户 Key」。

    - ``None`` / 空串 / 纯空白 → False
    - 命中占位串或占位前缀 → False
    - 过短（< 8 字符）明显无效 → False
    - 其余视为真实 Key → True
    """
    if not key:
        return False
    k = key.strip()
    if not k:
        return False
    low = k.lower()
    if low in _PLACEHOLDER_EXACT:
        return False
    if any(low.startswith(p) for p in _PLACEHOLDER_PREFIXES):
        return False
    if len(k) < 8:
        return False
    return True
