// LawPilot 前端 API 客户端。
// 封装对后端 /api/v1 的调用，提供与后端 Pydantic Schema 对应的 TS 类型。
// 所有需鉴权的请求自动附带 localStorage 中的 Bearer Token。

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ---------------------------
// 类型定义（与后端 Schema 对齐）
// ---------------------------
export type CaseType =
  | "rent"
  | "labor"
  | "consumer"
  | "loan"
  | "marriage"
  | "medical"
  | "express"
  | "other";

export type CaseStatus =
  | "intake"
  | "collecting"
  | "analyzing"
  | "in_progress"
  | "completed"
  | "closed";

export type Role = "user" | "assistant" | "system";
export type MessageType = "text" | "quick_reply" | "document" | "system_event";
export type DocType =
  | "dunning_letter"
  | "lawyer_letter"
  | "complaint"
  | "arbitration"
  | "lawsuit"
  | "defense"
  | "evidence_list";
export type DocStatus = "draft" | "generated" | "finalized";
export type EvidenceCategory =
  | "contract"
  | "chat_record"
  | "payment_record"
  | "photo"
  | "video"
  | "audio"
  | "other";
export type StepStatus = "pending" | "done" | "skipped";
export type TaskStatus = "todo" | "in_progress" | "done" | "cancelled";
export type Priority = "low" | "medium" | "high";

// 案件中心状态（8 档，面向用户办事视角；与 Phase1 CaseStatus 不同）
export type CaseCenterStatus =
  | "pending"
  | "in_progress"
  | "waiting_reply"
  | "waiting_material"
  | "complained"
  | "sued"
  | "completed"
  | "closed";
export type EventType =
  | "created"
  | "message"
  | "evidence_added"
  | "report_generated"
  | "document_generated"
  | "status_changed"
  | "task_done"
  | "reminder";
export type LegalSource =
  | "law"
  | "judicial_interpretation"
  | "admin_regulation"
  | "local_regulation"
  | "guiding_case"
  | "typical_case"
  | "guide"
  | "policy";

