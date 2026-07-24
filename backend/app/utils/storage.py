"""文件存储抽象层。

统一证据 / 合同等上传文件的落盘与删除。当前实现为本地文件系统
（``settings.upload_dir`` 下按模块 / 用户分目录），并为「对象存储」
预留切换点：后续可将 ``save_upload`` 改为写入 S3 / OSS / COS 并返回
可访问 URL，调用方无需改动（模型字段 ``file_url`` 兼容相对路径与绝对 URL）。
"""
from __future__ import annotations

import os
import uuid

from fastapi import UploadFile

from app.core.config import settings


class StorageError(Exception):
    """存储层异常（磁盘写入失败等）。"""


def _ext(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


async def save_upload(
    file: UploadFile,
    *,
    module: str = "evidence",
    owner_id: uuid.UUID | None = None,
) -> tuple[str, str, int]:
    """保存上传文件，返回 ``(存储绝对路径, file_url, 字节数)``。

    - 物理路径：``{upload_dir}/{module}/{owner_id or 'anon'}/{uuid}{ext}``
    - ``file_url``：当前为相对 ``upload_dir`` 的路径（统一正斜杠），
      对象存储实现应返回可公开/带签名访问的 URL。
    """
    filename = file.filename or "unnamed"
    ext = _ext(filename)
    base = os.path.join(settings.upload_dir, module)
    if owner_id is not None:
        base = os.path.join(base, str(owner_id))
    os.makedirs(base, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(base, stored_name)
    try:
        content = await file.read()
        with open(stored_path, "wb") as f:
            f.write(content)
    except OSError as exc:  # pragma: no cover - 磁盘异常
        raise StorageError(f"文件写入失败：{exc}") from exc

    file_url = os.path.relpath(stored_path, settings.upload_dir).replace(os.sep, "/")
    return stored_path, file_url, len(content)


def resolve_path(file_url: str | None) -> str | None:
    """由 ``file_url`` 解析为本地绝对路径（对象存储 URL 时返回 None）。"""
    if not file_url:
        return None
    if file_url.startswith(("http://", "https://", "/")):
        # 远程 / 绝对 URL 无法在本地解析
        return None
    return os.path.join(settings.upload_dir, file_url)


def delete_file(stored_path: str | None) -> None:
    """删除本地落盘文件（忽略不存在 / 异常）。"""
    if not stored_path:
        return
    try:
        if os.path.isfile(stored_path):
            os.remove(stored_path)
    except OSError:
        pass
