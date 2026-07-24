"""领域枚举定义。

集中管理所有业务状态枚举，保证数据库、API、Agent 三处共用同一套取值，
避免字符串散落导致的不一致。PostgreSQL 中使用原生枚举类型存储。
"""
from __future__ import annotations

import enum


class CaseTypeEnum(str, enum.Enum):
    """案件类型（对应首页四个快捷入口 + 扩展场景）。"""

    RENT = "rent"               # 房屋租赁
    LABOR = "labor"             # 劳动纠纷
    CONSUMER = "consumer"       # 消费维权
    LOAN = "loan"               # 借贷纠纷
    MARRIAGE = "marriage"       # 婚姻纠纷
    MEDICAL = "medical"         # 医疗纠纷
    EXPRESS = "express"         # 快递/物流
    OTHER = "other"             # 其他


class CaseStatusEnum(str, enum.Enum):
    """案件生命周期状态。"""

    INTAKE = "intake"                       # 录入中（用户刚描述遭遇）
    COLLECTING_EVIDENCE = "collecting"      # Agent 追问收集证据中
    ANALYZING = "analyzing"                 # 证据充足，生成分析中
    IN_PROGRESS = "in_progress"             # 已出报告，用户按 Roadmap 办理
    COMPLETED = "completed"                 # 办结
    CLOSED = "closed"                       # 关闭/放弃


class RoleEnum(str, enum.Enum):
    """对话角色。"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageTypeEnum(str, enum.Enum):
    """消息类型。"""

    TEXT = "text"               # 普通文本
    QUICK_REPLY = "quick_reply" # 结构化快捷回复（如选项）
    DOCUMENT = "document"       # 关联文书消息
    SYSTEM_EVENT = "system_event" # 系统事件（状态变更等）


class DocTypeEnum(str, enum.Enum):
    """可自动生成的文书类型。"""

    DUNNING_LETTER = "dunning_letter"   # 催告函
    LAWYER_LETTER = "lawyer_letter"     # 律师函（模板）
    COMPLAINT = "complaint"             # 投诉书
    ARBITRATION = "arbitration"         # 仲裁申请书（模板）
    LAWSUIT = "lawsuit"                 # 起诉状（模板）
    DEFENSE = "defense"                 # 答辩状（模板）
    EVIDENCE_LIST = "evidence_list"     # 证据目录


class DocStatusEnum(str, enum.Enum):
    """文书状态。"""

    DRAFT = "draft"
    GENERATED = "generated"
    FINALIZED = "finalized"


class EvidenceCategoryEnum(str, enum.Enum):
    """证据类别。"""

    CONTRACT = "contract"         # 合同/协议
    CHAT_RECORD = "chat_record"   # 聊天记录
    PAYMENT_RECORD = "payment_record" # 付款/转账记录
    PHOTO = "photo"               # 照片
    VIDEO = "video"               # 视频
    AUDIO = "audio"               # 录音
    OTHER = "other"               # 其他


class StepStatusEnum(str, enum.Enum):
    """Roadmap 步骤状态。"""

    PENDING = "pending"
    DONE = "done"
    SKIPPED = "skipped"


class WorkflowStageEnum(str, enum.Enum):
    """Agent 工作流阶段（状态机）。"""

    IDENTIFY = "identify"             # 识别案件类型
    CLARIFY = "clarify"               # 追问澄清事实
    COLLECT_EVIDENCE = "collect"      # 收集证据
    ANALYZE = "analyze"               # 生成分析/报告
    REPORT = "report"                 # 报告已交付
    MONITOR = "monitor"               # 持续提醒/跟进


class TaskStatusEnum(str, enum.Enum):
    """待办任务状态。"""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class PriorityEnum(str, enum.Enum):
    """优先级。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EventTypeEnum(str, enum.Enum):
    """案件时间线事件类型（history 表）。"""

    CREATED = "created"
    MESSAGE = "message"
    EVIDENCE_ADDED = "evidence_added"
    REPORT_GENERATED = "report_generated"
    DOCUMENT_GENERATED = "document_generated"
    STATUS_CHANGED = "status_changed"
    TASK_DONE = "task_done"
    REMINDER = "reminder"


