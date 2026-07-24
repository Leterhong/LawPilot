// 枚举值 -> 中文标签映射（与后端 enums.py 取值保持一致）
import type {
  CaseType,
  CaseStatus,
  CaseCenterStatus,
  DocType,
  EvidenceCategory,
  StepStatus,
  TaskStatus,
  Priority,
  EventType,
  EvidenceFileCategory,
  EvidenceFileStatus,
  EvidenceRelationType,
  EvidenceReportType,
} from "./api";

export const caseTypeLabels: Record<CaseType, string> = {
  rent: "房屋租赁",
  labor: "劳动纠纷",
  consumer: "消费维权",
  loan: "借贷纠纷",
  marriage: "婚姻纠纷",
  medical: "医疗纠纷",
  express: "快递物流",
  other: "其他",
};

export const caseStatusLabels: Record<CaseStatus, string> = {
  intake: "录入中",
  collecting: "收集证据中",
  analyzing: "分析中",
  in_progress: "办理中",
  completed: "已办结",
  closed: "已关闭",
};

// 案件中心状态（8 档）
export const caseCenterStatusLabels: Record<CaseCenterStatus, string> = {
  pending: "待处理",
  in_progress: "处理中",
  waiting_reply: "等待回复",
  waiting_material: "等待材料",
  complained: "已投诉",
  sued: "已起诉",
  completed: "已完成",
  closed: "已关闭",
};

// 案件中心状态 -> Badge 配色（与 ui.tsx Badge tone 取值一致）
export const caseCenterStatusTone: Record<
  CaseCenterStatus,
  "brand" | "gray" | "green" | "red" | "amber"
> = {
  pending: "gray",
  in_progress: "brand",
  waiting_reply: "amber",
  waiting_material: "amber",
  complained: "green",
  sued: "red",
  completed: "green",
  closed: "red",
};

export const docTypeLabels: Record<DocType, string> = {
  dunning_letter: "催告函",
  lawyer_letter: "律师函",
  complaint: "投诉书",
  arbitration: "仲裁申请书",
  lawsuit: "起诉状",
  defense: "答辩状",
  evidence_list: "证据目录",
};

export const evidenceCategoryLabels: Record<EvidenceCategory, string> = {
  contract: "合同",
  chat_record: "聊天记录",
  payment_record: "付款记录",
  photo: "照片",
  video: "视频",
  audio: "录音",
  other: "其他",
};

export const stepStatusLabels: Record<StepStatus, string> = {
  pending: "待办",
  done: "已完成",
  skipped: "已跳过",
};

export const taskStatusLabels: Record<TaskStatus, string> = {
  todo: "待办",
  in_progress: "进行中",
  done: "已完成",
  cancelled: "已取消",
};

export const priorityLabels: Record<Priority, string> = {
  low: "低",
  medium: "中",
  high: "高",
};

export const eventTypeLabels: Record<EventType, string> = {
  created: "创建",
  message: "消息",
  evidence_added: "证据",
  report_generated: "报告",
  document_generated: "文书",
  status_changed: "状态",
  task_done: "任务",
  reminder: "提醒",
};

// 法条现状标签（与后端 LawStatusEnum 取值一致）
export const lawStatusLabels: Record<string, string> = {
  effective: "现行有效",
  amended: "已被修正",
  repealed: "已废止",
  pending: "尚未施行",
};

// ---------------------------
// 案例智能搜索（Legal Case Search）
// ---------------------------
// 案件类型（与后端 LegalCaseTypeEnum 取值一致）
export const legalCaseTypeLabels: Record<string, string> = {
  civil: "民事纠纷",
  labor: "劳动争议",
  contract: "合同纠纷",
  consumer: "消费维权",
  other: "其他",
};

// 案件类型 -> Badge 配色（与 ui.tsx Badge tone 取值一致）
export const legalCaseTypeTone: Record<
  string,
  "brand" | "gray" | "green" | "red" | "amber"
