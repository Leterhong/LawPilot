# AI 能力中心（AI Capability Center）—— 第一步：数据库设计

> 目标：把 LawPilot 重构成「支持任意大模型 / 任意 Provider / 可视化配置 / 智能路由」的 AI 平台。
> 原则：**以后新增任何模型不得修改业务代码，全部通过后台管理完成**；保持现有架构、模块独立、支持 Docker + PostgreSQL + OpenAI Compatible + 多 Provider。
> 本文件仅含**设计**，不含实现代码。确认后才会生成 SQLAlchemy 模型 + Alembic 迁移。

---

## 0. 与现有架构的关系（关键决策）

| 现状 | 设计后 |
|---|---|
| `LLMClient` / `EmbeddingService` / `RerankerService` 直接读 `config.py` 的 `.env` 变量 | 这些配置**移入数据库**（providers / ai_models），由 `AIManager` 读取 |
| API Key 存于 `.env` 明文 | 数据库中的 `api_key` **加密存储**（Fernet，密钥取自 `settings.ai_encryption_key` 或回退 `settings.secret_key`） |
| 无管理员概念，`User` 只有 `is_active`/`is_verified` | 新增 `User.is_superuser`（**增量列，不破坏已有模块**），AI 能力中心后台仅超级管理员可访问 |
| 各业务里散落 `LLMClient()` / `EmbeddingService()` 直调 | 统一收口到 `AIManager.chat/embedding/vision/rerank/auto_route`（Step4/5 实现） |
| Prompt 硬编码在 service 里 | 全部抽到 `prompt_templates`（Step3 起禁止代码内写 Prompt） |

**优雅迁移保证（满足「不得影响已有模块 / 接口」）**：
- `AIManager` 解析路由时，若数据库无对应 `routing_rules` / `ai_models`，**回退到 `settings`**（即现在的行为），因此 Step4/5 未完成前系统照常工作。
- 迁移只**新增** 7 张表 + 1 个增量列，**不修改、不删除**任何已有表/列。

---

## 1. 表总览

| 表名 | 作用 | 关键关系 |
|---|---|---|
| `providers` | Provider 注册（多家 OpenAI Compatible 等） | 1:N → `ai_models` |
| `ai_models` | 模型实例（含参数/能力/高级配置） | N:1 → `providers`（可空，可独立） |
| `routing_rules` | 每个 AI 功能 → 指定模型 + fallback + 策略 | N:1 → `ai_models`；feature 唯一 |
| `prompt_templates` | Prompt 模板（按功能 key） | 1:N → `prompt_versions` |
| `prompt_versions` | Prompt 版本历史 | N:1 → `prompt_templates` |
| `model_usage` | Token / 费用 / 调用 / 失败率（按天聚合） | N:1 → `ai_models` / `providers` |
| `model_logs` | 每次调用的请求/响应/耗时/错误明细 | N:1 → `ai_models` / `providers` / `users` |
| `model_health` | 定时探测各能力状态 | N:1 → `ai_models` |

---

## 2. 逐表字段设计

### 2.1 `providers` —— Provider 管理
```text
id              UUID PK
name            String(128)  UNIQUE  显示名（硅基流动 / OpenRouter / OneAPI…）
type            String(48)   NOT NULL  见下方 Provider 类型枚举
base_url        String(512)  nullable  OpenAI Compatible 端点（如 https://api.siliconflow.cn/v1）
api_key         Text         nullable  加密存储（env 变量引用或真实 key 均可）
enabled         Boolean      default True
description     Text         nullable
created_at / updated_at     TimestampMixin
```
**Provider 类型枚举** `provider_type`：
`openai_compatible` / `openai` / `anthropic` / `gemini` / `azure` / `openrouter` / `siliconflow` / `bailian`(阿里百炼) / `volcano`(火山方舟) / `zhipu`(智谱) / `moonshot` / `deepseek` / `ollama` / `lmstudio` / `vllm` / `xinference` / `custom`
> 说明：`type` 决定 `AIManager` 用哪套 SDK 构建客户端；`openai_compatible` 覆盖绝大多数（硅基流动/OpenRouter/OneAPI/NewAPI/FastGPT/LiteLLM 等）。

