"""ORM 模型统一导入。

务必在此处导入所有模型模块，使它们在导入本包时被注册到
``Base.metadata``（Alembic 自动生成迁移、init_db 建表都依赖完整元数据）。
新增模型后请在此追加导入。
"""
from app.models.base import Base, TimestampMixin, UUIDMixin  # noqa: F401
from app.models.enums import (  # noqa: F401
    CaseCenterStatusEnum,
    CaseStatusEnum,
    CaseTypeEnum,
    DocStatusEnum,
    DocTypeEnum,
    EventTypeEnum,
    EvidenceCategoryEnum,
    LegalSourceEnum,
    MessageTypeEnum,
    PriorityEnum,
    RoleEnum,
    StepStatusEnum,
    TaskStatusEnum,
    WorkflowStageEnum,
)
from app.models.user import User  # noqa: F401
from app.models.case import Case  # noqa: F401
from app.models.message import Message  # noqa: F401
from app.models.document import Document  # noqa: F401
from app.models.evidence import Evidence  # noqa: F401
from app.models.roadmap import Roadmap, RoadmapStep  # noqa: F401
from app.models.legal_reference import LegalReference  # noqa: F401
from app.models.workflow import Workflow  # noqa: F401
from app.models.task import Task  # noqa: F401
from app.models.history import History  # noqa: F401
from app.models.knowledge import Knowledge  # noqa: F401
from app.models.law import Law, LawStatusEnum  # noqa: F401
from app.models.law_search_history import LawSearchHistory  # noqa: F401
from app.models.case_center import (  # noqa: F401
    CaseAnalysis,
    CaseCenter,
    CaseDocument,
    CaseEvidence,
    CaseNote,
    CaseTask,
    CaseTimeline,
)
from app.models.legal_case import (  # noqa: F401
    LegalCase,
    LegalCaseFavorite,
)
from app.models.research import (  # noqa: F401
    LegalDocument,
    JudicialInterpretation,
    DepartmentRule,
    LocalRegulation,
    Guideline,
    Policy,
)
from app.models.ai_center import (  # noqa: F401
    Provider,
    AIModel,
    RoutingRule,
    PromptTemplate,
    PromptVersion,
    ModelUsage,
    ModelLog,
    ModelHealth,
)
from app.models.playground import (  # noqa: F401
    PlaygroundSession,
    ModelComparison,
    EvaluationDataset,
    EvaluationItem,
    EvaluationTask,
    EvaluationResult,
    PromptLibrary,
    ModelPricing,
    PlaygroundPublish,
)
from app.models.contract import (  # noqa: F401
    Contract,
    ContractRisk,
    ContractClause,
    ContractReport,
    CONTRACT_TYPES,
    CONTRACT_TYPE_LABELS,
    CONTRACT_RISK_CATEGORIES,
    CONTRACT_RISK_LEVELS,
    CONTRACT_STATUS,
    CONTRACT_TASK_TYPES,
    CONTRACT_REMINDER_CATEGORIES,
    CONTRACT_REPORT_TYPES,
    CONTRACT_ALLOWED_EXTENSIONS,
)
from app.models.evidence_center import (  # noqa: F401
    EvidenceAnalysis,
    EvidenceFile,
    EvidenceRelation,
    EvidenceReport,
    EvidenceTimelineNode,
)

__all__ = [
    "Base",
    "UUIDMixin",
    "TimestampMixin",
    "User",
    "Case",
    "Message",
    "Document",
    "Evidence",
    "Roadmap",
    "RoadmapStep",
    "LegalReference",
    "Workflow",
    "Task",
    "History",
    "Knowledge",
    "Law",
    "LawStatusEnum",
    "LawSearchHistory",
    "CaseCenter",
    "CaseAnalysis",
    "CaseEvidence",
    "CaseDocument",
    "CaseTask",
    "CaseTimeline",
    "CaseNote",
    "LegalCase",
    "LegalCaseFavorite",
    "LegalDocument",
    "JudicialInterpretation",
    "DepartmentRule",
    "LocalRegulation",
    "Guideline",
    "Policy",
    "Provider",
    "AIModel",
    "RoutingRule",
    "PromptTemplate",
    "PromptVersion",
    "ModelUsage",
    "ModelLog",
    "ModelHealth",
    "PlaygroundSession",
    "ModelComparison",
    "EvaluationDataset",
    "EvaluationItem",
    "EvaluationTask",
    "EvaluationResult",
    "PromptLibrary",
    "ModelPricing",
    "PlaygroundPublish",
    "Contract",
    "ContractRisk",
    "ContractClause",
    "ContractReport",
    "ContractTask",
    "CONTRACT_TYPES",
    "CONTRACT_TYPE_LABELS",
    "CONTRACT_RISK_CATEGORIES",
    "CONTRACT_RISK_LEVELS",
    "CONTRACT_STATUS",
    "CONTRACT_TASK_TYPES",
    "CONTRACT_REMINDER_CATEGORIES",
    "CONTRACT_REPORT_TYPES",
    "CONTRACT_ALLOWED_EXTENSIONS",
    "EvidenceFile",
    "EvidenceAnalysis",
    "EvidenceRelation",
    "EvidenceTimelineNode",
    "EvidenceReport",
]
