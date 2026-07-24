"""Agent 知识库（确定性规则来源）。

为每类案件预置：追问脚本（收集证据）、建议证据清单、我的权益分析、对方可能
存在的问题、推荐办理部门、可用文书类型、一句话结论模板、风险要点。

作用：
1. 当未配置 LLM 时，作为 Agent 的唯一决策依据，保证全流程可离线运行；
2. 当配置了 LLM 时，作为约束与兜底，防止模型幻觉、遗漏关键证据项。

所有内容均为通用法律常识性指引，最终以官方规定与个案事实为准。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.models.case import Case
from app.models.enums import CaseTypeEnum, DocTypeEnum

# 案件类型中文标签
CASE_TYPE_LABELS: dict[CaseTypeEnum, str] = {
    CaseTypeEnum.RENT: "房屋租赁纠纷",
    CaseTypeEnum.LABOR: "劳动纠纷",
    CaseTypeEnum.CONSUMER: "消费维权",
    CaseTypeEnum.LOAN: "借贷纠纷",
    CaseTypeEnum.MARRIAGE: "婚姻纠纷",
    CaseTypeEnum.MEDICAL: "医疗纠纷",
    CaseTypeEnum.EXPRESS: "快递/物流纠纷",
    CaseTypeEnum.OTHER: "其他纠纷",
}


@dataclass
class Question:
    """一次追问：问题文本 + 可选快捷选项（供前端快速回复）。"""

    id: str
    text: str
    options: Optional[List[str]] = None


# 每类案件的追问脚本（按顺序收集关键事实/证据）
QUESTION_SCRIPTS: dict[CaseTypeEnum, List[Question]] = {
    CaseTypeEnum.RENT: [
        Question("has_contract", "您和房东之间是否签订了书面租赁合同？", ["签订了", "只有口头约定", "没有任何约定"]),
        Question("deposit", "房东收取了多少押金？能否提供转账或收据凭证？", None),
        Question("issue", "目前的核心争议是什么？", ["无故扣押金", "提前赶人/清退", "房屋质量问题", "乱涨租金", "二房东跑路"]),
        Question("communication", "您是否与房东沟通协商过？是否有聊天记录或录音？", ["有聊天记录", "有录音", "都没有"]),
        Question("period", "您已入住多久？租期何时到期？", None),
    ],
    CaseTypeEnum.LABOR: [
        Question("has_contract", "您与单位是否签订了书面劳动合同？", ["签订了", "没签订", "不确定"]),
        Question("issue", "主要争议是什么？", ["拖欠工资", "违法解除/辞退", "未缴社保", "加班费争议", "工伤"]),
        Question("amount", "涉及金额大约多少（工资/补偿/赔偿金）？", None),
        Question("evidence", "您手头有哪些证据？", ["工资流水", "考勤记录", "聊天记录", "工牌/录用通知", "基本都没有"]),
        Question("period", "争议发生至今多久？单位是否仍在职？", None),
    ],
    CaseTypeEnum.CONSUMER: [
        Question("goods", "您购买的是什么商品或服务？金额大约多少？", None),
        Question("issue", "遇到了什么问题？", ["质量问题", "虚假宣传/欺诈", "拒绝退换货", "价格欺诈", "服务缩水"]),
        Question("evidence", "您保存了哪些凭证？", ["订单/支付记录", "商品照片/视频", "聊天记录", "发票", "基本都没有"]),
        Question("negotiated", "您是否已与商家协商？结果如何？", ["协商未果", "商家失联", "尚未协商"]),
    ],
    CaseTypeEnum.LOAN: [
        Question("has_io", "这是您借出还是借入？是否有借条/借款合同？", ["借出有借条", "借入有合同", "都没有书面凭证"]),
        Question("amount", "借款金额是多少？是否约定利息与还款期限？", None),
        Question("evidence", "您有哪些证据？", ["转账记录", "聊天记录确认借款", "借条照片", "都没有"]),
        Question("status", "对方目前还款态度如何？", ["拖延", "失联", "否认借款"]),
    ],
    CaseTypeEnum.MARRIAGE: [
        Question("goal", "您当前的主要诉求是什么？", ["协议离婚", "诉讼离婚", "财产分割", "子女抚养", "彩礼返还"]),
        Question("property", "涉及哪些主要财产？", ["房产", "车辆", "存款/理财", "公司股权", "基本无共同财产"]),
        Question("child", "是否有未成年子女？抚养如何考虑？", ["有，归我", "有，归对方", "有，争抚养权", "无子女"]),
        Question("agreement", "双方对离婚与分割是否大致达成一致？", ["基本一致", "分歧较大", "完全谈不拢"]),
    ],
    CaseTypeEnum.MEDICAL: [
        Question("relation", "您是患者本人还是家属？", ["本人", "家属"]),
        Question("issue", "争议焦点是什么？", ["诊断失误", "手术/操作过错", "用药错误", "告知不足/知情同意", "病历问题"]),
        Question("harm", "造成了什么后果？", ["病情加重", "伤残", "死亡", "额外医疗费用"]),
        Question("evidence", "您保存了哪些材料？", ["病历资料", "缴费单据", "沟通记录", "基本都没有"]),
    ],
    CaseTypeEnum.EXPRESS: [
        Question("issue", "快递出现了什么问题？", ["丢失", "损毁", "延误", "派送错误"]),
        Question("value", "托寄物品价值多少？是否保价？", None),
        Question("evidence", "您有哪些凭证？", ["运单号/订单", "物品价值证明", "破损照片", "沟通记录"]),
        Question("claimed", "您是否向快递公司索赔过？结果如何？", ["已索赔被拒", "尚未索赔", "赔偿金额不合理"]),
    ],
    CaseTypeEnum.OTHER: [
        Question("summary", "请用一两句话概括您遇到的问题。", None),
        Question("counterparty", "对方是个人还是单位？您是否知道其身份信息？", ["个人有信息", "单位有信息", "都不清楚"]),
        Question("evidence", "您目前有哪些证据或材料？", None),
        Question("goal", "您最希望达成什么结果？", None),
    ],
}

# 每类案件建议准备的证据清单
EVIDENCE_CHECKLIST: dict[CaseTypeEnum, List[str]] = {
    CaseTypeEnum.RENT: ["租赁合同/协议", "押金与租金转账记录", "押金收据", "房屋现状照片/视频", "与房东的聊天记录", "催告退款记录"],
    CaseTypeEnum.LABOR: ["劳动合同", "工资银行流水/工资条", "考勤记录", "社保缴纳记录", "录用通知/工牌", "辞退通知或聊天记录"],
    CaseTypeEnum.CONSUMER: ["订单截图与支付记录", "商品照片/视频", "发票或收据", "与商家聊天记录", "平台投诉记录"],
    CaseTypeEnum.LOAN: ["借条/借款合同", "转账凭证", "确认借款的聊天记录", "对方身份信息", "催收记录"],
    CaseTypeEnum.MARRIAGE: ["结婚证", "房产证/车辆登记", "银行流水", "子女出生证明", "对方收入证明"],
    CaseTypeEnum.MEDICAL: ["门诊/住院病历", "检查报告与影像资料", "缴费单据", "术前知情同意书", "与院方沟通记录"],
    CaseTypeEnum.EXPRESS: ["运单号与下单记录", "物品价值证明（发票/购买记录）", "破损/丢失照片", "与快递员或客服沟通记录"],
    CaseTypeEnum.OTHER: ["能证明事实的材料", "对方身份信息", "沟通记录", "损失证明"],
}

# 我的权益分析
RIGHTS: dict[CaseTypeEnum, str] = {
    CaseTypeEnum.RENT: "作为承租人，您享有按约使用房屋、要求房东交付符合约定房屋、到期退还押金的权利；房东不得擅自清退或无故扣押金。",
    CaseTypeEnum.LABOR: "作为劳动者，您享有按时足额获取劳动报酬、依法缴纳社保、在法定情形下解除劳动关系并获经济补偿的权利。",
    CaseTypeEnum.CONSUMER: "作为消费者，您享有知情权、安全权、公平交易权；遇欺诈可主张三倍赔偿（保底500元），遇不符合安全标准食品可主张十倍赔偿（保底1000元）。",
    CaseTypeEnum.LOAN: "作为出借人，您有权按约定收回本金与合法利息；利率超出合同成立时一年期贷款市场报价利率四倍的部分不受法律保护。",
    CaseTypeEnum.MARRIAGE: "婚姻自由与财产权利受法律保护；夫妻共同财产一般应均等分割，子女抚养以最有利于未成年子女为原则。",
    CaseTypeEnum.MEDICAL: "您享有安全医疗、知情同意与病历查阅复制的权利；因医疗过错受损可主张赔偿。",
    CaseTypeEnum.EXPRESS: "作为寄件人，您享有按约定安全送达的权利；快件丢失/损毁可依据保价或实际损失索赔。",
    CaseTypeEnum.OTHER: "您的人身、财产权益受法律保护，有权通过协商、投诉、调解、仲裁或诉讼维护自身合法权益。",
}

# 对方可能存在的问题
COUNTERPARTY: dict[CaseTypeEnum, str] = {
    CaseTypeEnum.RENT: "房东可能存在：未按约退还押金、无合法事由提前终止租赁、交付房屋不符合约定、单方面涨租等违约或违规情形。",
    CaseTypeEnum.LABOR: "单位可能存在：拖欠/不足额支付工资、未依法签订或续签合同、未缴社保、违法解除等违反劳动法规的情形。",
    CaseTypeEnum.CONSUMER: "经营者可能存在：虚假宣传、以次充好、价格欺诈、拒绝履行三包义务等侵害消费者权益的情形。",
    CaseTypeEnum.LOAN: "借款人可能存在：到期拒不还款、失联、否认借款等违约情形；如涉及高利或暴力催收亦可能涉嫌违法。",
    CaseTypeEnum.MARRIAGE: "对方可能在财产分割、子女抚养、债务承担等方面与您存在分歧，需厘清共同财产与个人财产边界。",
    CaseTypeEnum.MEDICAL: "医疗机构/医务人员可能存在：诊断或操作过错、未尽告知义务、病历书写不规范等情形。",
    CaseTypeEnum.EXPRESS: "快递企业可能存在：运输保管不当导致丢损、未按保价足额赔付、推诿责任等情形。",
    CaseTypeEnum.OTHER: "对方可能存在违约、侵权或欺诈等情形，需结合事实与证据具体判断。",
}

# 推荐办理部门
DEPARTMENTS: dict[CaseTypeEnum, List[dict]] = {
    CaseTypeEnum.RENT: [
        {"name": "房屋所在地街道办事处/司法所（人民调解）", "reason": "成本低、效率高，适合先行调解退押金/腾房争议"},
        {"name": "住建部门（房屋租赁管理）", "reason": "对租赁违规行为可进行行政处理"},
        {"name": "人民法院（基层）", "reason": "调解不成可立案起诉，主张退还押金与赔偿"},
    ],
    CaseTypeEnum.LABOR: [
        {"name": "劳动监察大队", "reason": "可责令单位支付拖欠工资、补缴社保"},
        {"name": "劳动争议仲裁委员会", "reason": "劳动纠纷仲裁前置，免费且专业"},
        {"name": "人民法院", "reason": "对仲裁裁决不服可于15日内起诉"},
    ],
    CaseTypeEnum.CONSUMER: [
        {"name": "12315 市场监管投诉举报平台", "reason": "处理消费欺诈、质量问题、退换货争议"},
        {"name": "电商/服务平台客服", "reason": "平台内纠纷可先行投诉维权"},
        {"name": "人民法院", "reason": "协商投诉无果可起诉索赔"},
    ],
    CaseTypeEnum.LOAN: [
        {"name": "人民法院", "reason": "凭借条与转账记录起诉要求还款"},
        {"name": "人民调解委员会", "reason": "可组织双方达成分期还款协议"},
    ],
    CaseTypeEnum.MARRIAGE: [
        {"name": "婚姻登记机关", "reason": "双方自愿且对子女/财产达成一致可协议离婚"},
        {"name": "人民法院", "reason": "争议较大时可诉讼离婚并分割财产"},
    ],
    CaseTypeEnum.MEDICAL: [
        {"name": "医疗机构投诉管理部门", "reason": "先行院内投诉与封存病历"},
        {"name": "医疗纠纷人民调解委员会", "reason": "专业调解医疗损害赔偿"},
        {"name": "卫生健康行政部门", "reason": "对违法违规行为可行政处理"},
        {"name": "人民法院", "reason": "调解不成可起诉，必要时申请医疗损害鉴定"},
    ],
    CaseTypeEnum.EXPRESS: [
        {"name": "快递企业官方客服/投诉渠道", "reason": "先行索赔与协商"},
        {"name": "国家邮政局申诉网站（12305）", "reason": "对企业处理结果不满可升级申诉"},
        {"name": "人民法院", "reason": "索赔无果可起诉"},
    ],
    CaseTypeEnum.OTHER: [
        {"name": "对应行业主管部门/12345 市民热线", "reason": "按纠纷性质寻求行政处理或指引"},
        {"name": "人民调解委员会", "reason": "低成本化解民间纠纷"},
        {"name": "人民法院", "reason": "协商不成依法起诉"},
    ],
}

# 可用文书类型
DOC_TYPES: dict[CaseTypeEnum, List[DocTypeEnum]] = {
    CaseTypeEnum.RENT: [DocTypeEnum.DUNNING_LETTER, DocTypeEnum.LAWYER_LETTER, DocTypeEnum.COMPLAINT, DocTypeEnum.LAWSUIT, DocTypeEnum.EVIDENCE_LIST],
    CaseTypeEnum.LABOR: [DocTypeEnum.DUNNING_LETTER, DocTypeEnum.LAWYER_LETTER, DocTypeEnum.COMPLAINT, DocTypeEnum.ARBITRATION, DocTypeEnum.LAWSUIT, DocTypeEnum.EVIDENCE_LIST],
    CaseTypeEnum.CONSUMER: [DocTypeEnum.COMPLAINT, DocTypeEnum.LAWYER_LETTER, DocTypeEnum.LAWSUIT, DocTypeEnum.EVIDENCE_LIST],
    CaseTypeEnum.LOAN: [DocTypeEnum.DUNNING_LETTER, DocTypeEnum.LAWYER_LETTER, DocTypeEnum.LAWSUIT, DocTypeEnum.EVIDENCE_LIST],
    CaseTypeEnum.MARRIAGE: [DocTypeEnum.LAWSUIT, DocTypeEnum.DEFENSE, DocTypeEnum.EVIDENCE_LIST],
    CaseTypeEnum.MEDICAL: [DocTypeEnum.COMPLAINT, DocTypeEnum.LAWYER_LETTER, DocTypeEnum.LAWSUIT, DocTypeEnum.EVIDENCE_LIST],
    CaseTypeEnum.EXPRESS: [DocTypeEnum.COMPLAINT, DocTypeEnum.LAWYER_LETTER, DocTypeEnum.LAWSUIT, DocTypeEnum.EVIDENCE_LIST],
    CaseTypeEnum.OTHER: [DocTypeEnum.DUNNING_LETTER, DocTypeEnum.COMPLAINT, DocTypeEnum.LAWSUIT, DocTypeEnum.EVIDENCE_LIST],
}

# 一句话结论模板
CONCLUSION: dict[CaseTypeEnum, str] = {
    CaseTypeEnum.RENT: "本案为房屋租赁纠纷，您作为承租人有权主张退还押金并要求房东承担违约/赔偿责任，建议先固定证据再协商或投诉。",
    CaseTypeEnum.LABOR: "本案为劳动争议，您作为劳动者有权追讨欠薪/补偿，应先收集劳动关系证据并申请劳动仲裁。",
    CaseTypeEnum.CONSUMER: "本案为消费维权，您可依据消法主张退赔，遇欺诈可主张三倍赔偿，建议保留凭证并向12315投诉。",
    CaseTypeEnum.LOAN: "本案为借贷纠纷，您作为出借人可凭借条与转账记录要求还款，协商不成可向法院起诉。",
    CaseTypeEnum.MARRIAGE: "本案为婚姻纠纷，建议围绕财产分割与子女抚养厘清共同财产边界，能协议则协议、不能则诉讼。",
    CaseTypeEnum.MEDICAL: "本案为医疗纠纷，建议封存病历并固定过错证据，通过调解或诉讼主张赔偿，必要时申请医疗损害鉴定。",
    CaseTypeEnum.EXPRESS: "本案为快递纠纷，您可凭运单与价值证明向快递企业及邮政申诉渠道索赔。",
    CaseTypeEnum.OTHER: "本案为一般民事纠纷，建议先厘清事实与证据，再选择协商、投诉或诉讼路径维权。",
}

# 风险要点（用于报告风险分析中的文字说明）
RISK_NOTES: dict[CaseTypeEnum, str] = {
    CaseTypeEnum.RENT: "注意诉讼时效为三年；仅有口头约定或无押金凭证将显著增加举证难度。",
    CaseTypeEnum.LABOR: "劳动仲裁时效为一年，自知道权利受损起算；未签合同仍可凭工资流水、考勤等认定事实劳动关系。",
    CaseTypeEnum.CONSUMER: "请保留原始商品与凭证，拆封/使用可能影响退换；三倍赔偿以实际支付价款为基数。",
    CaseTypeEnum.LOAN: "超出法定上限的利息不受保护；现金交付且无借条极难举证，建议补强证据。",
    CaseTypeEnum.MARRIAGE: "离婚冷静期适用于协议离婚；财产转移可能被认定为恶意，需注意保全。",
    CaseTypeEnum.MEDICAL: "病历是关键证据，务必及时封存；医疗损害需鉴定确认过错与因果关系。",
    CaseTypeEnum.EXPRESS: "未保价通常按资费倍数限额赔偿，贵重物品务必保价并留存价值证明。",
    CaseTypeEnum.OTHER: "尽早固定证据，超过时效或证据不足将明显不利于维权。",
}


def build_legal_query(case: Case) -> str:
    """构造用于 RAG 法律检索的查询语句。"""
    label = CASE_TYPE_LABELS.get(case.case_type, "纠纷")
    desc = (case.description or case.title or "").strip()
    if desc:
        return f"{label} {desc[:120]}"
    return label


def script_for(case_type: CaseTypeEnum) -> List[Question]:
    """获取某案件类型的追问脚本。"""
    return QUESTION_SCRIPTS.get(case_type, QUESTION_SCRIPTS[CaseTypeEnum.OTHER])
