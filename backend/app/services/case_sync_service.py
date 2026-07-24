"""案例数据同步服务。

职责
----
- 从 JSONL 批量 upsert 裁判文书到 ``legal_cases`` 表（幂等，按 ``case_number`` 去重）。
- 预留外部权威数据源接入点（中国裁判文书网 / 北大法宝案例库 / 威科先行等）。

数据真实性说明
--------------
``legal_cases`` 表存放**真实裁判文书**（建议以最高人民法院指导案例、公报案例等权威
公开文书为准）。本服务只做入库，文书真实性由数据提供方保证；请勿写入虚构 / 演示文书。

JSONL 每行格式（与 ``scripts/seed_legal_cases.py`` 的 SEED 对齐）::

    {
      "title": "指导案例23号：孙银山诉南京欧尚超市有限公司江宁店买卖合同纠纷案",
      "case_number": "（2012）江宁商初字第...",
      "court": "江苏省南京市江宁区人民法院",
      "province": "江苏", "city": "南京",
      "trial_date": "2013-02-05",
      "case_type": "consumer", "court_level": "basic",
      "cause_of_action": "买卖合同纠纷",
      "plaintiff": "孙银山", "defendant": "南京欧尚超市有限公司江宁店",
      "facts": "...", "court_reasoning": "...", "judgement": "...",
      "winner": "孙银山", "compensation": "退一赔十",
      "keywords": ["食品安全", "十倍赔偿"], "related_laws": ["食品安全法第148条"],
      "source": "最高人民法院指导案例"
    }
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CourtLevelEnum, LegalCaseTypeEnum
from app.models.legal_case import LegalCase


def _parse_date(v) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


def _norm_row(d: dict) -> dict:
    ct = d.get("case_type", "other")
    cl = d.get("court_level", "basic")
    return {
        "title": d["title"].strip(),
        "case_number": (d.get("case_number") or "").strip() or None,
        "court": d.get("court"),
        "province": d.get("province"),
        "city": d.get("city"),
        "trial_date": _parse_date(d.get("trial_date")),
        "case_type": LegalCaseTypeEnum(ct),
        "court_level": CourtLevelEnum(cl),
        "cause_of_action": d.get("cause_of_action"),
        "plaintiff": d.get("plaintiff"),
        "defendant": d.get("defendant"),
        "facts": d.get("facts"),
        "court_reasoning": d.get("court_reasoning"),
        "judgement": d.get("judgement"),
        "winner": d.get("winner"),
        "compensation": d.get("compensation"),
        "keywords": d.get("keywords") or [],
        "related_laws": d.get("related_laws") or [],
        "source": d.get("source"),
    }


async def upsert_cases(session: AsyncSession, rows: Iterable[dict]) -> tuple[int, int]:
    """幂等 upsert 案例。返回 (新增数, 更新数)。按 ``case_number`` 去重。"""
    added = 0
    updated = 0
    for raw in rows:
        r = _norm_row(raw)
        cn = r["case_number"]
        existing = None
        if cn:
            existing = (
                await session.execute(
                    select(LegalCase).where(LegalCase.case_number == cn)
                )
            ).scalar_one_or_none()
        if existing is None:
            session.add(LegalCase(embedding=None, **r))
            added += 1
        else:
            for k, v in r.items():
                setattr(existing, k, v)
            updated += 1
    await session.commit()
    return added, updated


async def upsert_cases_from_jsonl(session: AsyncSession, path: str | Path) -> tuple[int, int]:
    """从 JSONL 文件批量 upsert 案例。"""
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
    return await upsert_cases(session, rows)


async def fetch_from_external_source(session: AsyncSession, source: str = "wenshu") -> None:
    """【预留】从外部裁判文书数据源拉取并入库（当前未实现，需数据源凭证/抓取逻辑）。"""
    raise NotImplementedError(
        f"外部案例数据源「{source}」尚未接入。请在 case_sync_service.fetch_from_external_source "
        "中实现抓取 + 清洗逻辑后调用 upsert_cases 入库。"
    )
