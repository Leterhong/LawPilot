# AI Playground（AI 模型测试中心）—— 第一步：数据库设计

> 目标：为 LawPilot 新增一个**独立于业务**的「模型实验室」，让用户可以测试/对比/评测模型、调试 Prompt、连接 AI Routing 并一键发布到生产。
> 原则（与既有「AI 能力中心」一致）：**只新增表，绝不修改、不删除任何已有表/列**；复用 `ai_models` / `routing_rules` / `prompt_templates` / `users`，不重复造轮子；保持现有架构、支持 Docker + PostgreSQL + 全 Provider + 流式输出。
> 本文件仅含**设计**，不含实现代码。确认后才会生成 SQLAlchemy 模型 + Alembic 迁移。

---

## 0. 与现有架构的关系（关键决策）

| 现状（AI 能力中心已建） | Playground 设计后 |
|---|---|
| `ai_models` 已存全部模型实例（参数/能力/Provider） | Playground **直接 FK 引用** `ai_models.id`，不再建「模型表」 |
| `routing_rules` 已存「功能 → 模型 + fallback」 | Playground 路由测试读取它；「应用到生产」通过 `ai_center_service` **UPDATE** 它（数据操作，不改表结构） |
| `prompt_templates` 已存功能 Prompt | Playground Prompt 测试可加载它；用户收藏存到独立 `prompt_library` |
| `users` 已有 `is_superuser` | Playground 历史/收藏归属 `user_id`（FK，SET NULL），不新增 users 列 |
| `AIManager` 已统一收口所有模型调用 | Playground 全部走 `AIManager.chat/embedding/vision/rerank`，复用流式与路由 |
| 成本统计：`model_usage` 用 `Numeric(14,6)` 默认 USD | Playground 沿用同精度；「预计成本」靠新增 `model_pricing`（不碰 `ai_models`） |

**「不修改已有业务」的保证**：
- 本模块新增 **7 张核心表 + 2 张可选表**，全部 `CREATE TABLE`，**零 ALTER 已有表**。
- 所有外键引用 `ai_models` / `routing_rules` / `prompt_templates` / `users` 一律 `ondelete="SET NULL"`，删除被引用行不会摧毁 Playground 历史。
- 「应用到生产」是服务层的 `UPDATE routing_rules`（数据变更），不在本模块迁移脚本里改表，因此不触碰 AI 能力中心 Schema。

---

## 1. 表总览

| 表名 | 作用 | 对应功能 | 关键关系 |
|---|---|---|---|
| `playground_sessions` | 测试历史（单测/对比/Prompt/路由测试的统一记录） | 功能1/2/3/5/6 | N:1 → `users`；引用 `ai_models`(JSONB) |
| `model_comparisons` | 多模型对比中**每个模型**的逐条结果 | 功能2 | N:1 → `playground_sessions`；N:1 → `ai_models`(SET NULL) |
| `evaluation_datasets` | 评测测试集（元数据） | 功能4 | N:1 → `users` |
| `evaluation_items` | 测试集内的单条题目 | 功能4 | N:1 → `evaluation_datasets` |
| `evaluation_tasks` | 一次评测运行 | 功能4 | N:1 → `users`/`evaluation_datasets`/`ai_models`(judge) |
| `evaluation_results` | 评测中**每题每模型**的结果 | 功能4 | N:1 → `evaluation_tasks`/`evaluation_items`/`ai_models` |
| `prompt_library` | 收藏的优秀 Prompt | 功能3/7 | N:1 → `users`（可公开） |
| `model_pricing` *(可选)* | 模型单价（用于「预计成本」） | 全局 | 1:1 → `ai_models`（不修改原表） |
| `playground_publishes` *(可选)* | 「应用到生产」审计日志 | 功能8 | N:1 → `users`/`playground_sessions`/`routing_rules` |

> 说明：你列出的 DB 清单为 `playground_sessions / model_comparisons / evaluation_tasks / evaluation_results / prompt_library` 5 张。我**额外建议**加入 `evaluation_datasets` + `evaluation_items`（功能4「创建测试集」必须有可复用实体，否则无法支撑 100 题级评测），以及可选的 `model_pricing`（成本预估）与 `playground_publishes`（发布审计）。下方均给出，可删减。

---

## 2. 常量（供后端模型/枚举复用）

```python
# 测试模式（playground_sessions.type）
PLAYGROUND_TYPES = ["single", "compare", "prompt", "evaluate", "routing"]
# 映射中文：单模型测试 / 多模型对比 / Prompt测试 / 模型评测 / AI路由测试

# 会话状态
SESSION_STATUS = ["success", "error", "timeout", "partial"]

# 评测任务状态
EVAL_STATUS = ["pending", "running", "done", "error", "partial"]

# AI 自动评分维度（功能2 多模型对比 & 功能4 评测共用）
SCORE_DIMS = ["accuracy", "completeness", "professionalism", "logic", "format", "citation"]
# 中文：准确性 / 完整性 / 专业性 / 逻辑性 / 格式 / 引用质量

# Prompt 变量（功能3）
PROMPT_VARIABLES = ["case", "law", "context", "document"]
# 可扩展：user_input / query / contract …

# 评测指标（功能4 报告）
EVAL_METRICS = ["accuracy", "latency", "token_cost", "stability", "hallucination_rate", "json_success_rate"]
```

