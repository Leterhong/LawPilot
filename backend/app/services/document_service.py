"""文书服务：按类型生成法律文书（Markdown 模板）。

Phase 3 采用确定性模板填充（不依赖大模型，保证可离线运行）。Phase 6 可由
Agent 调用大模型润色。文书内容使用占位符标注未知信息，便于用户补全。
"""
from __future__ import annotations

from datetime import date

from app.models.case import Case
from app.models.document import Document
from app.models.enums import DocStatusEnum, DocTypeEnum, EventTypeEnum
from app.models.evidence import Evidence
from app.models.user import User
from app.repositories.case_repo import DocumentRepository, EvidenceRepository
from app.repositories.task_repo import HistoryRepository


def _ctx(case: Case, user: User, extra: dict | None):
    extra = extra or {}
    return {
        "today": date.today().isoformat(),
        "claimant": user.display_name or "（您的姓名）",
        "respondent": extra.get("respondent") or "（对方姓名/名称）",
        "amount": extra.get("amount") or "（金额）",
        "address": extra.get("address") or "（地址）",
        "case_title": case.title,
        "description": case.description or "（请补充事实经过）",
    }


# 各文书生成器：返回 (title, content_md)
_GENERATORS = {
    DocTypeEnum.DUNNING_LETTER: lambda c, u, e, ev: (
        f"催告函 - {c['case_title']}",
        f"""致：{c['respondent']}

关于「{c['case_title']}」一事，本人（{c['claimant']}）现正式催告如下：

一、事由
{c['description']}

二、要求
请于收到本函之日起 7 日内，向本人履行相关义务（涉及金额：{c['amount']}）。

三、法律后果
若逾期未处理，本人将依法向有关部门投诉或向人民法院起诉，由此产生的
诉讼费、律师费、保全费等将由贵方承担。

催告人：{c['claimant']}
日期：{c['today']}
""",
    ),
    DocTypeEnum.LAWYER_LETTER: lambda c, u, e, ev: (
        f"律师函（模板） - {c['case_title']}",
        f"""【律师事务所名称】（以下简称"本所"）接受 {c['claimant']} 的委托，
就「{c['case_title']}」一事，特向 {c['respondent']} 致送本律师函：

事实摘要：
{c['description']}

律师意见：
依据相关法律规定，贵方应当履行相应义务。请于收到本函之日起 7 日内与
委托人协商解决，否则本所将协助委托人采取进一步法律行动。

【律师签名】
【律师事务所】
{c['today']}
""",
    ),
    DocTypeEnum.COMPLAINT: lambda c, u, e, ev: (
        f"投诉书 - {c['case_title']}",
        f"""投诉人：{c['claimant']}
被投诉人：{c['respondent']}

投诉请求：
1. 依法处理被投诉人的违法违规行为；
2. 维护投诉人合法权益（涉及金额：{c['amount']}）。

事实与理由：
{c['description']}

此致
（主管部门名称）

投诉人：{c['claimant']}
日期：{c['today']}
""",
    ),
    DocTypeEnum.ARBITRATION: lambda c, u, e, ev: (
        f"仲裁申请书 - {c['case_title']}",
        f"""申请人：{c['claimant']}
被申请人：{c['respondent']}

仲裁请求：
1. 裁决被申请人履行义务（涉及金额：{c['amount']}）；
2. 由被申请人承担本案仲裁费用。

事实与理由：
{c['description']}

此致
（仲裁委员会名称）

申请人：{c['claimant']}
日期：{c['today']}
""",
    ),
    DocTypeEnum.LAWSUIT: lambda c, u, e, ev: (
        f"民事起诉状 - {c['case_title']}",
        f"""原告：{c['claimant']}
被告：{c['respondent']}

诉讼请求：
1. 判令被告履行义务（涉及金额：{c['amount']}）；
2. 判令被告承担本案诉讼费用。

事实与理由：
{c['description']}

此致
（人民法院名称）

具状人：{c['claimant']}
日期：{c['today']}
""",
    ),
    DocTypeEnum.DEFENSE: lambda c, u, e, ev: (
        f"答辩状（模板） - {c['case_title']}",
        f"""答辩人：{c['claimant']}
被答辩人：{c['respondent']}

答辩意见：
针对被答辩人就「{c['case_title']}」提出的诉求，答辩人作如下答辩：
（请结合事实与法律依据逐条回应）

此致
（人民法院名称）

答辩人：{c['claimant']}
日期：{c['today']}
""",
    ),
}


def _evidence_list_md(evidence: list[Evidence]) -> str:
    if not evidence:
        return "（暂无证据，请先添加）"
    lines = ["| 序号 | 类别 | 证据名称 | 是否已提供 |", "|---|---|---|---|"]
    cat_map = {
        "contract": "合同",
        "chat_record": "聊天记录",
        "payment_record": "付款记录",
        "photo": "照片",
        "video": "视频",
        "audio": "录音",
        "other": "其他",
    }
    for i, ev in enumerate(evidence, 1):
        lines.append(
            f"| {i} | {cat_map.get(ev.category.value, ev.category.value)} | {ev.title} | {'是' if ev.is_uploaded else '否'} |"
        )
    return "\n".join(lines)


class DocumentService:
    def __init__(self, session) -> None:
        self.repo = DocumentRepository(session)
        self.evidence_repo = EvidenceRepository(session)
        self.history = HistoryRepository(session)

    async def generate(
        self,
        case: Case,
        user: User,
        doc_type: DocTypeEnum,
        extra: dict | None = None,
    ) -> Document:
        ctx = _ctx(case, user, extra)
        evidence = await self.evidence_repo.list(case_id=case.id)
        if doc_type == DocTypeEnum.EVIDENCE_LIST:
            title = f"证据目录 - {case.title}"
            content = f"# 证据目录\n\n{_evidence_list_md(evidence)}\n"
        else:
            gen = _GENERATORS.get(doc_type)
            if gen is None:
                raise ValueError("UNSUPPORTED_DOC_TYPE")
            title, content = gen(ctx, user, extra or {}, evidence)

        document = await self.repo.create(
            case_id=case.id,
            user_id=user.id,
            doc_type=doc_type,
            title=title,
            content=content,
            status=DocStatusEnum.GENERATED,
        )
        await self.history.create(
            case_id=case.id,
            user_id=user.id,
            event_type=EventTypeEnum.DOCUMENT_GENERATED,
            title="生成文书",
            detail=title,
        )
        return document

    async def list_by_case(self, case: Case) -> list[Document]:
        return await self.repo.list(case_id=case.id, order_by=Document.created_at.desc())