> = {
  civil: "brand",
  labor: "amber",
  contract: "green",
  consumer: "red",
  other: "gray",
};

// 法院级别（与后端 CourtLevelEnum 取值一致）
export const courtLevelLabels: Record<string, string> = {
  basic: "基层法院",
  intermediate: "中级法院",
  advanced: "高级法院",
  supreme: "最高法院",
};

// 时间范围（与后端 /search time_range 取值一致）
export const timeRangeLabels: Record<string, string> = {
  "1y": "近一年",
  "5y": "近五年",
  all: "全部时间",
};

// 首页四个快捷入口
export const quickEntries: {
  type: CaseType;
  label: string;
  hint: string;
  icon: "home" | "briefcase" | "shopping" | "banknote";
}[] = [
  { type: "rent", label: "房屋租赁", hint: "押金 / 退租 / 维修", icon: "home" },
  { type: "labor", label: "劳动纠纷", hint: "欠薪 / 辞退 / 合同", icon: "briefcase" },
  { type: "consumer", label: "消费维权", hint: "虚假宣传 / 退款", icon: "shopping" },
  { type: "loan", label: "借贷纠纷", hint: "借钱不还 / 利息", icon: "banknote" },
];

// ---------------------------
// 法律研究中心（Legal Research Center）
// ---------------------------
// 九大类资源与后端过滤（doc_type / category）映射
export interface ResearchCategoryDef {
  key: string;
  label: string;
  doc_type?: string;
  category?: string;
}

export const researchCategories: ResearchCategoryDef[] = [
  { key: "law", label: "法律", doc_type: "legal_document", category: "法律" },
  { key: "admin_reg", label: "行政法规", doc_type: "legal_document", category: "行政法规" },
  { key: "guiding_case", label: "指导性案例", doc_type: "legal_document", category: "指导性案例" },
  { key: "typical_case", label: "典型案例", doc_type: "legal_document", category: "典型案例" },
  { key: "judicial", label: "司法解释", doc_type: "judicial_interpretation" },
  { key: "dept_rule", label: "部门规章", doc_type: "department_rule" },
  { key: "local_reg", label: "地方性法规", doc_type: "local_regulation" },
  { key: "guide", label: "办事指南", doc_type: "guideline" },
  { key: "policy", label: "政策文件", doc_type: "policy" },
];

// 文档类型 -> 中文标签（与后端 DOC_TYPE_LABELS 一致）
export const researchDocTypeLabels: Record<string, string> = {
  legal_document: "法律法规",
  judicial_interpretation: "司法解释",
  department_rule: "部门规章",
  local_regulation: "地方性法规",
  guideline: "办事指南",
  policy: "政策文件",
};

// 分类 -> 中文标签（与后端 CATEGORY_LABELS 一致）
export const researchCategoryLabels: Record<string, string> = {
  法律: "法律",
  行政法规: "行政法规",
  指导性案例: "指导性案例",
  典型案例: "典型案例",
  司法解释: "司法解释",
  部门规章: "部门规章",
  地方性法规: "地方性法规",
  办事指南: "办事指南",
  政策文件: "政策文件",
};

// 文档类型 -> Badge 配色（与 ui.tsx Badge tone 取值一致）
export const researchDocTypeTone: Record<
  string,
  "brand" | "gray" | "green" | "red" | "amber"
> = {
  legal_document: "brand",
  judicial_interpretation: "amber",
  department_rule: "green",
  local_regulation: "red",
  guideline: "gray",
  policy: "amber",
};

// 检索模式（与后端 search_mode 取值一致）
export const researchSearchModes: { value: string; label: string }[] = [
  { value: "auto", label: "自动" },
  { value: "full_text", label: "全文" },
  { value: "semantic", label: "语义" },
];

// 热门检索（首屏引导）
export const researchHotQueries: string[] = [
  "合同",
  "劳动合同",
  "婚姻",
  "离婚",
  "知识产权",
  "消费者权益",
];

