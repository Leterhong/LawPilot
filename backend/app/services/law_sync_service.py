"""法律数据同步服务。

职责
----
- 从 JSONL 批量 upsert 法条到 ``law`` 表（幂等，按 ``law_name + article`` 去重）。
- 预留外部权威数据源接入点（如「国家法律法规数据库」flk.npc.gov.cn、北大法宝、
  无讼等），便于后续持续补全，做到「所有法律都能搜出来」。

关于数据真实性的重要说明
------------------------
``law`` 表只存放**真实法条正文**，不存放任何演示 / 占位 / 虚构解读。所有文本应来自
权威出处（全国人大、国务院等）。本服务的 ``upsert_laws_from_jsonl`` 仅做入库，
文本真实性由数据提供方保证。

JSONL 每行格式（与 ``scripts/seed_laws.py`` 的 ROWS 对齐）::

    {
      "law_name": "中华人民共和国民法典",
      "chapter": "第三编 合同",
      "section": "第十四章 租赁合同",
      "article": "第703条",
      "content": "租赁合同是出租人将租赁物交付承租人使用、收益，承租人支付租金的合同。",
      "keywords": ["租赁", "合同", "租金"],
      "effective_date": "2021-01-01",
      "status": "effective",
      "source": "全国人民代表大会"
    }
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.law import Law


def _norm_row(d: dict) -> dict:
    """规整一行 JSONL 为 Law 字段；content 必填，其余带默认值。"""
    content = (d.get("content") or "").strip()
    if not content:
        raise ValueError(f"法条 content 不能为空: {d.get('law_name')} {d.get('article')}")
    return {
        "law_name": d["law_name"].strip(),
        "chapter": (d.get("chapter") or "").strip() or None,
        "section": (d.get("section") or "").strip() or None,
        "article": (d.get("article") or "").strip() or None,
        "content": content,
        "keywords": d.get("keywords") or [],
        "effective_date": d.get("effective_date"),
        "status": d.get("status", "effective"),
        "source": d.get("source"),
    }


async def upsert_laws(session: AsyncSession, rows: Iterable[dict]) -> tuple[int, int]:
    """幂等 upsert 法条。返回 (新增数, 更新数)。

    唯一键：``(law_name, article)``（article 非空时）。已存在则更新正文等字段，
    便于后续用更准确的权威文本补全。
    """
    added = 0
    updated = 0
    for raw in rows:
        r = _norm_row(raw)
        existing = (
            await session.execute(
                select(Law).where(
                    Law.law_name == r["law_name"], Law.article == r["article"]
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(Law(embedding=None, **r))
            added += 1
        else:
            for k, v in r.items():
                setattr(existing, k, v)
            updated += 1
    await session.commit()
    return added, updated


async def upsert_laws_from_jsonl(session: AsyncSession, path: str | Path) -> tuple[int, int]:
    """从 JSONL 文件批量 upsert。每行一个 JSON 对象。"""
    path = Path(path)
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{lineno} JSON 解析失败: {e}") from e
    return await upsert_laws(session, rows)


async def fetch_from_external_source(session: AsyncSession, source: str = "npc") -> None:
    """【预留】从外部权威数据源拉取并入库。

    当前未实现（需对应数据源的访问方式 / 凭证）。接入方式：
    1. 国家法律法规数据库 flk.npc.gov.cn —— 其前端为 SPA，需解析其内网 JSON 接口；
    2. 商业 API（北大法宝 / 无讼 / OpenLaw 等）—— 配置 base_url + api_key 后分页抓取。

    拿到结构化法条后，直接调用 :func:`upsert_laws` 即可，检索 / 前端无需改动。
    """
    raise NotImplementedError(
        f"外部数据源「{source}」尚未接入。请在 law_sync_service.fetch_from_external_source "
        "中实现抓取 + 清洗逻辑后调用 upsert_laws 入库。"
    )