### 2.2 `ai_models` —— AI 模型管理
```text
id              UUID PK
name            String(128)  NOT NULL  显示名（DeepSeek V3 / GPT-5.5 / BGE-M3…）
provider_id     UUID         FK → providers.id  nullable（为空则用本表 base_url/api_key 独立配置）
provider_type   String(48)   nullable  冗余缓存，避免每次调用 join（= provider.type）

api_key         Text         nullable  加密存储（可覆盖 provider 的 key）
base_url        String(512)  nullable  可覆盖 provider 的 base_url
model_name      String(128)  NOT NULL  实际发给 API 的模型 ID（deepseek-chat / gpt-4o…）
embedding_model String(128)  nullable  （如 BAAI/bge-m3）
vision_model    String(128)  nullable  （多模态模型 ID）
reranker_model  String(128)  nullable  （rerank 模型 ID）
embedding_dim   Integer      nullable  向量维度（用于校验/建索引，默认 1024）

temperature     Float        default 0.2
top_p           Float        default 1.0
timeout         Integer      default 60      # 秒
max_tokens      Integer      nullable

is_default      Boolean      default False  # 全局默认（应用层保证至多一个）
is_enabled      Boolean      default True

capabilities    JSONB        # 能力开关，见下方
advanced        JSONB        # 高级配置，见下方

created_at / updated_at
```
**`capabilities` JSONB 结构**（对应「高级配置」勾选项 + 测试连接探测项）：
```json
{ "chat": true, "embedding": false, "vision": false,
  "streaming": true, "json_mode": true, "function_calling": true,
  "web_search": false, "reasoning": false }
```
**`advanced` JSONB 结构**（对应「自动重试 / 并发数 / Rate Limit」）：
```json
{ "auto_retry": 3, "max_concurrency": 4,
  "rate_limit_rpm": 0, "rate_limit_tpm": 0 }   // 0 = 不限
```

### 2.3 `routing_rules` —— AI 路由规则（最重要）
```text
id              UUID PK
feature         String(64)   UNIQUE NOT NULL   LawPilot 的 AI 功能 key（见下方枚举）
model_id        UUID         FK → ai_models.id  NOT NULL
fallback_model_ids JSONB     # 有序 fallback 链，例：[uuid_claude, uuid_gpt, uuid_deepseek]
strategy        String(24)   # lowest_cost / fastest / highest_quality / balanced / custom
auto_route      Boolean      default False   # true=不固定模型，按策略+任务类型自动选
prompt_template_key String(64) nullable   # 关联 prompt_templates.key；空=内置默认
priority        Integer      default 0       # 拖拽排序用
enabled         Boolean      default True
created_at / updated_at
```
**`feature` 功能枚举**（来自需求，作为稳定 key）：
`legal_analysis`(法律分析) / `law_explain`(法条解释) / `case_summary`(案例总结) / `case_search`(案例搜索) / `case_overview`(案件总结) / `contract_review`(合同审查) / `ocr_analysis`(OCR分析) / `image_understanding`(图片理解) / `document_generation`(文书生成) / `prompt_optimize`(Prompt优化) / `workflow_planning`(Workflow规划) / `agent_reasoning`(Agent推理) / `embedding` / `reranker` / `web_search`(联网搜索) / `chat` / `timeline_generation`(时间线生成) / `evidence_analysis`(证据分析)

> **Auto Routing 行为**：当 `auto_route=true`，`AIManager` 按 `strategy` + 任务类型自动选模型（如任务含图片→vision 能力模型；Embedding→capabilities.embedding 模型；长文本→高质量模型）。首选失败 → 按 `fallback_model_ids` 顺序切换。

### 2.4 `prompt_templates` —— Prompt 管理
```text
id              UUID PK
key             String(64)   UNIQUE NOT NULL  功能 key（legal_analysis / law_search / case_summary…）
name            String(128)  NOT NULL  显示名
content         Text         NOT NULL  模板体，支持 {{variable}} 占位
variables       JSONB        # [{ "name": "user_input", "default": "", "desc": "用户输入" }, …]
enabled         Boolean      default True
current_version Integer      default 1
model_id        UUID         FK → ai_models.id  nullable  # 可选：该 prompt 固定绑定某模型
created_at / updated_at
```

### 2.5 `prompt_versions` —— Prompt 版本管理 / 历史
```text
id              UUID PK
template_id     UUID  FK → prompt_templates.id  NOT NULL  INDEX
version         Integer NOT NULL
content         Text  NOT NULL
variables       JSONB
note            String(255) nullable  变更说明
created_by      UUID  FK → users.id    nullable
created_at
UNIQUE (template_id, version)
```