// ---------------------------
// AI 能力中心（AI Capability Center）标签映射
// ---------------------------
// Provider 类型 -> 中文标签（与后端 PROVIDER_TYPES 取值一致）
export const aiProviderTypeLabels: Record<string, string> = {
  openai_compatible: "OpenAI Compatible",
  openai: "OpenAI",
  anthropic: "Anthropic",
  gemini: "Google Gemini",
  azure: "Azure OpenAI",
  openrouter: "OpenRouter",
  siliconflow: "硅基流动",
  bailian: "阿里百炼",
  volcano: "火山方舟",
  zhipu: "智谱 AI",
  moonshot: "Moonshot",
  deepseek: "DeepSeek",
  ollama: "Ollama",
  lmstudio: "LM Studio",
  vllm: "vLLM",
  xinference: "Xinference",
  custom: "自定义",
};

// AI 功能 -> 中文标签（与后端 AI_FEATURES 取值一致）
export const aiFeatureLabels: Record<string, string> = {
  legal_analysis: "法律分析",
  law_explain: "法条解释",
  case_summary: "案例总结",
  case_search: "案例搜索",
  case_overview: "案件总结",
  contract_review: "合同审查",
  ocr_analysis: "OCR 分析",
  image_understanding: "图片理解",
  document_generation: "法律文书生成",
  prompt_optimize: "Prompt 优化",
  workflow_planning: "Workflow 规划",
  agent_reasoning: "Agent 推理",
  embedding: "Embedding",
  reranker: "Reranker",
  web_search: "联网搜索",
  chat: "聊天",
  timeline_generation: "时间线生成",
  evidence_analysis: "证据分析",
};

// 路由策略 -> 中文标签（与后端 ROUTING_STRATEGIES 取值一致）
export const aiStrategyLabels: Record<string, string> = {
  lowest_cost: "最低成本",
  fastest: "最快速度",
  highest_quality: "最高质量",
  balanced: "自动均衡",
  custom: "自定义",
};

// 能力键 -> 中文标签（与后端 CAPABILITY_KEYS 取值一致）
export const aiCapabilityLabels: Record<string, string> = {
  chat: "对话",
  embedding: "向量",
  vision: "视觉",
  streaming: "流式",
  json_mode: "JSON 模式",
  function_calling: "函数调用",
  web_search: "联网搜索",
  reasoning: "推理",
};

// AI 中心侧边栏七个模块
export interface AICenterModule {
  key: string;
  label: string;
  desc: string;
}
export const aiCenterModules: AICenterModule[] = [
  { key: "models", label: "模型管理", desc: "添加 / 编辑 / 测试 / 删除模型" },
  { key: "providers", label: "Provider 管理", desc: "管理多家兼容 Provider" },
  { key: "routing", label: "路由规则", desc: "为每个 AI 功能指定模型与策略" },
  { key: "prompts", label: "Prompt 管理", desc: "模板 / 版本 / 变量" },
  { key: "stats", label: "Token 统计", desc: "用量 / 费用 / 失败率" },
  { key: "logs", label: "日志中心", desc: "调用明细与错误" },
  { key: "health", label: "健康检测", desc: "模型能力探测" },
];

// ---------------------------
// AI Playground（AI 模型测试中心）标签映射
// ---------------------------
// 评分维度 -> 中文标签（与后端 SCORE_DIMS / scorer 取值一致）
export const scoreDimLabels: Record<string, string> = {
  accuracy: "准确性",
  completeness: "完整性",
  professionalism: "专业性",
  logic: "逻辑性",
  format: "格式",
  citation: "引用质量",
  total: "总分",
};

// ---------------------------
// 合同智能中心（Contract Intelligence Center）标签映射
// 取值与后端 contract.py 常量保持一致
// ---------------------------
// 合同类型 -> 中文标签（与后端 CONTRACT_TYPES 取值一致）
export const contractTypeLabels: Record<string, string> = {
  rent: "租赁合同",
  labor: "劳动合同",
  sales: "买卖合同",
  service: "服务合同",
  nda: "保密协议",
  cooperation: "合作协议",
  loan: "借款合同",
  purchase: "采购合同",
  other: "其他",
};

