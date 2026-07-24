"""Agent 流程引擎（Phase 6 核心）。

以 Workflow 状态机为驱动，实现产品定义的对话流程：
识别案件类型 → 连续追问收集证据 → 证据充足后调用 RAG 生成案件报告。

设计要点：
- 默认走确定性规则分支（knowledge_base 的追问脚本），无需 LLM 即可完整运行；
- 若配置了真实 LLM（settings.llm_api_key），则在每轮用模型做事实抽取与更自然
  的回复，失败后自动回退规则分支；
- 证据收集完成（脚本问完）即触发 build_and_persist_report，产出 11 章节报告
  并落库，同时生成 Roadmap 与待办任务。

所有写操作在方法内提交，调用方无需关心事务细节。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.enums import (
    CaseStatusEnum,
    EventTypeEnum,
    MessageTypeEnum,
    RoleEnum,
    WorkflowStageEnum,
)
from app.models.message import Message
from app.models.user import User
from app.models.workflow import Workflow
from app.repositories.case_repo import EvidenceRepository, MessageRepository, WorkflowRepository
from app.repositories.task_repo import HistoryRepository
from app.services.agent.knowledge_base import Question, script_for
from app.services.agent.prompts import SYSTEM_PROMPT, build_decision_prompt
from app.services.agent.report import build_and_persist_report
from app.services.llm.client import LLMClient


@dataclass
class _Step:
    """单轮决策结果（内部使用）。"""

    collected: dict
    missing: List[str]
    next_question: Optional[str]
    next_options: Optional[List[str]]
    is_complete: bool
    reply: str


@dataclass
class AgentTurn:
    """一轮对话后的返回。"""

    assistant_message: Message
    workflow: Workflow
    case: Case
    report_generated: bool


class AgentEngine:
    """Agent 流程引擎。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.llm = LLMClient(db=self.session, feature="agent_reasoning")
        self.workflow = WorkflowRepository(session)
        self.messages = MessageRepository(session)
        self.evidence = EvidenceRepository(session)
        self.history = HistoryRepository(session)

    # ------------------------- 初始化与状态 -------------------------
    async def _get_or_init(self, case: Case) -> Workflow:
        """加载工作流；若不存在或脚本未初始化则初始化（含首个问题消息）。"""
        wf = await self.workflow.get_by_case(case.id)
        if wf is None:
            wf = await self.workflow.create(case_id=case.id, stage=WorkflowStageEnum.IDENTIFY)
        if wf.missing_fields is None:
            await self._init_script(case, wf)
        return wf

    async def _init_script(self, case: Case, wf: Workflow) -> None:
        script = script_for(case.case_type)
        wf.collected_fields = {}
        wf.missing_fields = [q.id for q in script]
        if script:
            wf.next_question = script[0].text
            wf.stage = WorkflowStageEnum.CLARIFY
            # 把首个问题作为 assistant 消息落库，使对话完整可回放
            await self._add_assistant(
                case,
                script[0].text,
                metadata={"question_id": script[0].id, "is_question": True, "options": script[0].options},
            )
        else:
            wf.next_question = None
            wf.is_complete = True
            wf.stage = WorkflowStageEnum.REPORT
        self.session.add(wf)
        await self.session.commit()
        await self.session.refresh(wf)

    async def get_state(self, case: Case):
        """供前端拉取当前状态（首个问题在此初始化并展示）。"""
        wf = await self._get_or_init(case)
        return wf, case

    # ------------------------- 核心：处理一轮用户消息 -------------------------
    async def respond(self, case: Case, user_text: str, user: User) -> AgentTurn:
        wf = await self._get_or_init(case)

        # 先持久化用户消息，保证对话时序（首个问题 → 用户回答 → 下一问）
        await self._add_user(case, user_text, user)

        # 已出报告：不再追问，仅做轻量回应
        if wf.is_complete:
            reply = (
                "您的案件报告已生成，可在「报告」标签页查看完整分析"
                "（结论、涉及法律、权益、证据建议、下一步与办理部门）。"
                "如需补充信息或生成文书，随时告诉我。"
            )
            msg = await self._add_assistant(case, reply, metadata={"report_ready": True})
            return AgentTurn(msg, wf, case, False)

        pending_qid = wf.missing_fields[0]
        script = script_for(case.case_type)

        decision = None
        if await self.llm.available_async():
            decision = await self._llm_step(case, wf, user_text, pending_qid, script)
        if decision is None:
            decision = self._rule_step(wf, user_text, pending_qid, script)

        # 应用决策到工作流
        wf.collected_fields = decision.collected
        wf.missing_fields = decision.missing
        wf.next_question = decision.next_question
        wf.is_complete = decision.is_complete
        wf.stage = (
            WorkflowStageEnum.REPORT
            if decision.is_complete
            else WorkflowStageEnum.COLLECT_EVIDENCE
        )
        self.session.add(wf)
        await self.session.commit()
        await self.session.refresh(wf)

        # 保存 assistant 回复（含下一问的快捷选项）
        meta = {"is_question": not decision.is_complete}
        if not decision.is_complete and decision.next_options:
            meta["options"] = decision.next_options
        msg = await self._add_assistant(case, decision.reply, metadata=meta)

        report_generated = False
        if decision.is_complete:
            await build_and_persist_report(case, self.session)
            report_generated = True
            case.status = CaseStatusEnum.IN_PROGRESS
            case.current_stage = WorkflowStageEnum.REPORT.value
            self.session.add(case)
            await self.session.commit()
            await self.session.refresh(case)

        return AgentTurn(msg, wf, case, report_generated)

    # ------------------------- 规则分支（默认/兜底） -------------------------
    def _rule_step(self, wf, user_text, pending_qid, script) -> _Step:
        collected = dict(wf.collected_fields or {})
        collected[pending_qid] = (user_text or "").strip()
        missing = list(wf.missing_fields)
        if pending_qid in missing:
            missing.remove(pending_qid)
        next_q = self._find_question(missing[0], script) if missing else None
        return self._build_step(collected, missing, next_q)

    # ------------------------- LLM 分支 -------------------------
    async def _llm_step(self, case, wf, user_text, pending_qid, script):
        history_lines = await self._history_lines(case, limit=8)
        prompt = build_decision_prompt(
            case, script, wf.collected_fields or {}, pending_qid, history_lines
        )
        data = await self.llm.complete_json(prompt, system=SYSTEM_PROMPT, temperature=0.2)
        if not data:
            return None
        try:
            collected = dict(wf.collected_fields or {})
            updates = data.get("collected_updates") or {}
            if isinstance(updates, dict):
                collected.update({k: str(v) for k, v in updates.items()})
            collected[pending_qid] = (user_text or "").strip()

            # 依据已收集事实重新推导待问列表
            script_ids = [q.id for q in script]
            missing = [qid for qid in script_ids if qid not in collected]

            next_qid = data.get("next_question_id")
            is_complete = bool(data.get("is_complete")) or next_qid is None
            next_q = self._find_question(next_qid, script) if (next_qid and not is_complete) else None
            reply = data.get("reply") or self._reply_for_next(next_q)
            return self._build_step(collected, missing, next_q, reply=reply)
        except Exception:
            return None

    # ------------------------- 工具方法 -------------------------
    def _build_step(self, collected, missing, next_q, reply=None) -> _Step:
        next_question = next_q.text if next_q else None
        next_options = next_q.options if next_q else None
        is_complete = next_q is None
        if reply is None:
            reply = self._reply_for_next(next_q)
        return _Step(
            collected=collected,
            missing=missing,
            next_question=next_question,
            next_options=next_options,
            is_complete=is_complete,
            reply=reply,
        )

    @staticmethod
    def _find_question(qid, script) -> Optional[Question]:
        for q in script:
            if q.id == qid:
                return q
        return None

    @staticmethod
    def _reply_for_next(next_q) -> str:
        if next_q is None:
            return (
                "✅ 信息已收集齐全，我正在为您生成案件分析报告"
                "（包含结论、涉及法律、您的权益、证据建议、下一步与办理部门等），请稍候…"
            )
        return f"好的，已记录。还有一个问题想向您确认：\n{next_q.text}"

    async def _add_assistant(self, case: Case, content: str, metadata=None) -> Message:
        seq = await self.messages.next_sequence(case.id)
        msg = await self.messages.create(
            case_id=case.id,
            role=RoleEnum.ASSISTANT,
            content=content,
            sequence=seq,
            message_type=MessageTypeEnum.TEXT,
            metadata_json=metadata,
        )
        return msg

    async def _add_user(self, case: Case, content: str, user: User) -> Message:
        seq = await self.messages.next_sequence(case.id)
        msg = await self.messages.create(
            case_id=case.id,
            role=RoleEnum.USER,
            content=content,
            sequence=seq,
            message_type=MessageTypeEnum.TEXT,
        )
        await self.history.create(
            case_id=case.id,
            user_id=user.id,
            event_type=EventTypeEnum.MESSAGE,
            title="用户消息",
            detail=content[:80],
        )
        return msg

    async def _history_lines(self, case: Case, limit: int = 8) -> List[str]:
        msgs = await self.messages.list(order_by=Message.sequence, case_id=case.id)
        lines = [f"{'用户' if m.role == RoleEnum.USER else '助手'}：{m.content}" for m in msgs]
        return lines[-limit:]
