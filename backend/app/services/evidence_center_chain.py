"""智能证据中心 Step4：证据链（Evidence Graph）服务。

职责：
- 证据关系管理：手动建立 / 查询 / 删除（sequence/support/contradict/prerequisite/related）
- AI 关系推断：将若干证据的摘要交给 LLM，产出证据间关系建议并落库；
  无 AI key 时启发式兜底（时间先后 → sequence；金额重合 → support）
- 时间线构建：从 ``formed_at`` / 分析元数据中的日期自动生成案件时间线节点
  （``evidence_timeline``，可重建）
- 图谱组装：节点（证据 + 分析摘要/证明力）+ 边（关系）+ 时间线，一次返回

与 Step2/3 一致：不改动任何既有模块；AI 调用走 AIManager（AI Routing）。
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EvidenceRelationTypeEnum
from app.models.evidence_center import (
    EvidenceAnalysis,
    EvidenceFile,
    EvidenceRelation,
    EvidenceTimelineNode,
)
from app.models.user import User
from app.services.ai.manager import AIManager
from app.services.evidence_center_analyzer import _safe_json

logger = logging.getLogger(__name__)

# 单次链分析最多纳入的证据数（提示词长度与成本控制）
MAX_CHAIN_EVIDENCE = 30

_DATE_RE = re.compile(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})")


def _parse_any_date(val: object) -> datetime | None:
    """从任意字符串中解析出日期（支持 2024-01-15 / 2024年1月15日 等）。"""
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if not isinstance(val, str):
        return None
    m = _DATE_RE.search(val)
    if not m:
        return None
    try:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return datetime(y, mo, d, tzinfo=timezone.utc)
    except ValueError:
        return None


def _evidence_time(ef: EvidenceFile) -> datetime | None:
    """证据的「事件时间」：优先 formed_at，其次元数据中最早的日期。"""
    if ef.formed_at is not None:
        t = ef.formed_at
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    meta = ef.meta or {}
    dates = [
        d
        for d in (_parse_any_date(x) for x in (meta.get("times") or []))
        if d is not None
    ]
    return min(dates) if dates else None


class EvidenceChainService:
    """证据关系 / 时间线 / 图谱。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # 证据集选取（含权限）
    # ------------------------------------------------------------------
    async def pick_evidences(
        self,
        current: User,
        *,
        case_id: UUID | None = None,
        evidence_ids: list[UUID] | None = None,
        limit: int = MAX_CHAIN_EVIDENCE,
    ) -> list[EvidenceFile]:
        """选取参与证据链的证据集合（仅当前用户可见的）。

        优先级：显式 ``evidence_ids`` > ``case_id`` 下全部 > 用户全部（截断）。
        """
        conds = []
        if not current.is_superuser:
            conds.append(EvidenceFile.user_id == current.id)
        if evidence_ids:
            conds.append(EvidenceFile.id.in_(evidence_ids))
        elif case_id is not None:
            conds.append(EvidenceFile.case_id == case_id)
        stmt = (
            select(EvidenceFile)
            .where(*conds)
            .order_by(EvidenceFile.created_at.asc())
            .limit(limit)
        )
        return list((await self.db.scalars(stmt)).all())

    async def _owned(self, evidence_id: UUID, current: User) -> EvidenceFile | None:
        ef = await self.db.get(EvidenceFile, evidence_id)
        if ef is None:
            return None
        if ef.user_id != current.id and not current.is_superuser:
            return None
        return ef

    # ------------------------------------------------------------------
    # 关系 CRUD
    # ------------------------------------------------------------------
    async def create_relation(
        self,
        current: User,
        *,
        source_id: UUID,
        target_id: UUID,
        relation_type: EvidenceRelationTypeEnum,
        note: str | None = None,
    ) -> tuple[EvidenceRelation | None, bool, str | None]:
        """建立证据关系。返回 (relation, 是否新建, 错误信息)。

        校验：两端证据均存在且归当前用户；禁止自环；同向同类型幂等去重。
        """
        if source_id == target_id:
            return None, False, "不能建立证据与自身的关系"
        src = await self._owned(source_id, current)
        tgt = await self._owned(target_id, current)
        if src is None or tgt is None:
            return None, False, "源或目标证据不存在（或无权访问）"
        existing = (
            await self.db.scalars(
                select(EvidenceRelation).where(
                    EvidenceRelation.source_id == source_id,
                    EvidenceRelation.target_id == target_id,
                    EvidenceRelation.relation_type == relation_type,
                )
            )
        ).first()
        if existing is not None:
            return existing, False, None  # 幂等：已存在直接返回
        rel = EvidenceRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            note=note,
        )
        self.db.add(rel)
        await self.db.flush()
        return rel, True, None

    async def list_relations(
        self,
        current: User,
        *,
        case_id: UUID | None = None,
        evidence_id: UUID | None = None,
    ) -> list[EvidenceRelation]:
        """查询关系：按单证据（出边+入边）或按案件（案件下证据的所有关系）。"""
        if evidence_id is not None:
            ef = await self._owned(evidence_id, current)
            if ef is None:
                return []
            stmt = select(EvidenceRelation).where(
                or_(
                    EvidenceRelation.source_id == evidence_id,
                    EvidenceRelation.target_id == evidence_id,
                )
            )
            return list((await self.db.scalars(stmt)).all())

        evs = await self.pick_evidences(current, case_id=case_id, limit=200)
        ids = [e.id for e in evs]
        if not ids:
            return []
        stmt = select(EvidenceRelation).where(
            or_(
                EvidenceRelation.source_id.in_(ids),
                EvidenceRelation.target_id.in_(ids),
            )
        )
        return list((await self.db.scalars(stmt)).all())

    async def delete_relation(
        self, relation_id: UUID, current: User
    ) -> bool:
        rel = await self.db.get(EvidenceRelation, relation_id)
        if rel is None:
            return False
        # 权限：关系两端任一证据归当前用户即可删（关系本身无 owner 字段）
        src = await self._owned(rel.source_id, current)
        tgt = await self._owned(rel.target_id, current)
        if src is None and tgt is None:
            return False
        await self.db.delete(rel)
        await self.db.flush()
        return True

    # ------------------------------------------------------------------
    # AI 关系推断（无 key 启发式兜底）
    # ------------------------------------------------------------------
    async def infer_relations(
        self,
        current: User,
        mgr: AIManager,
        evidences: list[EvidenceFile],
    ) -> tuple[int, bool, str | None]:
        """自动推断证据间关系并落库。返回 (新建数量, ai_available, 说明)。"""
        if len(evidences) < 2:
            return 0, False, "证据不足 2 条，无需推断关系"

        analyses = await self._load_analyses([e.id for e in evidences])
        ai_available = False
        suggestions: list[dict] = []

        # --- AI 路径 ---
        try:
            content = await self._llm_suggest(mgr, evidences, analyses, current.id)
            if content is not None:
                ai_available = True
                suggestions = content
        except Exception as exc:  # AI 失败 → 兜底
            logger.warning("evidence chain AI infer failed, fallback: %s", exc)

        # --- 启发式兜底 ---
        if not suggestions:
            suggestions = self._heuristic_suggest(evidences)

        created = 0
        valid_ids = {str(e.id) for e in evidences}
        for s in suggestions:
            try:
                sid, tid = str(s.get("source_id")), str(s.get("target_id"))
                if sid not in valid_ids or tid not in valid_ids or sid == tid:
                    continue
                try:
                    rtype = EvidenceRelationTypeEnum(str(s.get("relation_type")))
                except ValueError:
                    rtype = EvidenceRelationTypeEnum.RELATED
                _rel, is_new, err = await self.create_relation(
                    current,
                    source_id=UUID(sid),
                    target_id=UUID(tid),
                    relation_type=rtype,
                    note=(str(s.get("note"))[:500] if s.get("note") else None),
                )
                if is_new and err is None:
                    created += 1
            except Exception:  # 单条建议异常不阻断
                continue
        note = None if ai_available else "AI 未配置或调用失败，已用启发式规则推断"
        return created, ai_available, note

    async def _load_analyses(
        self, ids: list[UUID]
    ) -> dict[UUID, EvidenceAnalysis]:
        if not ids:
            return {}
        rows = (
            await self.db.scalars(
                select(EvidenceAnalysis).where(EvidenceAnalysis.evidence_id.in_(ids))
            )
        ).all()
        return {a.evidence_id: a for a in rows}

    async def _llm_suggest(
        self,
        mgr: AIManager,
        evidences: list[EvidenceFile],
        analyses: dict[UUID, EvidenceAnalysis],
        user_id: UUID | None,
    ) -> list[dict] | None:
        """调用 LLM 产出关系建议；AI 不可用返回 None。"""
        if not await mgr.available("evidence_analysis", "chat"):
            return None

        lines = []
        for e in evidences:
            a = analyses.get(e.id)
            t = _evidence_time(e)
            lines.append(
                f"- id={e.id} | 名称:{e.name} | 类型:{e.category.value}"
                f" | 时间:{t.date().isoformat() if t else '未知'}"
                f" | 证明事项:{(a.proof_point or a.summary or '未分析')[:120] if a else '未分析'}"
            )
        system = (
            "你是资深诉讼律师，擅长梳理证据链。根据证据清单推断证据之间的关系，"
            "只输出 JSON，不要输出其他内容。关系类型限定："
            "sequence(时间先后)/support(相互印证)/contradict(矛盾)/"
            "prerequisite(前提基础)/related(一般关联)。"
        )
        user = (
            "证据清单：\n" + "\n".join(lines) + "\n\n"
            '输出格式：{"relations": [{"source_id": "…", "target_id": "…", '
            '"relation_type": "support", "note": "一句话说明"}]}\n'
            "要求：只在证据间确有逻辑联系时给出关系；矛盾要指明矛盾点；"
            "同一对证据最多一条最重要的关系；总数不超过 15 条。"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            model = await mgr.auto_route("evidence_analysis", "chat")
        except Exception:
            model = None
        if model is not None:
            rc = await mgr.chat_model(
                model.id, messages, json_mode=True, user_id=user_id
            )
            raw = rc.content
        else:
            raw = await mgr.chat(
                "evidence_analysis", messages, json_mode=True, user_id=user_id
            )
        data = _safe_json(raw)
        if not data:
            return None
        rels = data.get("relations")
        return rels if isinstance(rels, list) else None

    def _heuristic_suggest(self, evidences: list[EvidenceFile]) -> list[dict]:
        """启发式关系推断（无 AI 时兜底）。

        - 有时间的证据按时间排序，相邻两条建 sequence；
        - 元数据金额有交集的两条建 support。
        """
        suggestions: list[dict] = []
        dated = sorted(
            [(e, _evidence_time(e)) for e in evidences if _evidence_time(e)],
            key=lambda x: x[1],  # type: ignore[arg-type]
        )
        for (a, ta), (b, tb) in zip(dated, dated[1:]):
            suggestions.append(
                {
                    "source_id": str(a.id),
                    "target_id": str(b.id),
                    "relation_type": "sequence",
                    "note": f"时间先后：{ta.date()} → {tb.date()}",  # type: ignore[union-attr]
                }
            )
        # 金额交集 → support
        def amounts(e: EvidenceFile) -> set[str]:
            meta = e.meta or {}
            return {str(x) for x in (meta.get("amounts") or [])}

        n = len(evidences)
        for i in range(n):
            for j in range(i + 1, n):
                inter = amounts(evidences[i]) & amounts(evidences[j])
                if inter:
                    suggestions.append(
                        {
                            "source_id": str(evidences[i].id),
                            "target_id": str(evidences[j].id),
                            "relation_type": "support",
                            "note": f"金额相互印证：{'、'.join(sorted(inter)[:3])}",
                        }
                    )
        return suggestions[:15]

    # ------------------------------------------------------------------
    # 时间线
    # ------------------------------------------------------------------
    async def build_timeline(
        self,
        case_id: UUID,
        evidences: list[EvidenceFile],
        analyses: dict[UUID, EvidenceAnalysis] | None = None,
    ) -> list[EvidenceTimelineNode]:
        """重建案件时间线：删除旧节点 → 按证据时间排序生成新节点。

        每条「有时间」的证据生成一个节点；同一天的多条证据合并为一个节点。
        无时间的证据不进入时间线（仍在图谱节点中展示）。
        """
        if analyses is None:
            analyses = await self._load_analyses([e.id for e in evidences])

        # 删除旧时间线（重建语义）
        await self.db.execute(
            sa_delete(EvidenceTimelineNode).where(
                EvidenceTimelineNode.case_id == case_id
            )
        )

        # 按日期分组
        by_day: dict[str, list[EvidenceFile]] = {}
        times: dict[str, datetime] = {}
        for e in evidences:
            t = _evidence_time(e)
            if t is None:
                continue
            key = t.date().isoformat()
            by_day.setdefault(key, []).append(e)
            times[key] = t

        nodes: list[EvidenceTimelineNode] = []
        for idx, key in enumerate(sorted(by_day)):
            evs = by_day[key]
            if len(evs) == 1:
                a = analyses.get(evs[0].id)
                event = (a.proof_point[:80] if a and a.proof_point else evs[0].name)[:255]
                desc = a.summary if a else None
            else:
                event = f"{key}：{len(evs)} 项证据形成"
                desc = "；".join(e.name for e in evs)[:2000]
            node = EvidenceTimelineNode(
                case_id=case_id,
                event=event,
                event_time=times[key],
                description=desc,
                order_index=idx,
                evidence_ids=[str(e.id) for e in evs],
            )
            self.db.add(node)
            nodes.append(node)
        await self.db.flush()
        return nodes

    async def list_timeline(self, case_id: UUID) -> list[EvidenceTimelineNode]:
        stmt = (
            select(EvidenceTimelineNode)
            .where(EvidenceTimelineNode.case_id == case_id)
            .order_by(EvidenceTimelineNode.order_index.asc())
        )
        return list((await self.db.scalars(stmt)).all())

    # ------------------------------------------------------------------
    # 图谱组装
    # ------------------------------------------------------------------
    async def build_graph(
        self,
        current: User,
        *,
        case_id: UUID | None = None,
        evidence_ids: list[UUID] | None = None,
    ) -> dict:
        """组装 Evidence Graph：nodes + edges + timeline（timeline 仅限指定案件）。"""
        evidences = await self.pick_evidences(
            current, case_id=case_id, evidence_ids=evidence_ids
        )
        analyses = await self._load_analyses([e.id for e in evidences])
        ids = {e.id for e in evidences}

        edges: list[EvidenceRelation] = []
        if ids:
            edges = list(
                (
                    await self.db.scalars(
                        select(EvidenceRelation).where(
                            EvidenceRelation.source_id.in_(ids),
                            EvidenceRelation.target_id.in_(ids),
                        )
                    )
                ).all()
            )

        timeline: list[EvidenceTimelineNode] = []
        if case_id is not None:
            timeline = await self.list_timeline(case_id)

        nodes = []
        for e in evidences:
            a = analyses.get(e.id)
            t = _evidence_time(e)
            nodes.append(
                {
                    "id": e.id,
                    "name": e.name,
                    "category": e.category,
                    "status": e.status,
                    "event_time": t,
                    "proof_strength": a.proof_strength if a else None,
                    "proof_point": a.proof_point if a else None,
                    "summary": a.summary if a else None,
                }
            )
        return {"nodes": nodes, "edges": edges, "timeline": timeline}