export interface UserOut {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  is_active: boolean;
  is_verified: boolean;
  is_superuser: boolean;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface CaseOut {
  id: string;
  user_id: string;
  title: string;
  case_type: CaseType;
  status: CaseStatus;
  description: string | null;
  summary: string | null;
  conclusion: string | null;
  rights_analysis: string | null;
  counterparty_issues: string | null;
  risk_analysis: Record<string, unknown> | null;
  recommended_departments: Record<string, unknown> | null;
  current_stage: string | null;
  report: CaseReport | null;
  legal_references: LegalCitation[] | null;
  report_generated_at: string | null;
  created_at: string;
  updated_at: string;
}

// 案件报告（Agent 生成，11 章节）
export interface LegalCitation {
  id: string;
  source_table: string;
  source: LegalSource;
  label: string;
  title: string;
  article: string | null;
  snippet: string;
  score: number;
}
export interface CaseReport {
  case_type: string;
  conclusion: string;
  /** 事实梳理：由逐条追问收集到的结构化事实还原而成（v1.1 新增） */
  facts?: string[];
  legal: {
    query: string;
    markdown: string;
    citations: LegalCitation[];
    note: string;
  };
  rights: string;
  counterparty_issues: string;
  evidence: { uploaded: string[]; checklist: string[]; advice?: string };
  next_steps: {
    order: number;
    title: string;
    description: string | null;
    due_offset_days: number | null;
    status: string;
  }[];
  where_to_go: { name: string; reason: string }[];
  documents: { type: DocType; label: string }[];
  risk: {
    evidence_completeness: string;
    complexity: string;
    limitation: string;
    suggestion: string;
  };
  /** 生成溯源：用于界面上标注本报告的生成方式与引用轨迹（v1.1 新增） */
  meta?: {
    analysis_source: "llm" | "template";
    fallback_reason: string;
    cited_articles: number[];
    fact_count: number;
    citation_count: number;
  };
  disclaimer: string;
  generated_at: string;
}

export interface WorkflowOut {
  stage: string;
  collected_fields: Record<string, unknown> | null;
  missing_fields: string[] | null;
  next_question: string | null;
  is_complete: boolean;
  updated_at: string;
}

export interface ChatResponse {
  assistant_message: MessageOut;
  case: CaseOut;
  workflow: WorkflowOut;
  report_generated: boolean;
  suggested_evidence: string[];
  available_documents: { type: DocType; label: string }[];
}

export interface AgentStateResponse {
  case: CaseOut;
  workflow: WorkflowOut;
  messages: MessageOut[];
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface MessageOut {
  id: string;
  case_id: string;
  role: Role;
  message_type: MessageType;
  content: string;
  sequence: number;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
}

export interface EvidenceOut {
  id: string;
  case_id: string;
  user_id: string | null;
  category: EvidenceCategory;
  title: string;
  description: string | null;
  file_path: string | null;
  file_type: string | null;
  ocr_text: string | null;
  is_uploaded: boolean;
  ai_note: string | null;
  created_at: string;
}

export interface DocumentOut {
  id: string;
  case_id: string | null;
  user_id: string | null;
  doc_type: DocType;
  title: string;
  content: string;
  status: DocStatus;
  created_at: string;
}

export interface RoadmapStepOut {
  id: string;
  roadmap_id: string;
  title: string;
  description: string | null;
  order: number;
  due_offset_days: number | null;
  status: StepStatus;
  completed_at: string | null;
  created_at: string;
}

export interface RoadmapOut {
  id: string;
  case_id: string;
  title: string;
  is_active: boolean;
  steps: RoadmapStepOut[];
  created_at: string;
  updated_at: string;
}

export interface TaskOut {
  id: string;
  case_id: string;
  user_id: string | null;
  title: string;
  description: string | null;
  due_date: string | null;
  status: TaskStatus;
  priority: Priority;
  created_at: string;
  updated_at: string;
}

export interface HistoryOut {
  id: string;
  case_id: string;
  user_id: string | null;
  event_type: EventType;
  title: string;
  detail: string | null;
  created_at: string;
}

export interface LegalReferenceOut {
  id: string;
  source: LegalSource;
  title: string;
  article: string | null;
  content: string;
  explanation: string | null;
  jurisdiction: string | null;
  effective_date: string | null;
  extra: Record<string, unknown> | null;
}

export interface KnowledgeOut {
  id: string;
  category: LegalSource;
  title: string;
  content: string;
  source_url: string | null;
  tags: string[] | null;
}

export interface LegalSearchResult {
  references: LegalReferenceOut[];
  references_total: number;
  knowledge: KnowledgeOut[];
  knowledge_total: number;
}

// ---------------------------
// 法律搜索（Law Search 模块）
// ---------------------------
export type LawStatus = "effective" | "amended" | "repealed" | "pending";

export interface LawOut {
  id: string;
  law_name: string;
  chapter: string | null;
  section: string | null;
  article: string | null;
  content: string;
  keywords: string[] | null;
  effective_date: string | null;
  status: LawStatus | string;
  source: string | null;
}

export interface LawSearchItem extends LawOut {
  snippet: string | null;
  score: number | null;
  highlight: Record<string, string> | null;
}

export interface LawSearchResult {
  query: string;
  total: number;
  items: LawSearchItem[];
  parsed: {
    law_name?: string;
    article?: string;
    terms?: string[];
  } | null;
}

export interface LawDetail extends LawOut {
  ai_explanation: string | null;
  prev: LawOut | null;
  next: LawOut | null;
  related_laws: LawOut[];
  related_interpretations: {
    id: string;
    source: string;
    title: string;
    article: string | null;
    snippet: string;
  }[];
  related_cases: {
    id: string;
    source: string;
    title: string;
    article: string | null;
    snippet: string;
  }[];
  recommendations: LawOut[];
}

export interface LawHistoryOut {
  id: string;
  user_id: string | null;
  query: string;
  result_count: number | null;
  created_at: string;
}

// ---------------------------
// 案例智能搜索（Legal Case Search 模块，/api/legal-cases）
// ---------------------------
export type LegalCaseType = "civil" | "labor" | "contract" | "consumer" | "other";
export type CourtLevel = "basic" | "intermediate" | "advanced" | "supreme";

export interface LegalCaseOut {
  id: string;
  title: string;
  case_number: string | null;
  court: string | null;
  province: string | null;
  city: string | null;
  trial_date: string | null;
  case_type: LegalCaseType | string;
  court_level: CourtLevel | string | null;
  cause_of_action: string | null;
  plaintiff: string | null;
  defendant: string | null;
  winner: string | null;
  compensation: string | null;
  keywords: string[] | null;
  related_laws: string[] | null;
  source: string | null;
}

export interface LegalCaseSearchItem extends LegalCaseOut {
  snippet: string | null;
  score: number | null;
  highlight: Record<string, string> | null;
}

export interface LegalCaseSearchResult {
  query: string;
  total: number;
  items: LegalCaseSearchItem[];
  parsed: Record<string, unknown> | null;
  filters: Record<string, unknown> | null;
}

export interface LegalCaseAiSummary {
  similar_points: string | null;
  different_points: string | null;
  reference_value: string | null;
  raw: string | null;
}

// 详情：related_laws 被后端覆盖为可链法条对象数组，故用 Omit 排除基类的 string[]
export interface LegalCaseDetail extends Omit<LegalCaseOut, "related_laws"> {
  facts: string | null;
  court_reasoning: string | null;
  judgement: string | null;
  related_laws: LawOut[];
  related_law_citations: string[] | null;
  ai_summary: LegalCaseAiSummary | null;
}

export interface FacetItem {
  value: string;
  label: string;
}

// ---------------------------
// 法律研究中心（Legal Research Center，/api/research）
// ---------------------------
export type ResearchDocType =
  | "legal_document"
  | "judicial_interpretation"
  | "department_rule"
  | "local_regulation"
  | "guideline"
  | "policy";

export interface ResearchSearchItem {
  id: string;
  doc_type: ResearchDocType;
  title: string;
  doc_number: string | null;
  category: string;
  summary_one_line: string | null;
  core_points: string[] | null;
  scope: string | null;
  common_misconceptions: string[] | null;
  publish_date: string | null;
  effective_date: string | null;
  expiry_date: string | null;
  is_current: boolean;
  source: string | null;
  level: string | null;
  region: string | null;
  issuing_authority: string | null;
  keywords: string[] | null;
  related_law_ids: string[] | null;
  related_case_ids: string[] | null;
  related_interpretation_ids: string[] | null;
  snippet: string | null;
  score: number | null;
  highlight: { title: string; snippet: string } | null;
  category_label: string | null;
  doc_type_label: string | null;
}

export interface ResearchSearchResult {
  query: string;
  total: number;
  items: ResearchSearchItem[];
  parsed: {
    terms?: string[];
    mode?: string;
    boolean?: boolean;
    filters?: Record<string, unknown>;
  } | null;
  filters: Record<string, unknown> | null;
  facets: Record<string, { label: string; count: number }> | null;
}

export interface RelatedDocRef {
  id: string;
  doc_type: ResearchDocType;
  title: string;
  category: string;
  summary_one_line: string | null;
}

export interface ResearchDocDetail {
  id: string;
  doc_type: ResearchDocType;
  title: string;
  doc_number: string | null;
  category: string;
  summary_one_line: string | null;
  core_points: string[] | null;
  scope: string | null;
  common_misconceptions: string[] | null;
  publish_date: string | null;
  effective_date: string | null;
  expiry_date: string | null;
  is_current: boolean;
  source: string | null;
  level: string | null;
  region: string | null;
  issuing_authority: string | null;
  keywords: string[] | null;
  related_law_ids: string[] | null;
  related_case_ids: string[] | null;
  related_interpretation_ids: string[] | null;
  full_text: string | null;
  related_docs: RelatedDocRef[];
  ai_explanation: string | null;
  ai_summary: string | null;
  category_label: string | null;
  doc_type_label: string | null;
}

export interface ResearchRecommendResult {
  query: string;
  seed_id: string | null;
  total: number;
  items: ResearchSearchItem[];
}

export interface CaseFilterFacets {
  provinces: string[];
  cities: string[];
  court_levels: FacetItem[];
  case_types: FacetItem[];
  time_ranges: FacetItem[];
}

// ---------------------------
// AI 能力中心（AI Capability Center，/api/ai）
// ---------------------------
export interface ProviderOut {
  id: string;
  name: string;
  type: string;
  base_url: string | null;
  api_key: string | null;
  enabled: boolean;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface AIModelOut {
  id: string;
  name: string;
  provider_id: string | null;
  provider_name: string | null;
  provider_type: string | null;
  api_key: string | null;
  base_url: string | null;
  model_name: string;
  embedding_model: string | null;
  vision_model: string | null;
  reranker_model: string | null;
  embedding_dim: number | null;
  temperature: number;
  top_p: number;
  timeout: number;
  max_tokens: number | null;
  is_default: boolean;
  is_enabled: boolean;
  capabilities: Record<string, boolean>;
  advanced: Record<string, number>;
  created_at: string;
  updated_at: string;
}

export interface RoutingRuleOut {
  id: string;
  feature: string;
  model_id: string;
  model_name: string | null;
  fallback_model_ids: string[] | null;
  strategy: string;
  auto_route: boolean;
  prompt_template_key: string | null;
  priority: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface PromptTemplateOut {
  id: string;
  key: string;
  name: string;
  content: string;
  variables: Record<string, unknown>[] | null;
  enabled: boolean;
  current_version: number;
  model_id: string | null;
  model_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface PromptVersionOut {
  id: string;
  template_id: string;
  version: number;
  content: string;
  variables: Record<string, unknown>[] | null;
  note: string | null;
  created_by: string | null;
  created_at: string;
}

export interface TestConnectionResult {
  status: string;
  capability: string;
  latency_ms: number | null;
  capabilities_detected: string[];
  model: string | null;
  provider_type: string | null;
  error: string | null;
}

export interface ModelUsageRow {
  date: string;
  model_id: string | null;
  model_name: string | null;
  tokens_in: number;
  tokens_out: number;
  cost: number | string;
  cost_currency: string;
  calls: number;
  failures: number;
  avg_latency_ms: number;
  failure_rate: number;
}

export interface StatisticsOut {
  per_day: ModelUsageRow[];
  per_model: ModelUsageRow[];
  totals: Record<string, number | string>;
  range: Record<string, string>;
}

export interface ModelLogOut {
  id: string;
  model_id: string | null;
  model_name: string | null;
  provider_id: string | null;
  user_id: string | null;
  feature: string | null;
  endpoint: string | null;
  capability: string | null;
  tokens_in: number;
  tokens_out: number;
  cost: number | string;
  latency_ms: number;
  status: string;
  error_text: string | null;
  created_at: string;
}

export interface ModelHealthOut {
  id: string;
  model_id: string;
  model_name: string | null;
  provider_id: string | null;
  last_checked: string | null;
  chat_ok: boolean | null;
  vision_ok: boolean | null;
  embedding_ok: boolean | null;
  streaming_ok: boolean | null;
  json_ok: boolean | null;
  function_calling_ok: boolean | null;
  web_ok: boolean | null;
  status: string | null;
  latency_ms: number | null;
  error_text: string | null;
  created_at: string;
}

export interface AIMeta {
  provider_types: string[];
  features: string[];
  strategies: string[];
  capability_keys: string[];
}

// ---------------------------
// AI Playground（AI 模型测试中心，/api/playground）
// ---------------------------
export interface PlaygroundModelOut {
  id: string;
  name: string;
  provider_id: string | null;
  provider_name: string | null;
  capabilities: Record<string, boolean>;
  is_enabled: boolean;
}

export interface ChatResultOut {
  model_id: string | null;
  model_name: string | null;
  provider_name: string | null;
  content: string | null;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  cost: number | null;
  error: string | null;
}

export interface CompareRowOut {
  model_id: string | null;
  model_name: string | null;
  provider_name: string | null;
  content: string | null;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  cost: number | null;
  score: number | null;
  score_detail: Record<string, number> | null;
  status: string;
  error: string | null;
}

export interface PlaygroundSessionOut {
  id: string;
  user_id: string | null;
  type: string;
  title: string | null;
  model_ids: string[] | null;
  feature: string | null;
  system_prompt: string | null;
  user_prompt: string | null;
  context: string | null;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  score: number | null;
  score_detail: Record<string, number> | null;
  token_usage: Record<string, unknown> | null;
  latency_ms: number;
  status: string;
  error_text: string | null;
  created_at: string;
}

export interface EvaluationTaskOut {
  id: string;
  user_id: string | null;
  name: string;
  model_ids: string[];
  judge_model_id: string | null;
  feature: string | null;
  status: string;
  total_items: number;
  processed_items: number;
  score_summary: Record<string, unknown> | null;
  created_at: string;
}

export interface EvaluationResultOut {
  id: string;
  task_id: string;
  item_id: string | null;
  model_id: string | null;
  input: string | null;
  expected: string | null;
  output: string | null;
  is_correct: boolean | null;
  is_json_valid: boolean | null;
  has_hallucination: boolean | null;
  score: number | null;
  metrics: Record<string, number> | null;
  latency_ms: number;
  tokens_in: number;
  tokens_out: number;
  cost: number;
  error_text: string | null;
  created_at: string;
}

export interface EvaluationDatasetOut {
  id: string;
  user_id: string | null;
  name: string;
  category: string | null;
  description: string | null;
  is_public: boolean;
  item_count: number;
  created_at: string;
}

export interface EvaluationItemOut {
  id: string;
  dataset_id: string;
  input: string;
  expected: string | null;
  context: string | null;
  order_index: number;
}

export interface PromptLibraryOut {
  id: string;
  user_id: string | null;
  name: string;
  category: string | null;
  prompt: string;
  variables: string[] | null;
  score: number | null;
  tags: string[] | null;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface PlaygroundPublishOut {
  id: string;
  feature: string;
  from_model_id: string | null;
  to_model_id: string | null;
  routing_rule_id: string | null;
  note: string | null;
  created_at: string;
}

export interface RoutingRuleSimpleOut {
  feature: string;
  model_id: string;
  model_name: string | null;
  enabled: boolean;
}

// ---------------------------
// 合同智能中心（Contract Intelligence Center，/api/contracts）
// ---------------------------
export type ContractType =
  | "rent"
  | "labor"
  | "sales"
  | "service"
  | "nda"
  | "cooperation"
  | "loan"
  | "purchase"
  | "other";

export type ContractStatus = "uploaded" | "parsing" | "analyzed" | "error";

export type ContractRiskLevel = "low" | "medium" | "high";

export type ContractRiskCategory =
  | "payment"
  | "breach"
  | "confidentiality"
  | "ip"
  | "termination"
  | "liability"
  | "force_majeure"
  | "dispute";

export interface ContractOut {
  id: string;
  user_id: string | null;
  title: string | null;
  contract_type: ContractType | null;
  status: ContractStatus;
  file_type: string | null;
  file_size: number | null;
  language: string;
  page_count: number | null;
  summary: string | null;
  risk_score: number;
  risk_level: ContractRiskLevel;
  analyzed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContractRiskOut {
  id: string;
  contract_id: string;
  clause_ref: string | null;
  clause_text: string | null;
  category: ContractRiskCategory;
  risk_level: ContractRiskLevel;
  score: number;
  reason: string | null;
  suggestion: string | null;
  suggested_text: string | null;
  king_clause: boolean;
  created_at: string;
}

export interface ContractClauseOut {
  id: string;
  contract_id: string;
  clause_no: string | null;
  section: string | null;
  clause_text: string | null;
  category: ContractRiskCategory | null;
  order_index: number;
  explanation: string | null;
  risk_level: ContractRiskLevel | null;
  risk_note: string | null;
  suggested_version: string | null;
  created_at: string;
}

export interface ContractDetailOut extends ContractOut {
  full_text: string | null;
  ocr_text: string | null;
  law_involved: Record<string, unknown>[] | null;
  risk_clauses: Record<string, unknown>[] | null;
  king_clauses: Record<string, unknown>[] | null;
  payment_risk: Record<string, unknown> | null;
  breach_risk: Record<string, unknown> | null;
  liability_risk: Record<string, unknown> | null;
  analysis_meta: Record<string, unknown> | null;
  token_usage: Record<string, unknown> | null;
  checklist: Record<string, unknown>[] | null;
  risks: ContractRiskOut[];
  clauses: ContractClauseOut[];
}

export interface ContractUploadResponse {
  contract: ContractOut;
  parsed: boolean;
  text_length: number;
  ocr_used: boolean;
}

export interface ContractReportOut {
  id: string;
  contract_id: string;
  report_type: string;
  title: string | null;
  content: string | null;
  content_json: Record<string, unknown> | null;
  format: string;
  generated_by: string | null;
  model_id: string | null;
  file_path: string | null;
  created_at: string;
  updated_at: string;
}

// 提醒 / 待办类型
export type ContractTaskType = "reminder" | "checklist";

// 优先级
export type ContractTaskPriority = "low" | "normal" | "high" | "urgent";

// 提醒分类（与后端 CONTRACT_REMINDER_CATEGORIES 取值一致）
export type ContractTaskCategory =
  | "expiry"
  | "payment"
  | "renewal"
  | "sign_check"
  | "other";

// 单条提醒 / 待办（带 contract_title，仅聚合接口返回）
export interface ContractTaskOut {
  id: string;
  contract_id: string;
  type: ContractTaskType;
  title: string;
  category: ContractTaskCategory | null;
  due_date: string | null; // ISO date (YYYY-MM-DD)
  remind_before_days: number;
  done: boolean;
  priority: ContractTaskPriority;
  note: string | null;
  created_at: string;
  updated_at: string;
  contract_title?: string | null;
}

// 创建提醒 / 待办
export interface ContractTaskCreate {
  type?: ContractTaskType;
  title: string;
  category?: ContractTaskCategory | null;
  due_date?: string | null;
  remind_before_days?: number;
  done?: boolean;
  priority?: ContractTaskPriority;
  note?: string | null;
}

// 更新提醒 / 待办（全字段可选）
export interface ContractTaskUpdate {
  type?: ContractTaskType;
  title?: string;
  category?: ContractTaskCategory | null;
  due_date?: string | null;
  remind_before_days?: number;
  done?: boolean;
  priority?: ContractTaskPriority;
  note?: string | null;
}

// ---------------------------
// 错误类型
// ---------------------------
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// ---------------------------
// AI 能力中心（AI Capability Center，/api/ai）
// 全部接口需超管权限（后端 require_superuser）。
// ---------------------------
const aiCenter = {
  meta() {
    return request<AIMeta>("/api/ai/meta");
  },

  // 全局 AI 是否已配置真实模型（供前端门控：未配置时隐藏 AI 分析能力）
  // 仅需登录态，不暴露密钥
  status() {
    return request<{ ai_configured: boolean; provider_count: number; model_count: number }>(
      "/api/ai/status"
    );
  },

  // Provider
  listProviders() {
    return request<ProviderOut[]>("/api/ai/providers");
  },
  createProvider(body: Partial<ProviderOut> & { name: string; type: string }) {
    return request<ProviderOut>("/api/ai/providers", jsonBody(body));
  },
  updateProvider(id: string, patch: Partial<ProviderOut>) {
    return request<ProviderOut>(`/api/ai/providers/${id}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    });
  },
  deleteProvider(id: string) {
    return request<void>(`/api/ai/providers/${id}`, { method: "DELETE" });
  },

  // AIModel
  listModels() {
    return request<AIModelOut[]>("/api/ai/models");
  },
  createModel(body: Partial<AIModelOut> & { name: string; model_name: string }) {
    return request<AIModelOut>("/api/ai/models", jsonBody(body));
  },
  updateModel(id: string, patch: Partial<AIModelOut>) {
    return request<AIModelOut>(`/api/ai/models/${id}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    });
  },
  deleteModel(id: string) {
    return request<void>(`/api/ai/models/${id}`, { method: "DELETE" });
  },
  testConnection(body: {
    model_id?: string;
    provider_type?: string;
    base_url?: string | null;
    api_key?: string | null;
    model_name?: string | null;
    capability?: string;
  }) {
    return request<TestConnectionResult>("/api/ai/models/test", jsonBody(body));
  },
  checkHealth(id: string) {
    return request<ModelHealthOut>(`/api/ai/models/${id}/health/check`, {
      method: "POST",
    });
  },

  // Routing
  listRouting() {
    return request<RoutingRuleOut[]>("/api/ai/routing");
  },
  createRouting(
    body: Partial<RoutingRuleOut> & { feature: string; model_id: string }
  ) {
    return request<RoutingRuleOut>("/api/ai/routing", jsonBody(body));
  },
  updateRouting(id: string, patch: Partial<RoutingRuleOut>) {
    return request<RoutingRuleOut>(`/api/ai/routing/${id}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    });
  },

  // Prompt
  listPrompts() {
    return request<PromptTemplateOut[]>("/api/ai/prompts");
  },
  createPrompt(
    body: Partial<PromptTemplateOut> & { key: string; name: string; content: string }
  ) {
    return request<PromptTemplateOut>("/api/ai/prompts", jsonBody(body));
  },
  updatePrompt(id: string, patch: Partial<PromptTemplateOut>) {
    return request<PromptTemplateOut>(`/api/ai/prompts/${id}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    });
  },
  deletePrompt(id: string) {
    return request<void>(`/api/ai/prompts/${id}`, { method: "DELETE" });
  },
  promptVersions(id: string) {
    return request<PromptVersionOut[]>(`/api/ai/prompts/${id}/versions`);
  },

  // 统计 / 日志 / 健康
  statistics(days = 30) {
    const qs = new URLSearchParams({ days: String(days) });
    return request<StatisticsOut>(`/api/ai/statistics?${qs.toString()}`);
  },
  logs(opts: { limit?: number; offset?: number; feature?: string } = {}) {
    const qs = new URLSearchParams();
    if (opts.limit != null) qs.set("limit", String(opts.limit));
    if (opts.offset != null) qs.set("offset", String(opts.offset));
    if (opts.feature) qs.set("feature", opts.feature);
    return request<ModelLogOut[]>(`/api/ai/logs?${qs.toString()}`);
  },
  health() {
    return request<ModelHealthOut[]>("/api/ai/health");
  },
};

// ---------------------------
// 请求封装
// ---------------------------
function authHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("lp_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  needAuth = true
): Promise<T> {
  const headers = new Headers(options.headers);
  if (needAuth) {
    Object.entries(authHeader()).forEach(([k, v]) => headers.set(k, v));
  }
  // 带 body 的请求若未显式声明编码，统一按 JSON 发送，避免后端 422
  if (options.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = formatDetail(data.detail, detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function formatDetail(detail: unknown, fallback: string): string {
  if (detail == null) return fallback;
  if (typeof detail === "string") return detail;
  // FastAPI/Pydantic 校验错误数组
  if (Array.isArray(detail)) {
    return detail
      .map((e: { loc?: string[]; msg?: string; type?: string }) => {
        const loc = e.loc?.slice(1).join(".") ?? "请求";
        return `${loc}：${e.msg ?? "格式错误"}`;
      })
      .join("；");
  }
  return JSON.stringify(detail);
}

function jsonBody(body: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

// 触发浏览器下载（已有 ObjectURL）
function triggerDownload(url: string, filename: string) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

// 取回证据原件（带鉴权）并返回 blob ObjectURL，供前端预览 / 下载
async function fetchEvidenceBlob(id: string): Promise<string> {
  const headers = new Headers();
  Object.entries(authHeader()).forEach(([k, v]) => headers.set(k, v));
  const res = await fetch(`${API_BASE}/api/v1/evidence-center/${id}/file`, {
    headers,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = formatDetail(data.detail, detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

// 导出证据报告（word / pdf / markdown）→ blob 触发下载
async function downloadEvidenceReport(
  id: string,
  fmt: "word" | "pdf" | "markdown",
  filename: string
) {
  const headers = new Headers();
  Object.entries(authHeader()).forEach(([k, v]) => headers.set(k, v));
  const res = await fetch(
    `${API_BASE}/api/v1/evidence-center/reports/${id}/download?fmt=${fmt}`,
    { headers }
  );
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = formatDetail(data.detail, detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  triggerDownload(url, filename);
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

// ---------------------------
// 认证
// ---------------------------
const caseCenter = {
  list(params: {
    q?: string;
    status?: string;
    case_type?: string;
    tag?: string;
    starred?: boolean;
    favorite?: boolean;
    page?: number;
    page_size?: number;
  } = {}) {
    const qs = new URLSearchParams();
    if (params.q) qs.set("q", params.q);
    if (params.status) qs.set("status", params.status);
    if (params.case_type) qs.set("case_type", params.case_type);
    if (params.tag) qs.set("tag", params.tag);
    if (params.starred != null) qs.set("starred", String(params.starred));
    if (params.favorite != null) qs.set("favorite", String(params.favorite));
    if (params.page) qs.set("page", String(params.page));
    if (params.page_size) qs.set("page_size", String(params.page_size));
    const q = qs.toString();
    return request<Page<CaseCenterOut>>(`/api/cases${q ? `?${q}` : ""}`);
  },
  create(body: {
    title: string;
    case_type: CaseType;
    description?: string;
    status?: CaseCenterStatus;
    priority?: Priority;
    owner?: string;
    tags?: string[];
    color?: string;
    cover_url?: string;
    position?: number;
  }) {
    return request<CaseCenterOut>("/api/cases", jsonBody(body));
  },
  get(id: string) {
    return request<CaseCenterDetailOut>(`/api/cases/${id}`);
  },
  update(id: string, patch: Partial<CaseCenterOut>) {
    return request<CaseCenterOut>(`/api/cases/${id}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    });
  },
  remove(id: string) {
    return request<void>(`/api/cases/${id}`, { method: "DELETE" });
  },
  addAnalysis(id: string, body: { analysis_type?: string; summary?: string; risk?: string; risk_level?: string; suggested_status?: CaseCenterStatus; next_steps?: string[] }) {
    return request<CaseAnalysisOut>(`/api/cases/${id}/analysis`, jsonBody(body));
  },
  addEvidence(id: string, body: { category: EvidenceCategory; title: string; description?: string; is_uploaded?: boolean; ai_note?: string }) {
    return request<CaseEvidenceOut>(`/api/cases/${id}/evidence`, jsonBody(body));
  },
  updateEvidence(id: string, evId: string, patch: Partial<CaseEvidenceOut>) {
    return request<CaseEvidenceOut>(`/api/cases/${id}/evidence/${evId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  },
  removeEvidence(id: string, evId: string) {
    return request<void>(`/api/cases/${id}/evidence/${evId}`, { method: "DELETE" });
  },
  addDocument(id: string, body: { doc_type: DocType; title: string; content: string; status?: DocStatus }) {
    return request<CaseDocumentOut>(`/api/cases/${id}/document`, jsonBody(body));
  },
  updateDocument(id: string, docId: string, patch: Partial<CaseDocumentOut>) {
    return request<CaseDocumentOut>(`/api/cases/${id}/document/${docId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  },
  removeDocument(id: string, docId: string) {
    return request<void>(`/api/cases/${id}/document/${docId}`, { method: "DELETE" });
  },
  addTask(id: string, body: { title: string; description?: string; due_date?: string; status?: TaskStatus; priority?: Priority }) {
    return request<CaseTaskOut>(`/api/cases/${id}/task`, jsonBody(body));
  },
  updateTask(id: string, taskId: string, patch: Partial<CaseTaskOut>) {
    return request<CaseTaskOut>(`/api/cases/${id}/task/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  },
  removeTask(id: string, taskId: string) {
    return request<void>(`/api/cases/${id}/task/${taskId}`, { method: "DELETE" });
  },
  addTimeline(id: string, body: { event_type: string; title: string; detail?: string; occurred_at?: string }) {
    return request<CaseTimelineOut>(`/api/cases/${id}/timeline`, jsonBody(body));
  },
  updateTimeline(id: string, tlId: string, patch: Partial<CaseTimelineOut>) {
    return request<CaseTimelineOut>(`/api/cases/${id}/timeline/${tlId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  },
  removeTimeline(id: string, tlId: string) {
    return request<void>(`/api/cases/${id}/timeline/${tlId}`, { method: "DELETE" });
  },
  addNote(id: string, body: { content: string }) {
    return request<CaseNoteOut>(`/api/cases/${id}/note`, jsonBody(body));
  },
  updateNote(id: string, noteId: string, patch: Partial<CaseNoteOut>) {
    return request<CaseNoteOut>(`/api/cases/${id}/note/${noteId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  },
  removeNote(id: string, noteId: string) {
    return request<void>(`/api/cases/${id}/note/${noteId}`, { method: "DELETE" });
  },
};

// ---------------------------
// 案例智能搜索（Legal Case Search，/api/legal-cases）
// search/filter/detail 公开；similar/favorites 及收藏写操作需登录
// ---------------------------
const legalCase = {
  search(
    q: string,
    opts: {
      province?: string;
      city?: string;
      court_level?: string;
      case_type?: string;
      time_range?: string;
      limit?: number;
      offset?: number;
    } = {}
  ) {
    const qs = new URLSearchParams({ q });
    if (opts.province) qs.set("province", opts.province);
    if (opts.city) qs.set("city", opts.city);
    if (opts.court_level) qs.set("court_level", opts.court_level);
    if (opts.case_type) qs.set("case_type", opts.case_type);
    if (opts.time_range) qs.set("time_range", opts.time_range);
    if (opts.limit != null) qs.set("limit", String(opts.limit));
    if (opts.offset != null) qs.set("offset", String(opts.offset));
    // 带登录态调用无副作用；未登录时 authHeader 返回空
    return request<LegalCaseSearchResult>(
      `/api/legal-cases/search?${qs.toString()}`
    );
  },
  filter() {
    return request<CaseFilterFacets>(`/api/legal-cases/filter`, {}, false);
  },
  detail(id: string) {
    return request<LegalCaseDetail>(`/api/legal-cases/${id}`, {}, false);
  },
  similar(body: { case_id?: string; query?: string; limit?: number }) {
    return request<LegalCaseSearchResult>(
      `/api/legal-cases/similar`,
      jsonBody(body)
    );
  },
  favorites() {
    return request<LegalCaseSearchResult>(`/api/legal-cases/user/favorites`);
  },
  addFavorite(id: string) {
    return request<{ ok: boolean }>(`/api/legal-cases/${id}/favorite`, {
      method: "POST",
    });
  },
  removeFavorite(id: string) {
    return request<{ ok: boolean }>(`/api/legal-cases/${id}/favorite`, {
      method: "DELETE",
    });
  },
};

// ---------------------------
// 法律研究中心（Legal Research Center，/api/research）
// search / document / recommend 均为公开接口（无需登录）
// ---------------------------
const research = {
  search(
    q: string,
    opts: {
      doc_type?: string;
      category?: string;
      level?: string;
      region?: string;
      issuing_authority?: string;
      is_current?: boolean;
      publish_from?: string;
      publish_to?: string;
      search_mode?: string;
      limit?: number;
      offset?: number;
    } = {}
  ) {
    const qs = new URLSearchParams();
    if (q) qs.set("q", q);
    if (opts.doc_type) qs.set("doc_type", opts.doc_type);
    if (opts.category) qs.set("category", opts.category);
    if (opts.level) qs.set("level", opts.level);
    if (opts.region) qs.set("region", opts.region);
    if (opts.issuing_authority) qs.set("issuing_authority", opts.issuing_authority);
    if (opts.is_current != null) qs.set("is_current", String(opts.is_current));
    if (opts.publish_from) qs.set("publish_from", opts.publish_from);
    if (opts.publish_to) qs.set("publish_to", opts.publish_to);
    if (opts.search_mode) qs.set("search_mode", opts.search_mode);
    if (opts.limit != null) qs.set("limit", String(opts.limit));
    if (opts.offset != null) qs.set("offset", String(opts.offset));
    return request<ResearchSearchResult>(
      `/api/research/search?${qs.toString()}`,
      {},
      false
    );
  },
  detail(id: string) {
    return request<ResearchDocDetail>(`/api/research/document/${id}`, {}, false);
  },
  recommend(opts: { doc_id?: string; q?: string; limit?: number } = {}) {
    const qs = new URLSearchParams();
    if (opts.doc_id) qs.set("doc_id", opts.doc_id);
    if (opts.q) qs.set("q", opts.q);
    if (opts.limit != null) qs.set("limit", String(opts.limit));
    return request<ResearchRecommendResult>(
      `/api/research/recommend?${qs.toString()}`,
      {},
      false
    );
  },
};

export const api = {
  async register(email: string, password: string, display_name?: string) {
    return request<UserOut>("/api/v1/auth/register", jsonBody({ email, password, display_name }));
  },
  async login(email: string, password: string) {
    // OAuth2 密码流使用 form-urlencoded
    const form = new URLSearchParams({ username: email, password });
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded", ...authHeader() },
      body: form.toString(),
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const data = await res.json();
        detail = formatDetail(data.detail, detail);
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, detail);
    }
    return (await res.json()) as Token;
  },
  async me() {
    return request<UserOut>("/api/v1/users/me");
  },

  // -------------------------
  // 案件
  // -------------------------
  async createCase(title: string, case_type: CaseType, description?: string) {
    return request<CaseOut>(
      "/api/v1/cases",
      jsonBody({ title, case_type, description })
    );
  },
  async listCases(params: { status?: string; case_type?: string; page?: number; page_size?: number } = {}) {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status", params.status);
    if (params.case_type) qs.set("case_type", params.case_type);
    if (params.page) qs.set("page", String(params.page));
    if (params.page_size) qs.set("page_size", String(params.page_size));
    const q = qs.toString();
    return request<Page<CaseOut>>(`/api/v1/cases${q ? `?${q}` : ""}`);
  },
  async getCase(id: string) {
    return request<CaseOut>(`/api/v1/cases/${id}`);
  },
  async updateCase(id: string, patch: Partial<CaseOut>) {
    return request<CaseOut>(`/api/v1/cases/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  },
  async deleteCase(id: string) {
    return request<void>(`/api/v1/cases/${id}`, { method: "DELETE" });
  },

  // -------------------------
  // 消息
  // -------------------------
  async addMessage(caseId: string, content: string) {
    return request<MessageOut>(`/api/v1/cases/${caseId}/messages`, jsonBody({ content }));
  },
  async listMessages(caseId: string) {
    return request<MessageOut[]>(`/api/v1/cases/${caseId}/messages`);
  },

  // -------------------------
  // Agent 对话（Phase 6）
  // -------------------------
  async getAgentState(caseId: string) {
    return request<AgentStateResponse>(`/api/v1/cases/${caseId}/agent/state`);
  },
  async sendChat(caseId: string, content: string) {
    return request<ChatResponse>(`/api/v1/cases/${caseId}/chat`, jsonBody({ content }));
  },

  // -------------------------
  // 证据
  // -------------------------
  async uploadEvidence(caseId: string, file: File, category: EvidenceCategory, title?: string, description?: string) {
    const form = new FormData();
    form.append("file", file);
    form.append("category", category);
    if (title) form.append("title", title);
    if (description) form.append("description", description);
    const headers = new Headers();
    Object.entries(authHeader()).forEach(([k, v]) => headers.set(k, v));
    const res = await fetch(`${API_BASE}/api/v1/cases/${caseId}/evidence`, {
      method: "POST",
      headers,
      body: form,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const data = await res.json();
        detail = data.detail ?? detail;
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, detail);
    }
    return (await res.json()) as EvidenceOut;
  },
  async addPlannedEvidence(caseId: string, category: EvidenceCategory, title: string, description?: string, ai_note?: string) {
    return request<EvidenceOut>(`/api/v1/cases/${caseId}/evidence/planned`, jsonBody({ category, title, description, ai_note }));
  },
  async listEvidence(caseId: string) {
    return request<EvidenceOut[]>(`/api/v1/cases/${caseId}/evidence`);
  },

  // -------------------------
  // 文书
  // -------------------------
  async generateDocument(caseId: string, doc_type: DocType, extra?: Record<string, unknown>) {
    return request<DocumentOut>(`/api/v1/cases/${caseId}/documents`, jsonBody({ doc_type, extra }));
  },
  async listDocuments(caseId: string) {
    return request<DocumentOut[]>(`/api/v1/cases/${caseId}/documents`);
  },

  // -------------------------
  // Roadmap
  // -------------------------
  async generateRoadmap(caseId: string) {
    return request<RoadmapOut>(`/api/v1/cases/${caseId}/roadmaps`, { method: "POST" });
  },
  async getRoadmap(caseId: string) {
    return request<RoadmapOut | null>(`/api/v1/cases/${caseId}/roadmaps`);
  },
  async updateStep(caseId: string, stepId: string, status: StepStatus) {
    return request<RoadmapStepOut>(`/api/v1/cases/${caseId}/roadmaps/steps/${stepId}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
  },

  // -------------------------
  // 任务
  // -------------------------
  async listTasks(caseId: string) {
    return request<TaskOut[]>(`/api/v1/cases/${caseId}/tasks`);
  },
  async updateTask(caseId: string, taskId: string, patch: Partial<TaskOut>) {
    return request<TaskOut>(`/api/v1/cases/${caseId}/tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  },

  // -------------------------
  // 时间线
  // -------------------------
  async listHistory(caseId: string) {
    return request<HistoryOut[]>(`/api/v1/cases/${caseId}/history`);
  },

  // -------------------------
  // 法律检索（公开）
  // -------------------------
  async legalSearch(q: string, source?: LegalSource, limit = 10, offset = 0) {
    const qs = new URLSearchParams({ q, limit: String(limit), offset: String(offset) });
    if (source) qs.set("source", source);
    return request<LegalSearchResult>(`/api/v1/legal/search?${qs.toString()}`, {}, false);
  },

  // -------------------------
  // 法律搜索（Law Search 模块，search/detail/recommend 公开；history 需登录）
  // -------------------------
  async lawSearch(
    q: string,
    opts: { status?: string; limit?: number; offset?: number } = {}
  ) {
    const qs = new URLSearchParams({ q });
    if (opts.status) qs.set("status", opts.status);
    if (opts.limit != null) qs.set("limit", String(opts.limit));
    if (opts.offset != null) qs.set("offset", String(opts.offset));
    // 带登录态调用：登录用户会被记入搜索历史（后端 optional_current_user）
    return request<LawSearchResult>(`/api/laws/search?${qs.toString()}`);
  },
  async lawDetail(id: string) {
    return request<LawDetail>(`/api/laws/detail/${id}`);
  },
  async lawRecommend(lawId?: string, limit = 6) {
    const qs = new URLSearchParams({ limit: String(limit) });
    if (lawId) qs.set("law_id", lawId);
    return request<LawOut[]>(`/api/laws/recommend?${qs.toString()}`);
  },
  async lawHistory(limit = 20) {
    const qs = new URLSearchParams({ limit: String(limit) });
    return request<LawHistoryOut[]>(`/api/laws/history?${qs.toString()}`);
  },

  // 案件中心
  caseCenter,

  // 案例智能搜索
  legalCase,
  // 法律研究中心
  research,
  // AI 能力中心
  aiCenter,

  // -------------------------
  // AI Playground（AI 模型测试中心）
  // 除 publish 需超管外，其余接口任意登录用户可用
  // -------------------------
  playground: {
    listModels() {
      return request<PlaygroundModelOut[]>("/api/playground/models");
    },
    test(body: {
      model_id: string;
      system_prompt?: string | null;
      user_prompt: string;
      context?: string | null;
      files?: { name: string; size?: number; type?: string | null; storage_key?: string | null }[] | null;
      temperature?: number | null;
      top_p?: number | null;
      max_tokens?: number | null;
      streaming?: boolean;
    }) {
      return request<PlaygroundSessionOut>("/api/playground/test", jsonBody(body));
    },
    compare(body: {
      model_ids: string[];
      system_prompt?: string | null;
      user_prompt: string;
      context?: string | null;
      temperature?: number | null;
      top_p?: number | null;
      max_tokens?: number | null;
      judge_model_id?: string | null;
    }) {
      return request<{ session: PlaygroundSessionOut; rows: CompareRowOut[] }>(
        "/api/playground/compare",
        jsonBody(body)
      );
    },
    evaluate(body: {
      name: string;
      model_ids: string[];
      judge_model_id?: string | null;
      dataset_id?: string | null;
      feature?: string | null;
      prompt_template_key?: string | null;
      config?: Record<string, unknown> | null;
      items?: { input: string; expected?: string | null; context?: string | null }[] | null;
    }) {
      return request<EvaluationTaskOut>("/api/playground/evaluate", jsonBody(body));
    },
    history(opts: { type?: string; limit?: number; offset?: number } = {}) {
      const qs = new URLSearchParams();
      if (opts.type) qs.set("type", opts.type);
      if (opts.limit != null) qs.set("limit", String(opts.limit));
      if (opts.offset != null) qs.set("offset", String(opts.offset));
      const q = qs.toString();
      return request<PlaygroundSessionOut[]>(`/api/playground/history${q ? `?${q}` : ""}`);
    },
    publish(body: { feature: string; model_id: string; note?: string | null }) {
      return request<PlaygroundPublishOut>("/api/playground/publish", jsonBody(body));
    },
    routing() {
      return request<RoutingRuleSimpleOut[]>("/api/playground/routing");
    },
    listPrompts(opts: { category?: string } = {}) {
      const qs = new URLSearchParams();
      if (opts.category) qs.set("category", opts.category);
      const q = qs.toString();
      return request<PromptLibraryOut[]>(`/api/playground/prompts${q ? `?${q}` : ""}`);
    },
    createPrompt(body: {
      name: string;
      category?: string | null;
      prompt: string;
      variables?: string[] | null;
      tags?: string[] | null;
      is_public?: boolean;
    }) {
      return request<PromptLibraryOut>("/api/playground/prompts", jsonBody(body));
    },
    updatePrompt(
      pid: string,
      patch: {
        name?: string;
        category?: string | null;
        prompt?: string;
        variables?: string[] | null;
        tags?: string[] | null;
        is_public?: boolean | null;
      }
    ) {
      return request<PromptLibraryOut>(`/api/playground/prompts/${pid}`, {
        method: "PUT",
        body: JSON.stringify(patch),
      });
    },
    deletePrompt(pid: string) {
      return request<void>(`/api/playground/prompts/${pid}`, { method: "DELETE" });
    },
    listDatasets() {
      return request<EvaluationDatasetOut[]>("/api/playground/datasets");
    },
    // 后端 create_dataset：name/category/description/is_public 走 query，items 走 JSON 数组 body
    createDataset(params: {
      name: string;
      items: { input: string; expected?: string | null; context?: string | null }[];
      category?: string | null;
      description?: string | null;
      is_public?: boolean;
    }) {
      const qs = new URLSearchParams();
      qs.set("name", params.name);
      if (params.category) qs.set("category", params.category);
      if (params.description) qs.set("description", params.description);
      if (params.is_public) qs.set("is_public", "true");
      return request<EvaluationDatasetOut>(`/api/playground/datasets?${qs.toString()}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params.items),
      });
    },
    listDatasetItems(datasetId: string) {
      return request<EvaluationItemOut[]>(`/api/playground/datasets/${datasetId}/items`);
    },
    listEvaluations(opts: { limit?: number; offset?: number } = {}) {
      const qs = new URLSearchParams();
      if (opts.limit != null) qs.set("limit", String(opts.limit));
      if (opts.offset != null) qs.set("offset", String(opts.offset));
      const q = qs.toString();
      return request<EvaluationTaskOut[]>(`/api/playground/evaluations${q ? `?${q}` : ""}`);
    },
    getEvaluationResults(taskId: string) {
      return request<EvaluationResultOut[]>(`/api/playground/evaluations/${taskId}`);
    },
  },

  // -------------------------
  // 合同智能中心（Contract Intelligence Center，/api/contracts）
  // 所有接口需登录（Bearer）
  // -------------------------
  contracts: {
    // 上传：multipart/form-data（file + 可选 title）。
    // 复用 uploadEvidence 的手动 fetch 模式，避免 request() 自动设置 JSON Content-Type。
    async upload(file: File, title?: string) {
      const form = new FormData();
      form.append("file", file);
      if (title) form.append("title", title);
      const headers = new Headers();
      Object.entries(authHeader()).forEach(([k, v]) => headers.set(k, v));
      const res = await fetch(`${API_BASE}/api/contracts/upload`, {
        method: "POST",
        headers,
        body: form,
      });
      if (!res.ok) {
        let detail = res.statusText;
        try {
          const data = await res.json();
          detail = formatDetail(data.detail, detail);
        } catch {
          /* ignore */
        }
        throw new ApiError(res.status, detail);
      }
      return (await res.json()) as ContractUploadResponse;
    },
    list(
      params: {
        contract_type?: string;
        status?: string;
        page?: number;
        page_size?: number;
      } = {}
    ) {
      const qs = new URLSearchParams();
      if (params.contract_type) qs.set("contract_type", params.contract_type);
      if (params.status) qs.set("status", params.status);
      if (params.page) qs.set("page", String(params.page));
      if (params.page_size) qs.set("page_size", String(params.page_size));
      const q = qs.toString();
      return request<Page<ContractOut>>(`/api/contracts${q ? `?${q}` : ""}`);
    },
    get(id: string) {
      return request<ContractDetailOut>(`/api/contracts/${id}`);
    },
    analyze(id: string) {
      return request<ContractDetailOut>(`/api/contracts/${id}/analyze`, {
        method: "POST",
      });
    },
    risks(id: string) {
      return request<ContractRiskOut[]>(`/api/contracts/${id}/risks`);
    },
    clauses(id: string) {
      return request<ContractClauseOut[]>(`/api/contracts/${id}/clauses`);
    },
    remove(id: string) {
      return request<ContractOut>(`/api/contracts/${id}`, { method: "DELETE" });
    },
    // 生成/取回审查报告（report_type: review/summary/full/checklist；regenerate 强制重生成）
    report(id: string, reportType: string = "review", regenerate: boolean = false) {
      const qs = new URLSearchParams();
      qs.set("report_type", reportType);
      if (regenerate) qs.set("regenerate", "true");
      return request<ContractReportOut>(
        `/api/contracts/${id}/report?${qs.toString()}`
      );
    },
    reports(id: string) {
      return request<ContractReportOut[]>(`/api/contracts/${id}/reports`);
    },
    // 提醒 / 待办：列出某合同下的任务（type 可选过滤 reminder/checklist）
    tasks(id: string, type?: string) {
      const qs = type ? `?type=${encodeURIComponent(type)}` : "";
      return request<ContractTaskOut[]>(`/api/contracts/${id}/tasks${qs}`);
    },
    // 创建提醒 / 待办
    createTask(id: string, body: ContractTaskCreate) {
      return request<ContractTaskOut>(`/api/contracts/${id}/tasks`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    // 更新提醒 / 待办（标题 / 日期 / 完成状态等）
    updateTask(id: string, taskId: string, body: ContractTaskUpdate) {
      return request<ContractTaskOut>(
        `/api/contracts/${id}/tasks/${taskId}`,
        {
          method: "PATCH",
          body: JSON.stringify(body),
        }
      );
    },
    // 删除提醒 / 待办
    deleteTask(id: string, taskId: string) {
      return request<ContractTaskOut>(`/api/contracts/${id}/tasks/${taskId}`, {
        method: "DELETE",
      });
    },
    // 提醒中心聚合：当前用户所有「未完成」且 due_date 在 [今天, 今天+N天] 的提醒
    upcoming(days: number = 30) {
      return request<ContractTaskOut[]>(
        `/api/contracts/tasks/upcoming?days=${days}`
      );
    },
  },

  // -------------------------
  // 智能证据中心（Evidence Intelligence Center，/api/v1/evidence-center）
  // -------------------------
  evidenceCenter: {
    // 批量上传：multipart（files）+ query case_id / source / tags
    async upload(
      files: File[],
      opts: { case_id?: string; source?: string; tags?: string[] } = {}
    ) {
      const form = new FormData();
      for (const f of files) form.append("files", f);
      const qs = new URLSearchParams();
      if (opts.case_id) qs.set("case_id", opts.case_id);
      if (opts.source) qs.set("source", opts.source);
      if (opts.tags) for (const t of opts.tags) qs.append("tags", t);
      const q = qs.toString();
      const headers = new Headers();
      Object.entries(authHeader()).forEach(([k, v]) => headers.set(k, v));
      const res = await fetch(
        `${API_BASE}/api/v1/evidence-center/upload${q ? `?${q}` : ""}`,
        { method: "POST", headers, body: form }
      );
      if (!res.ok) {
        let detail = res.statusText;
        try {
          const data = await res.json();
          detail = formatDetail(data.detail, detail);
        } catch {
          /* ignore */
        }
        throw new ApiError(res.status, detail);
      }
      return (await res.json()) as EvidenceUploadResponse;
    },
    // 列表（支持类型 / 状态 / 案件筛选 + 名称搜索 + 分页）
    list(
      params: {
        category?: string;
        status?: string;
        case_id?: string;
        q?: string;
        page?: number;
        page_size?: number;
      } = {}
    ) {
      const qs = new URLSearchParams();
      if (params.category) qs.set("category", params.category);
      if (params.status) qs.set("status", params.status);
      if (params.case_id) qs.set("case_id", params.case_id);
      if (params.q) qs.set("q", params.q);
      if (params.page) qs.set("page", String(params.page));
      if (params.page_size) qs.set("page_size", String(params.page_size));
      const q = qs.toString();
      return request<Page<EvidenceFileOut>>(
        `/api/v1/evidence-center${q ? `?${q}` : ""}`
      );
    },
    // 详情（含分析结果）
    get(id: string) {
      return request<EvidenceDetailOut>(`/api/v1/evidence-center/${id}`);
    },
    // 删除
    remove(id: string) {
      return request<EvidenceFileOut>(`/api/v1/evidence-center/${id}`, {
        method: "DELETE",
      });
    },
    // 预览 / 下载原件：返回 blob ObjectURL（带鉴权）
    fileUrl(id: string) {
      return fetchEvidenceBlob(id);
    },
    // 下载原件（触发浏览器下载）
    downloadFile(id: string, filename: string) {
      return fetchEvidenceBlob(id).then((url) => {
        triggerDownload(url, filename);
        setTimeout(() => URL.revokeObjectURL(url), 2000);
      });
    },
    // 批量分析
    analyzeBatch(ids: string[]) {
      return request<EvidenceAnalyzeResponse>(
        `/api/v1/evidence-center/analyze`,
        { method: "POST", body: JSON.stringify({ evidence_ids: ids }) }
      );
    },
    // 单条分析（force_reparse 重新 OCR）
    analyzeSingle(id: string, force_reparse = false) {
      const qs = force_reparse ? "?force_reparse=true" : "";
      return request<EvidenceAnalyzeItem>(
        `/api/v1/evidence-center/${id}/analyze${qs}`,
        { method: "POST" }
      );
    },
    // 读取分析结果
    analysis(id: string) {
      return request<EvidenceAnalysisOut>(
        `/api/v1/evidence-center/${id}/analysis`
      );
    },
    // 建立证据关系
    createRelation(body: EvidenceRelationCreate) {
      return request<EvidenceRelationOut>(`/api/v1/evidence-center/relations`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    // 查询关系（按案件 / 按单证据）
    listRelations(params: { case_id?: string; evidence_id?: string } = {}) {
      const qs = new URLSearchParams();
      if (params.case_id) qs.set("case_id", params.case_id);
      if (params.evidence_id) qs.set("evidence_id", params.evidence_id);
      const q = qs.toString();
      return request<EvidenceRelationOut[]>(
        `/api/v1/evidence-center/relations${q ? `?${q}` : ""}`
      );
    },
    // 删除关系
    deleteRelation(id: string) {
      return request<{ deleted: boolean }>(
        `/api/v1/evidence-center/relations/${id}`,
        { method: "DELETE" }
      );
    },
    // 构建证据链（AI 推断关系 + 重建时间线）
    buildChain(body: EvidenceChainBuildRequest) {
      return request<EvidenceChainBuildResponse>(
        `/api/v1/evidence-center/chain/build`,
        { method: "POST", body: JSON.stringify(body) }
      );
    },
    // 案件时间线
    timeline(case_id: string) {
      return request<EvidenceTimelineNodeOut[]>(
        `/api/v1/evidence-center/chain/timeline?case_id=${case_id}`
      );
    },
    // 证据图谱（节点 + 边 + 时间线）
    graph(params: { case_id?: string; evidence_ids?: string[] } = {}) {
      const qs = new URLSearchParams();
      if (params.case_id) qs.set("case_id", params.case_id);
      if (params.evidence_ids)
        for (const e of params.evidence_ids) qs.append("evidence_ids", e);
      const q = qs.toString();
      return request<EvidenceGraphOut>(
        `/api/v1/evidence-center/chain/graph${q ? `?${q}` : ""}`
      );
    },
    // 生成报告（directory / score / missing / strategy / full）
    generateReport(body: EvidenceReportGenerateRequest) {
      return request<EvidenceReportOut>(`/api/v1/evidence-center/reports`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    // 报告列表（按案件或当前用户）
    listReports(case_id?: string) {
      const q = case_id ? `?case_id=${case_id}` : "";
      return request<EvidenceReportOut[]>(`/api/v1/evidence-center/reports${q}`);
    },
    // 报告详情
    getReport(id: string) {
      return request<EvidenceReportOut>(`/api/v1/evidence-center/reports/${id}`);
    },
    // 报告导出下载（word / pdf / markdown）
    downloadReport(
      id: string,
      fmt: "word" | "pdf" | "markdown",
      filename: string
    ) {
      return downloadEvidenceReport(id, fmt, filename);
    },
  },
};

// ---------------------------
// 案件中心（Case Center 模块，/api/cases）
// ---------------------------
export interface CaseCenterOut {
  id: string;
  user_id: string;
  title: string;
  case_type: CaseType;
  status: CaseCenterStatus;
  priority: Priority;
  owner: string | null;
  starred: boolean;
  favorite: boolean;
  tags: string[] | null;
  color: string | null;
  cover_url: string | null;
  position: number;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface CaseAnalysisOut {
  id: string;
  case_id: string;
  user_id: string | null;
  analysis_type: string;
  summary: string | null;
  risk: string | null;
  risk_level: string | null;
  suggested_status: CaseCenterStatus | null;
  next_steps: string[] | null;
  raw: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface CaseEvidenceOut {
  id: string;
  case_id: string;
  user_id: string | null;
  category: EvidenceCategory;
  title: string;
  description: string | null;
  file_path: string | null;
  file_type: string | null;
  ocr_text: string | null;
  is_uploaded: boolean;
  ai_note: string | null;
  created_at: string;
  updated_at: string;
}

export interface CaseDocumentOut {
  id: string;
  case_id: string;
  user_id: string | null;
  doc_type: DocType;
  title: string;
  content: string;
  status: DocStatus;
  created_at: string;
  updated_at: string;
}

export interface CaseTaskOut {
  id: string;
  case_id: string;
  user_id: string | null;
  title: string;
  description: string | null;
  due_date: string | null;
  status: TaskStatus;
  priority: Priority;
  position: number;
  created_at: string;
  updated_at: string;
}

export interface CaseTimelineOut {
  id: string;
  case_id: string;
  user_id: string | null;
  event_type: string;
  title: string;
  detail: string | null;
  occurred_at: string;
  created_at: string;
  updated_at: string;
}

export interface CaseNoteOut {
  id: string;
  case_id: string;
  user_id: string | null;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface CaseCenterDetailOut {
  case: CaseCenterOut;
  analyses: CaseAnalysisOut[];
  evidences: CaseEvidenceOut[];
  documents: CaseDocumentOut[];
  tasks: CaseTaskOut[];
  timelines: CaseTimelineOut[];
  notes: CaseNoteOut[];
}

// ---------------------------
// 智能证据中心（Evidence Intelligence Center，/api/v1/evidence-center）
// 枚举取值与后端 models/enums.py 保持一致
// ---------------------------
// 证据类型（与后端 EvidenceFileCategoryEnum 取值一致）
export type EvidenceFileCategory =
  | "contract"
  | "payment"
  | "chat"
  | "identity"
  | "notice"
  | "audio"
  | "photo"
  | "video"
  | "email"
  | "webpage"
  | "document"
  | "other";

// 证据处理状态（与后端 EvidenceFileStatusEnum 取值一致）
export type EvidenceFileStatus =
  | "uploaded"
  | "processing"
  | "ocr_done"
  | "analyzed"
  | "linked";

// 证据间关系类型（Evidence Graph 证据链，与后端 EvidenceRelationTypeEnum 一致）
export type EvidenceRelationType =
  | "sequence"
  | "support"
  | "contradict"
  | "prerequisite"
  | "related";

// 证据报告类型（与后端 EvidenceReportTypeEnum 取值一致）
export type EvidenceReportType =
  | "directory"
  | "score"
  | "missing"
  | "strategy"
  | "full";

export interface EvidenceFileOut {
  id: string;
  case_id: string | null;
  user_id: string | null;
  name: string;
  category: EvidenceFileCategory;
  status: EvidenceFileStatus;
  file_url: string | null;
  file_type: string | null;
  mime_type: string | null;
  size_bytes: number | null;
  ocr_text: string | null;
  meta: Record<string, unknown> | null;
  formed_at: string | null;
  source: string | null;
  tags: string[] | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface EvidenceUploadItem {
  file: EvidenceFileOut;
  stored: boolean;
  note: string | null;
}

export interface EvidenceUploadResponse {
  items: EvidenceUploadItem[];
  total: number;
  succeeded: number;
}

export interface EvidenceAnalysisOut {
  id: string;
  evidence_id: string;
  summary: string | null;
  proof_point: string | null;
  proof_strength: number | null;
  risk: string | null;
  suggestion: string | null;
  dimensions: Record<string, unknown> | null;
  model_used: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface EvidenceAnalyzeRequest {
  evidence_ids: string[];
  force_reparse?: boolean;
}

export interface EvidenceAnalyzeItem {
  evidence_id: string;
  ok: boolean;
  ai_available?: boolean;
  ocr_kind?: string | null;
  text_len?: number;
  proof_strength?: number | null;
  status?: string | null;
  latency_ms?: number;
  note?: string | null;
}

export interface EvidenceAnalyzeResponse {
  items: EvidenceAnalyzeItem[];
  total: number;
  succeeded: number;
}

export interface EvidenceDetailOut extends EvidenceFileOut {
  analysis: EvidenceAnalysisOut | null;
}

export interface EvidenceRelationCreate {
  source_id: string;
  target_id: string;
  relation_type: EvidenceRelationType;
  note?: string | null;
}

export interface EvidenceRelationOut {
  id: string;
  source_id: string;
  target_id: string;
  relation_type: EvidenceRelationType;
  note: string | null;
  created_at: string | null;
}

export interface EvidenceChainBuildRequest {
  case_id?: string | null;
  evidence_ids?: string[] | null;
  infer_relations?: boolean;
  build_timeline?: boolean;
}

export interface EvidenceChainBuildResponse {
  evidence_count: number;
  relations_created: number;
  timeline_nodes: number;
  ai_available?: boolean;
  note?: string | null;
}

export interface EvidenceTimelineNodeOut {
  id: string;
  case_id: string | null;
  event: string;
  event_time: string | null;
  description: string | null;
  order_index: number;
  evidence_ids: string[] | null;
}

export interface EvidenceGraphNode {
  id: string;
  name: string;
  category: EvidenceFileCategory;
  status: EvidenceFileStatus;
  event_time: string | null;
  proof_strength: number | null;
  proof_point: string | null;
  summary: string | null;
}

export interface EvidenceGraphOut {
  nodes: EvidenceGraphNode[];
  edges: EvidenceRelationOut[];
  timeline: EvidenceTimelineNodeOut[];
}

export interface EvidenceReportGenerateRequest {
  case_id?: string | null;
  evidence_ids?: string[] | null;
  report_type?: EvidenceReportType;
  regenerate?: boolean;
}

export interface EvidenceReportOut {
  id: string;
  case_id: string | null;
  title: string;
  report_type: EvidenceReportType;
  content: Record<string, unknown> | null;
  format: string | null;
  file_url: string | null;
  created_at: string | null;
  updated_at: string | null;
}

// Case Center API 方法
export default api;