class LegalSourceEnum(str, enum.Enum):
    """法律渊源（legal_reference.source 与 knowledge.category 共用）。"""

    LAW = "law"                           # 法律
    JUDICIAL_INTERPRETATION = "judicial_interpretation"  # 司法解释
    ADMIN_REGULATION = "admin_regulation" # 行政法规
    LOCAL_REGULATION = "local_regulation" # 地方性法规
    GUIDING_CASE = "guiding_case"         # 指导案例
    TYPICAL_CASE = "typical_case"         # 典型案例
    GUIDE = "guide"                       # 办事指南
    POLICY = "policy"                     # 政策


class CaseCenterStatusEnum(str, enum.Enum):
    """案件中心状态（独立于 Phase 1 cases 的 6 状态，共 8 档，面向用户办事视角）。"""

    PENDING = "pending"                       # 待处理
    IN_PROGRESS = "in_progress"               # 处理中
    WAITING_REPLY = "waiting_reply"           # 等待回复
    WAITING_MATERIAL = "waiting_material"     # 等待材料
    COMPLAINED = "complained"                 # 已投诉
    SUED = "sued"                             # 已起诉
    COMPLETED = "completed"                   # 已完成
    CLOSED = "closed"                         # 已关闭


class LegalCaseTypeEnum(str, enum.Enum):
    """案例库案件类型（Legal Case Search 模块，面向裁判文书分类）。"""

    CIVIL = "civil"           # 民事
    LABOR = "labor"           # 劳动
    CONTRACT = "contract"     # 合同
    CONSUMER = "consumer"     # 消费
    OTHER = "other"           # 其他


class CourtLevelEnum(str, enum.Enum):
    """审理法院级别（用于案例库「法院级别」筛选）。"""

    BASIC = "basic"                 # 基层人民法院
    INTERMEDIATE = "intermediate"   # 中级人民法院
    ADVANCED = "advanced"           # 高级人民法院
    SUPREME = "supreme"             # 最高人民法院


# =====================================================================
# Evidence Intelligence Center（智能证据中心）专用枚举
# 以下均为追加定义，不修改任何既有枚举取值，确保既有功能不受影响。
# =====================================================================
class EvidenceFileCategoryEnum(str, enum.Enum):
    """智能证据中心：证据类型（AI 自动识别分类）。"""

    CONTRACT = "contract"           # 合同/协议
    PAYMENT = "payment"             # 付款/转账记录
    CHAT = "chat"                   # 聊天记录
    IDENTITY = "identity"           # 身份证明
    NOTICE = "notice"               # 通知/函件
    AUDIO = "audio"                 # 录音
    PHOTO = "photo"                 # 照片
    VIDEO = "video"                 # 视频
    EMAIL = "email"                 # 邮件
    WEBPAGE = "webpage"             # 网页截图
    DOCUMENT = "document"           # 文档/其他文件
    OTHER = "other"                 # 其他


class EvidenceFileStatusEnum(str, enum.Enum):
    """智能证据中心：证据处理状态（流水线）。"""

    UPLOADED = "uploaded"           # 已上传
    PROCESSING = "processing"       # 解析中
    OCR_DONE = "ocr_done"           # OCR 完成
    ANALYZED = "analyzed"           # AI 分析完成
    LINKED = "linked"               # 已关联案件/证据链


class EvidenceRelationTypeEnum(str, enum.Enum):
    """证据间关系类型（Evidence Graph 证据链）。"""

    SEQUENCE = "sequence"           # 时间先后
    SUPPORT = "support"             # 印证/佐证
    CONTRADICT = "contradict"       # 矛盾
    PREREQUISITE = "prerequisite"   # 前提/基础
    RELATED = "related"             # 一般关联


class EvidenceReportTypeEnum(str, enum.Enum):
    """证据报告类型。"""

    DIRECTORY = "directory"         # 证据目录
    SCORE = "score"                 # 证据评分报告
    MISSING = "missing"             # 证据缺失分析
    STRATEGY = "strategy"           # 证据策略
    FULL = "full"                   # 综合报告