---

## 3. 逐表字段设计

### 3.1 `playground_sessions` —— 测试历史（核心统一表）
```text
id              UUID PK
user_id         UUID  FK → users.id  SET NULL          # 匿名/系统为 NULL
type            String(24)  NOT NULL                   # single/compare/prompt/evaluate/routing
title           String(255)  nullable                  # 会话标题（用户可命名）
model_ids       JSONB                                # 选中模型 id 列表（single=[1], compare=[多个]）
feature         String(64)   nullable                  # 关联 routing_rules.feature（routing/评测用）
system_prompt   Text         nullable
user_prompt     Text         nullable
context         Text         nullable
files           JSONB        nullable                  # 上传文件元信息 [{name,size,type,storage_key}]
params          JSONB                                # {temperature, top_p, max_tokens, streaming, ...}
input           JSONB                                # 完整输入快照（可重放）
output          JSONB                                # 主结果（single=单模型结果；compare=摘要；prompt=渲染后+输出；routing=各模型结果摘要）
score           Float        nullable                  # 自动评分总分（若有）
score_detail    JSONB        nullable                  # {accuracy, completeness, professionalism, logic, format, citation}
token_usage     JSONB                                # {in, out, total, cost}
latency_ms      Integer       default 0
status          String(16)   default 'success'         # success/error/timeout/partial
error_text      Text         nullable
created_at
INDEXES: (user_id), (type), (feature), (created_at DESC)
```

### 3.2 `model_comparisons` —— 多模型对比逐条结果（功能2）
```text
id              UUID PK
session_id      UUID  FK → playground_sessions.id  CASCADE  NOT NULL  INDEX
model_id        UUID  FK → ai_models.id  SET NULL  nullable   # 模型删除仍可读历史
model_name      String(128)                            # 冗余缓存显示名
provider_id     UUID  FK → providers.id  SET NULL  nullable
provider_name   String(128)  nullable                  # 冗余缓存
response        Text  nullable                         # 模型输出
tokens_in       Integer default 0
tokens_out      Integer default 0
cost            Numeric(14,6) default 0
latency_ms      Integer default 0
score           Float nullable                         # 该模型 AI 评分总分
score_detail    JSONB nullable                         # 各维度评分
status          String(16) default 'success'
error_text      Text nullable
created_at
INDEX: (session_id)
```

### 3.3 `evaluation_datasets` —— 测试集元数据（功能4，建议新增）
```text
id              UUID PK
user_id         UUID  FK → users.id  SET NULL
name            String(255)  NOT NULL
category        String(64)   nullable                  # 关联 AI_FEATURES：legal_analysis/case_summary/contract_review…
description     Text  nullable
is_public       Boolean      default False
item_count      Integer       default 0                 # 冗余缓存题目数
created_at / updated_at
```

### 3.4 `evaluation_items` —— 测试集单题（功能4，建议新增）
```text
id              UUID PK
dataset_id      UUID  FK → evaluation_datasets.id  CASCADE  NOT NULL  INDEX
input           Text  NOT NULL                       # 测试问题/输入
expected        Text  nullable                       # 期望答案/参考答案（用于准确率判定）
context         Text  nullable                       # 附加上下文（案例/法条/合同原文）
meta            JSONB nullable
order_index     Integer default 0
created_at
```

### 3.5 `evaluation_tasks` —— 评测运行（功能4）
```text
id              UUID PK
user_id         UUID  FK → users.id  SET NULL
dataset_id      UUID  FK → evaluation_datasets.id  SET NULL   # 也可内联（未建数据集时直接带 items）
name            String(255)  NOT NULL
model_ids       JSONB                                # 被测模型 id 列表（支持一次测多个）
judge_model_id  UUID  FK → ai_models.id  SET NULL    # LLM Judge 评分模型
feature         String(64)   nullable                # 关联 routing_rules.feature / AI_FEATURES
prompt_template_key String(64) nullable              # 使用的 prompt 模板 key
config          JSONB                                # {temperature, top_p, max_tokens, streaming, ...}
status          String(16)   default 'pending'        # pending/running/done/error/partial
total_items     Integer      default 0
processed_items Integer      default 0
score_summary   JSONB nullable                        # {avg_score, avg_latency, avg_cost, accuracy, json_success_rate, hallucination_rate, stability}
started_at      DateTime(timezone=True) nullable
finished_at     DateTime(timezone=True) nullable
created_at
INDEXES: (user_id), (status)
```

