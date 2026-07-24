"""AI 能力中心：密钥加密工具。

数据库中的 ``api_key`` 一律**加密存储**（Fernet 对称加密），密钥来自
``settings.ai_fernet_key``。读取（如「测试连接」真实调用）时才解密，明文
不落库、不出现在 API 响应里（列表接口返回 masked 形式）。
"""
from __future__ import annotations

from cryptography.fernet import Fernet

from app.core.config import settings

_fernet = Fernet(settings.ai_fernet_key)


def encrypt_secret(plain: str | None) -> str | None:
    """明文 → 密文（可逆）。None 原样返回。"""
    if plain is None:
        return None
    return _fernet.encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher: str | None) -> str | None:
    """密文 → 明文。None 原样返回。"""
    if cipher is None:
        return None
    try:
        return _fernet.decrypt(cipher.encode("utf-8")).decode("utf-8")
    except Exception:  # noqa: BLE001
        # 密钥轮换或数据损坏时，返回 None 而非崩溃（测试连接会因此失败）
        return None


def mask_secret(plain: str | None) -> str | None:
    """生成脱敏展示串，如 ``sk-1234...abcd``。用于列表接口回显。"""
    if not plain:
        return None
    if len(plain) <= 8:
        return "****"
    return f"{plain[:4]}...{plain[-4:]}"