// 合同状态 -> 中文标签（与后端 CONTRACT_STATUS 取值一致）
export const contractStatusLabels: Record<string, string> = {
  uploaded: "已解析",
  parsing: "解析中",
  analyzed: "已分析",
  error: "解析失败",
};

// 合同状态 -> Badge 配色（与 ui.tsx Badge tone 取值一致）
export const contractStatusTone: Record<
  string,
  "brand" | "gray" | "green" | "red" | "amber"
> = {
  uploaded: "gray",
  parsing: "amber",
  analyzed: "green",
  error: "red",
};

// 风险等级 -> 中文标签
export const contractRiskLevelLabels: Record<string, string> = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",
};

// 风险等级 -> Badge 配色（与 ui.tsx Badge tone 取值一致）
export const contractRiskLevelTone: Record<
  string,
  "brand" | "gray" | "green" | "red" | "amber"
> = {
  low: "green",
  medium: "amber",
  high: "red",
};

// 风险分类 -> 中文标签（与后端 CONTRACT_RISK_CATEGORIES 取值一致）
export const contractRiskCategoryLabels: Record<string, string> = {
  payment: "付款",
  breach: "违约",
  confidentiality: "保密",
  ip: "知识产权",
  termination: "解除合同",
  liability: "赔偿责任",
  force_majeure: "不可抗力",
  dispute: "争议解决",
};

// 合同中心支持的文件类型（与后端 CONTRACT_ALLOWED_EXTENSIONS 一致）
export const contractAllowedExtensions = [
  ".pdf",
  ".docx",
  ".txt",
  ".md",
  ".png",
  ".jpg",
  ".jpeg",
];

// 提醒 / 待办分类 -> 中文标签（与后端 CONTRACT_REMINDER_CATEGORIES 取值一致）
export const contractReminderCategoryLabels: Record<string, string> = {
  expiry: "到期",
  payment: "付款",
  renewal: "续约",
  sign_check: "签批",
  other: "其他",
};

// 提醒分类 -> Badge 配色（与 ui.tsx Badge tone 取值一致）
export const contractReminderCategoryTone: Record<
  string,
  "brand" | "gray" | "green" | "red" | "amber"
> = {
  expiry: "red",
  payment: "amber",
  renewal: "brand",
  sign_check: "gray",
  other: "gray",
};

// 提醒 / 待办优先级 -> 中文标签
export const contractPriorityLabels: Record<string, string> = {
  low: "低",
  normal: "普通",
  high: "高",
  urgent: "紧急",
};

// 提醒优先级 -> Badge 配色
export const contractPriorityTone: Record<
  string,
  "brand" | "gray" | "green" | "red" | "amber"
> = {
  low: "gray",
  normal: "brand",
  high: "amber",
  urgent: "red",
};

// 提醒 / 待办类型 -> 中文标签
export const contractTaskTypeLabels: Record<string, string> = {
  reminder: "提醒",
  checklist: "待办",
};

// Playground 侧边栏七个模块（5 种测试模式 + 历史 + 收藏）
export interface PlaygroundModule {
  key: string;
  label: string;
  desc: string;
}
export const playgroundModules: PlaygroundModule[] = [
  { key: "single", label: "单模型测试", desc: "选定单个模型跑通一次对话，查看 Token / 延迟 / 成本" },
  { key: "compare", label: "多模型对比", desc: "一次提问多模型并行，AI 自动评分横向比较" },
  { key: "prompt", label: "Prompt 测试", desc: "变量化 Prompt，对比不同写法效果" },
  { key: "eval", label: "模型评测", desc: "基于测试集批量评测，生成报告" },
  { key: "routing", label: "AI 路由测试", desc: "查看当前路由规则，比较候选模型并一键应用到生产" },
  { key: "history", label: "测试历史", desc: "所有测试会话留痕，可回看" },
  { key: "library", label: "我的收藏", desc: "收藏优秀 Prompt 与变量定义" },
];