### 2.6 `model_usage` —— Token 统计（按天聚合）
```text
id              UUID PK
date            Date   NOT NULL
model_id        UUID   FK → ai_models.id
provider_id     UUID   FK → providers.id  nullable
user_id         UUID   FK → users.id     nullable   # 系统调用为 NULL
tokens_in       Integer default 0
tokens_out      Integer default 0
cost            Numeric(14,6) default 0
cost_currency   String(8) default 'USD'
calls           Integer default 0
failures        Integer default 0
avg_latency_ms  Integer default 0
created_at / updated_at
UNIQUE (date, model_id, provider_id, user_id)
-- 失败率 = failures / calls（查询时计算）
```

### 2.7 `model_logs` —— 日志中心（每次调用明细）
```text
id              UUID PK
model_id        UUID   FK → ai_models.id  nullable
provider_id     UUID   FK → providers.id  nullable
user_id         UUID   FK → users.id     nullable
feature         String(64)  nullable   # 哪个 routing feature / 业务能力触发
endpoint        String(128) nullable   # 触发接口路径
capability      String(32)  nullable   # chat / embedding / vision / rerank / streaming
request_text    Text   nullable   # 请求/ prompt（可截断存储）
response_text   Text   nullable   # 模型响应（可截断存储）
tokens_in       Integer default 0
tokens_out      Integer default 0
cost            Numeric(14,6) default 0
latency_ms      Integer default 0
status          String(16)  # success / error / timeout
error_text      Text   nullable
created_at
INDEXES: (created_at DESC), (model_id), (user_id), (feature)
```

### 2.8 `model_health` —— 模型健康检测（定时探测）
```text
id              UUID PK
model_id        UUID   FK → ai_models.id  NOT NULL
provider_id     UUID   FK → providers.id  nullable
last_checked    DateTime(timezone=True)
chat_ok         Boolean
vision_ok       Boolean
embedding_ok    Boolean
streaming_ok    Boolean
json_ok         Boolean
function_calling_ok Boolean
web_ok          Boolean
status          String(16)  # healthy / degraded / down
latency_ms      Integer
error_text      Text   nullable
created_at
-- 后台定时任务 append 一条探测记录；「当前状态」= 每个 model_id 的最新一条
INDEX: (model_id, created_at DESC)
```

### 2.9 `users` —— 增量字段（不改动已有列）
```text
is_superuser    Boolean default False   # 新增：AI 能力中心仅超级管理员可访问
```

---

## 3. 索引与关系小结
- FK 全部建索引；`routing_rules.feature` 唯一；`prompt_templates.key` 唯一；`model_usage` 复合唯一；`model_logs`/`model_health` 按时间+model 建索引。
- 所有表继承 `UUIDMixin` + `TimestampMixin`（与现有模型一致）。
- `api_key` 在 `providers` 与 `ai_models` 两处均**加密存储**，读取时由 `AIManager` 解密。

---

## 4. 迁移实施计划（确认后执行）
1. 新建 `backend/app/models/ai_center.py`：8 个模型类（7 表 + 在 user.py 加 `is_superuser`）。
2. 在 `app/models/__init__.py` 追加导入（注册到 `Base.metadata`）。
3. 新增 Alembic 迁移：仅 `create_table` ×7 + `alter users add column is_superuser`；**严格裁剪，不触碰任何已有表**（沿用 research 迁移的「只留新增、删除漂移」做法）。
4. `alembic upgrade head` 应用；`init_db()` 开发环境自动建表不受影响。
5. 提供种子：默认注入 `providers`(openai_compatible 占位) 与若干 `routing_rules`（feature→默认模型），保证 `AIManager` 即使未配置也有路由雏形（回退 `settings`）。

---

## 5. 待你确认 / 可调整的点
1. **加密方式**：默认 Fernet（密钥取自 `ai_encryption_key`，回退 `secret_key`）。是否需要更严格的 KMS / 国密？
2. **管理员门槛**：新增 `is_superuser` 列，AI 能力中心后台仅超级管理员。是否同意此增量改动 `users` 表？
3. **Provider 与模型关系**：模型 `provider_id` 可空（支持「自定义」独立模型）。是否认可？
4. **`feature` 枚举**是否完整覆盖你列出的 18 项？有无需要拆分/合并？
5. **费用币种**：`cost_currency` 默认 `USD`，是否改为 `CNY` 或双字段？