### 3.6 `evaluation_results` —— 评测逐题结果（功能4）
```text
id              UUID PK
task_id         UUID  FK → evaluation_tasks.id  CASCADE  NOT NULL  INDEX
item_id         UUID  FK → evaluation_items.id  SET NULL
model_id        UUID  FK → ai_models.id  SET NULL
input           Text  nullable
expected        Text  nullable
output          Text  nullable
is_correct      Boolean nullable                      # 准确率（与 expected 比对 / judge 判定）
is_json_valid   Boolean nullable                      # JSON 格式成功率
has_hallucination Boolean nullable                    # 幻觉标记
score           Float nullable                         # judge 评分 0-100
metrics         JSONB                                # {accuracy, latency_ms, tokens_in, tokens_out, cost, stability}
latency_ms      Integer default 0
tokens_in       Integer default 0
tokens_out      Integer default 0
cost            Numeric(14,6) default 0
error_text      Text nullable
created_at
INDEX: (task_id)
```

### 3.7 `prompt_library` —— 收藏的优秀 Prompt（功能3/7）
```text
id              UUID PK
user_id         UUID  FK → users.id  SET NULL         # 个人收藏；is_public=True 则团队共享
name            String(255)  NOT NULL
category        String(64)   nullable                 # legal_analysis/contract_review… 或自由分类
prompt          Text  NOT NULL                        # 完整 prompt（可含 system+user，支持 {{var}}）
variables       JSONB                                # [{name, default, desc}] 变量定义
score           Float nullable                         # 历史最佳得分
tags            JSONB nullable
is_public       Boolean      default False
created_at / updated_at
```

### 3.8 `model_pricing` —— 模型单价（可选，用于「预计成本」）
```text
id                  UUID PK
model_id            UUID  FK → ai_models.id  CASCADE  NOT NULL  UNIQUE
price_in_per_1k     Numeric(10,6) default 0           # 输入单价（每 1k token）
price_out_per_1k    Numeric(10,6) default 0           # 输出单价（每 1k token）
currency            String(8)      default 'USD'
note                Text  nullable
created_at / updated_at
```
> 不修改 `ai_models`；未配置单价时成本显示「--」或按默认估算。

### 3.9 `playground_publishes` —— 发布审计（可选，功能8）
```text
id              UUID PK
user_id         UUID  FK → users.id  SET NULL
session_id      UUID  FK → playground_sessions.id  SET NULL
feature         String(64)   NOT NULL                # 被改写的 routing feature
from_model_id   UUID  nullable
to_model_id     UUID  FK → ai_models.id  SET NULL    # 新默认模型
routing_rule_id UUID  FK → routing_rules.id  SET NULL
note            Text  nullable
created_at
```

---

## 4. 索引与关系小结
- 所有表继承 `UUIDMixin` + `TimestampMixin`（与现有模型一致），`id` 为 UUID PK。
- FK 全部建索引；`playground_sessions` 按 `(user_id, type, created_at)` 便于历史分页；`model_comparisons` / `evaluation_results` 按 `session_id` / `task_id` 建索引。
- 外键 `ondelete` 策略：`playground_sessions` ↔ `users` 用 SET NULL；`model_comparisons` ↔ `ai_models`/`providers` 用 SET NULL（保留历史可读性）；级联删除仅限 Playground **内部**父子（sessions→comparisons、datasets→items、tasks→results）。
- `model_pricing.model_id` 用 CASCADE（模型删除则定价随之删除，不影响历史——历史存 `token_usage` 快照）。

---

## 5. 迁移实施计划（确认后执行）
1. 新建 `backend/app/models/playground.py`：上述 7~9 个模型类（按确认范围）。
2. `app/models/__init__.py` 追加导入，注册到 `Base.metadata`。
3. 新增 Alembic 迁移：**仅 `create_table`**，严格裁剪，不触碰任何已有表（沿用 AI 能力中心的「只留新增、删除漂移」做法）。
4. `alembic upgrade head` 应用；开发环境 `init_db()` 自动建表不受影响。
5. 种子（可选）：注入 `prompt_library` 几条示例法律 Prompt；`model_pricing` 给种子模型填默认单价，使「预计成本」开箱可用。

---

## 6. 待你确认 / 可调整的点
1. **表范围**：除你列明的 5 张外，是否同意加入 `evaluation_datasets` + `evaluation_items`（功能4 必需）？以及可选 `model_pricing` / `playground_publishes`？
2. **成本币种**：沿用 `USD` 还是改 `CNY` / 双字段？（与 AI 能力中心 `model_usage` 保持一致）
3. **Prompt 收藏归属**：`prompt_library.user_id` 允许 NULL＝全局共享模板；是否要区分「个人/团队/官方」三级？
4. **评测判定方式**：`is_correct` / `has_hallucination` 由 LLM Judge 判定还是规则比对 `expected`？Judge 模型是否固定为某个 `ai_models` 条目（如 GPT/Claude）？
5. **「应用到生产」权限**：是否限定仅 `is_superuser` 可发布改写 `routing_rules`？（建议：是，与 AI 能力中心门禁一致）
6. **文件上传**：`files` 仅存元信息；实际文件落在对象存储/RAG，Playground 不存原文。是否认可？