// ---------------------------
// 智能证据中心（Evidence Intelligence Center）标签映射
// 取值与后端 models/enums.py 的 Evidence*Enum 保持一致
// ---------------------------
// 证据类型 -> 中文标签（与后端 EvidenceFileCategoryEnum 取值一致）
export const evidenceFileCategoryLabels: Record<EvidenceFileCategory, string> = {
  contract: "合同",
  payment: "付款/转账",
  chat: "聊天记录",
  identity: "身份证明",
  notice: "通知/函件",
  audio: "录音",
  photo: "照片",
  video: "视频",
  email: "邮件",
  webpage: "网页截图",
  document: "文档",
  other: "其他",
};

// 证据类型 -> Badge 配色（与 ui.tsx Badge tone 取值一致）
export const evidenceFileCategoryTone: Record<
  EvidenceFileCategory,
  "brand" | "gray" | "green" | "red" | "amber"
> = {
  contract: "brand",
  payment: "green",
  chat: "gray",
  identity: "amber",
  notice: "gray",
  audio: "gray",
  photo: "green",
  video: "brand",
  email: "gray",
  webpage: "gray",
  document: "gray",
  other: "gray",
};

// 证据处理状态 -> 中文标签（与后端 EvidenceFileStatusEnum 取值一致）
export const evidenceFileStatusLabels: Record<EvidenceFileStatus, string> = {
  uploaded: "已上传",
  processing: "解析中",
  ocr_done: "OCR 完成",
  analyzed: "已分析",
  linked: "已关联",
};

// 证据处理状态 -> Badge 配色（与 ui.tsx Badge tone 取值一致）
export const evidenceFileStatusTone: Record<
  EvidenceFileStatus,
  "brand" | "gray" | "green" | "red" | "amber"
> = {
  uploaded: "gray",
  processing: "amber",
  ocr_done: "amber",
  analyzed: "green",
  linked: "brand",
};

// 证据间关系类型 -> 中文标签（与后端 EvidenceRelationTypeEnum 取值一致）
export const evidenceRelationLabels: Record<EvidenceRelationType, string> = {
  sequence: "时间先后",
  support: "印证/佐证",
  contradict: "矛盾",
  prerequisite: "前提/基础",
  related: "一般关联",
};

// 证据间关系类型 -> Badge 配色（与 ui.tsx Badge tone 取值一致）
export const evidenceRelationTone: Record<
  EvidenceRelationType,
  "brand" | "gray" | "green" | "red" | "amber"
> = {
  sequence: "gray",
  support: "green",
  contradict: "red",
  prerequisite: "amber",
  related: "brand",
};

// 证据报告类型 -> 中文标签（与后端 EvidenceReportTypeEnum 取值一致）
export const evidenceReportLabels: Record<EvidenceReportType, string> = {
  directory: "证据目录",
  score: "证据评分",
  missing: "缺失分析",
  strategy: "证据策略",
  full: "综合报告",
};

// 证据中心支持的文件扩展名（与后端 EVIDENCE_ALLOWED_EXTENSIONS 一致）
export const evidenceAllowedExtensions: string[] = [
  ".pdf",
  ".doc",
  ".docx",
  ".txt",
  ".md",
  ".rtf",
  ".png",
  ".jpg",
  ".jpeg",
  ".gif",
  ".webp",
  ".bmp",
  ".tif",
  ".tiff",
  ".heic",
  ".mp3",
  ".wav",
  ".m4a",
  ".aac",
  ".ogg",
  ".mp4",
  ".mov",
  ".avi",
  ".webm",
  ".mkv",
  ".eml",
  ".msg",
  ".html",
  ".htm",
];
