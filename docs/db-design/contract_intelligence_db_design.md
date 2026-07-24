# Contract Intelligence Center（合同智能中心）—— 第一步：数据库设计

> 目标：为 LawPilot 新增一个**独立于现有业务**的「合同智能中心」，让用户可以上传合同（PDF/DOCX/图片/扫描件/TXT/Markdown），AI 自动完成合同解析、风险识别、条款解释、风险评分、修改建议、合同摘要、关键时间提醒、自动生成审查报告。
> 原则（与既有「AI 能力中心」「AI Playground」完全一致）：**只新增表，绝不修改、不删除任何已有表/列**；复用 `users` / `ai_models` / `routing_rules` / `prompt_templates`，不重复造轮子；保持现有架构、支持 Docker + PostgreSQL + 全 Provider + 流式输出。
> 本文件仅含**设计**，不含实现代码。确认后才会生成 SQLAlchemy 模型 + Alembic 迁移。

---

## 0. 与现有架构的关系（关键决策）

| 现状（AI 能力中心 / Playground 已建） | 合同智能中心设计后 |
|---|---|
| `ai_models` 已存全部模型实例 | 合同分析记录 `model_id`（主分析模型）FK 引用，不建模型表 |
| `AI_FEATURES` 已含 `contract_review` / `ocr_analysis` / `image_understanding` / `law_explain` / `case_summary` | 合同分析**扇出多个 feature** 走 AI Routing 自动分配模型（Claude 分析 / GPT 总结 / DeepSeek 法律依据），无需新加 feature |
| `AIManager.chat` / `vision` 已统一收口 | 合同分析、OCR、条款解释全部走 `AIManager`，复用流式与路由/fallback |
| `prompt_templates` 已存功能 Prompt | 合同分析可绑定 `contract_review` 等 key，不改原表 |
| `users` 已有 `is_superuser` | 合同归属 `user_id`（FK SET NULL），不新增 users 列 |
| 证据模块已有 `upload_dir` 落盘 + 文本提取（`evidence_service._extract_text`） | 合同模块**新建自己的上传/提取**（不改动 evidence 业务），复用同一 `settings.upload_dir` 与提取思路 |
| RAG 已用 pgvector（`EmbeddingService`） | 合同内语义检索可选复用（见 `contract_chunks`，**可选**） |
| `model_usage` / `model_logs` 成本精度 `Numeric(14,6)` 默认 USD | 合同分析 token/成本沿用同精度 |

**「不修改已有业务」的保证**：
- 本模块新增 **6 张核心表 + 建议 1 张 + 可选 1 张**，全部 `CREATE TABLE`，**零 ALTER 已有表**。
- 所有外键引用 `users` / `ai_models` 一律 `ondelete="SET NULL"`，删除被引用行不会摧毁合同历史。
- AI 分析是服务层对 `AIManager` 的调用（数据操作），不改表结构，因此不触碰 AI 能力中心 Schema。

---

## 1. 表总览

| 表名 | 作用 | 对应功能 | 关键关系 |
|---|---|---|---|
| `contracts` | 合同主记录 + AI 分析结果 | 上传/解析/分析/摘要/风险总览 | N:1 → `users`；引用 `ai_models`(SET NULL) |
| `contract_versions` | 合同版本快照（Clause Compare） | 版本比较 | N:1 → `contracts` CASCADE |
| `contract_clauses` *(建议新增)* | 解析后的逐条款（Clause Analyzer 点击对象） | 条款解释/推荐修改 | N:1 → `contracts` CASCADE |
| `contract_risks` | 风险条款明细（Risk Dashboard 数据源） | 风险识别/分类/评分 | N:1 → `contracts` CASCADE |
| `contract_reports` | 生成的审查报告 | 报告生成/导出 | N:1 → `contracts` CASCADE；引用 `ai_models`(SET NULL) |
| `contract_templates` | 合同模板中心 | 模板中心 | N:1 → `users`（可公开/系统内置） |
| `contract_tasks` | 提醒 + 签署前检查清单 | 提醒中心/Checklist | N:1 → `contracts` CASCADE |
| `contract_chunks` *(可选)* | 合同内向量分块（语义检索/RAG） | 合同内 RAG | N:1 → `contracts` CASCADE |

> 你列出的 DB 清单为 `contracts / contract_versions / contract_risks / contract_reports / contract_templates / contract_tasks` 6 张。
> 我**额外建议**加入 `contract_clauses`（Clause Analyzer 必须能「点击任意条款」→ 需要逐条款记录与 AI 解释缓存），以及可选的 `contract_chunks`（合同内 RAG 语义检索，复用 pgvector）。下方均给出，可删减。

---

## 2. 常量（供后端模型/枚举复用）

```python
# 合同类型（自动分类 + 模板分类共用）
CONTRACT_TYPES = [
    "rent",          # 租房合同
    "labor",         # 劳动合同
    "sales",         # 买卖合同 / 销售合同
    "service",       # 服务合同 / 服务协议
    "nda",           # 保密协议
    "cooperation",   # 合作协议
    "loan",          # 借款合同
    "purchase",      # 采购合同
    "other",         # 其他
]

# 风险分类（Risk Dashboard 按此聚合）
CONTRACT_RISK_CATEGORIES = [
    "payment",          # 付款
    "breach",           # 违约
    "confidentiality",  # 保密
    "ip",               # 知识产权
    "termination",      # 解除合同
    "liability",        # 赔偿责任
    "force_majeure",    # 不可抗力
    "dispute",          # 争议解决
]

# 风险等级
CONTRACT_RISK_LEVELS = ["low", "medium", "high"]
# 映射中文：低 / 中 / 高

# 合同处理状态
CONTRACT_STATUS = ["uploaded", "parsing", "analyzed", "error"]

# 任务类型（contract_tasks.type）
CONTRACT_TASK_TYPES = ["reminder", "checklist"]
# reminder=提醒（到期/付款/续签）；checklist=签署前检查项

# 提醒分类
CONTRACT_REMINDER_CATEGORIES = ["expiry", "payment", "renewal", "sign_check", "other"]
# 到期 / 付款 / 续签 / 签署检查 / 其他

# 报告类型
CONTRACT_REPORT_TYPES = ["review", "summary", "full", "checklist"]
# 审查报告 / 摘要报告 / 完整报告 / 检查清单

# 合同模块允许的文件类型（独立于全局 allowed_extensions，避免改动 evidence 配置）
CONTRACT_ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg"]
```

---

## 3. 逐表字段设计

### 3.1 `contracts` —— 合同主记录 + AI 分析结果（核心）
```text
id              UUID PK
user_id         UUID  FK → users.id  SET NULL          # 归属用户；系统/匿名为 NULL
title           String(255)  nullable                  # 合同标题（默认文件名）
contract_type   String(32)   nullable                  # CONTRACT_TYPES，AI 自动分类
status          String(24)   default 'uploaded'         # uploaded/parsing/analyzed/error

# 文件与原文
file_path       String(512)  nullable                  # 原文存储路径（upload_dir）
storage_key     String(255)  nullable                  # 对象存储 key（若启用对象存储）
file_type       String(16)   nullable                  # pdf/docx/txt/md/png/jpg
file_size       Integer      nullable                  # 字节
full_text       Text         nullable                  # 解析后的纯文本全文（展示 / RAG / 条款解析）
ocr_text        Text         nullable                  # OCR 原始文本（图片/扫描件）
language        String(8)    default 'zh'
page_count      Integer      nullable

# AI 分析结果（①~⑨）
summary         Text         nullable                  # ① 一句话合同摘要
law_involved    JSONB        nullable                  # ③ 涉及法律 [{law_id, name, article, url?}]
risk_score      Integer      default 0                 # ⑤ 风险总分 0-100
risk_level      String(16)   default 'low'             # low/medium/high
risk_clauses    JSONB        nullable                  # ⑤ 高风险条款摘要（冗余缓存，详情见 contract_risks）
king_clauses    JSONB        nullable                  # ⑥ 霸王条款检测 [{clause, reason, suggestion}]
payment_risk    JSONB        nullable                  # ⑦ 付款风险 {level, detail, suggestion}
breach_risk     JSONB        nullable                  # ⑧ 违约风险
liability_risk  JSONB        nullable                  # ⑨ 赔偿责任

# 模型与用量（可追溯）
model_id        UUID  FK → ai_models.id  SET NULL      # 主分析模型（冗余显示）
analysis_meta   JSONB        nullable                  # {summary_model, review_model, legal_model, latency_ms}
token_usage     JSONB        nullable                  # {in, out, total, cost, currency}
analyzed_at     DateTime(timezone=True)  nullable

# 检查清单（Checklist，冗余缓存；明细可来自 contract_tasks type=checklist）
checklist       JSONB        nullable                  # [{item, checked, category}]

created_at / updated_at
INDEXES: (user_id), (contract_type), (risk_level), (created_at DESC)
```

### 3.2 `contract_versions` —— 版本快照（Clause Compare，功能：版本比较）
```text
id              UUID PK
contract_id     UUID  FK → contracts.id  CASCADE  NOT NULL  INDEX
version_label   String(32)   NOT NULL                  # v1 / v2 / 自定义
full_text       Text         nullable                  # 该版本全文快照
change_summary  Text         nullable                  # AI 总结本版本相对上一版的变化
diff            JSONB        nullable                  # {added:[...], removed:[...], modified:[{old,new,reason}]}
created_by      UUID  FK → users.id  SET NULL
created_at
INDEX: (contract_id)
```

### 3.3 `contract_clauses` —— 逐条款（建议新增，Clause Analyzer 点击对象）
```text
id              UUID PK
contract_id     UUID  FK → contracts.id  CASCADE  NOT NULL  INDEX
clause_no       String(32)   nullable                  # 第8条 / 8.2
section         String(64)   nullable                  # 章节标题
clause_text     Text         nullable                  # 条款原文
category        String(32)   nullable                  # 关联 CONTRACT_RISK_CATEGORIES（若已识别）
order_index     Integer      default 0

# Clause Analyzer 的 AI 结果（点击后生成并缓存，避免重复调用）
explanation     Text         nullable                  # 这一条是什么意思
risk_level      String(16)   nullable                  # low/medium/high
risk_note       Text         nullable                  # 有什么风险
suggested_version Text       nullable                  # 推荐修改版本
created_at
INDEX: (contract_id)
```
> 不建此表也能做 Clause Analyzer（前端按字符区间切分全文再请求 AI），但**缓存 AI 解释**与「条款级风险」会非常有用，强烈建议保留。

### 3.4 `contract_risks` —— 风险条款明细（Risk Dashboard 数据源）
```text
id              UUID PK
contract_id     UUID  FK → contracts.id  CASCADE  NOT NULL  INDEX
clause_ref      String(32)   nullable                  # 第8条
clause_text     Text         nullable
category        String(32)   NOT NULL                  # CONTRACT_RISK_CATEGORIES
risk_level      String(16)   default 'medium'          # low/medium/high
score           Integer      default 0                 # 0-100 该条款风险分
reason          Text         nullable                  # 风险原因
suggestion      Text         nullable                  # 修改建议
suggested_text  Text         nullable                  # 推荐修改版本
king_clause     Boolean      default False             # 是否霸王条款（⑥）
created_at
INDEXES: (contract_id), (category), (risk_level)
```

### 3.5 `contract_reports` —— 审查报告（功能：报告生成）
```text
id              UUID PK
contract_id     UUID  FK → contracts.id  CASCADE  NOT NULL  INDEX
report_type     String(24)   default 'review'           # review/summary/full/checklist
title           String(255)  nullable
content         Text         nullable                  # Markdown 报告正文
content_json    JSONB        nullable                  # 结构化报告（供前端分块渲染）
format          String(16)   default 'markdown'         # markdown/pdf/html
generated_by    UUID  FK → users.id  SET NULL
model_id        UUID  FK → ai_models.id  SET NULL      # 生成所用主模型
file_path       String(512)  nullable                  # 导出的 PDF/HTML 路径
created_at
INDEX: (contract_id)
```

### 3.6 `contract_templates` —— 合同模板中心（功能：模板中心）
```text
id              UUID PK
name            String(255)  NOT NULL
category        String(32)   NOT NULL                  # CONTRACT_TYPES
content         Text         NOT NULL                  # 模板正文，支持 {{var}} 占位
variables       JSONB        nullable                  # [{name, label, default, required, desc}]
description     Text         nullable
is_system       Boolean      default False             # 官方内置模板（不可删）
is_public       Boolean      default True              # 团队/全员共享
created_by      UUID  FK → users.id  SET NULL
usage_count     Integer      default 0                 # 使用次数（冗余）
created_at / updated_at
INDEX: (category), (is_public)
```

### 3.7 `contract_tasks` —— 提醒 + 签署前检查（功能：提醒中心 / Checklist）
```text
id              UUID PK
contract_id     UUID  FK → contracts.id  CASCADE  NOT NULL  INDEX
type            String(16)   NOT NULL                  # reminder / checklist
title           String(255)  NOT NULL
category        String(32)   nullable                  # CONTRACT_REMINDER_CATEGORIES（reminder 用）
due_date        Date         nullable                  # 提醒日期（到期/付款/续签）
remind_before_days Integer   default 7                 # 提前 N 天提醒
done            Boolean      default False
priority        String(16)   default 'normal'          # low/normal/high
note            Text         nullable
created_at / updated_at
INDEXES: (contract_id), (type), (due_date), (done)
```

### 3.8 `contract_chunks` —— 合同内向量分块（可选，RAG）
```text
id              UUID PK
contract_id     UUID  FK → contracts.id  CASCADE  NOT NULL  INDEX
chunk_index     Integer      default 0
text            Text         nullable
embedding       Vector(1024)                            # pgvector，复用现有 RAG 维度（如 BGE-M3=1024）
created_at
INDEX: (contract_id)
```
> 仅当需要「合同内语义检索 / 条款级问答 RAG」时建。如果合同分析只把全文/选中条款直接喂给 LLM，可跳过此表（更简单，先不建）。

---

## 4. 索引与关系小结
- 所有表继承 `UUIDMixin` + `TimestampMixin`（与现有模型一致），`id` 为 UUID PK。
- FK 全部建索引；`contracts` 按 `(user_id, contract_type, risk_level, created_at)` 便于列表/筛选/风控看板分页。
- `contract_risks` 按 `(contract_id, category, risk_level)` 支撑 Risk Dashboard 聚合。
- `contract_tasks` 按 `(due_date, done)` 支撑提醒扫描。
- 外键 `ondelete`：引用 `users` / `ai_models` 用 SET NULL（保留历史可读性）；级联删除仅限合同**内部**父子（contracts→versions/clauses/risks/reports/tasks/chunks）。
- `contracts.full_text` 用 Postgres `TEXT`（上限 ~1GB），合同文本通常 < 几 MB，直接存库即可，无需外部分片。

---

## 5. 迁移实施计划（确认后执行）
1. 新建 `backend/app/models/contract.py`：上述 6~8 个模型类（按确认范围）+ 常量。
2. `app/models/__init__.py` 追加导入，注册到 `Base.metadata`。
3. 新增 Alembic 迁移：**仅 `create_table`**，严格裁剪，不触碰任何已有表（沿用「只留新增、删除漂移」做法）。
4. `alembic upgrade head` 应用；开发环境 `init_db()` 自动建表不受影响。
5. 种子（可选）：注入 `contract_templates` 一批内置模板（租房/劳动/借款/合作/采购/销售/服务/保密），使「模板中心」开箱可用；可选 `contract_chunks` 仅在启用 RAG 时建。

---

## 6. 待你确认 / 可调整的点
1. **表范围**：除你列明的 6 张外，是否同意**建议新增** `contract_clauses`（Clause Analyzer 必需）？以及**可选** `contract_chunks`（合同内 RAG，先用可直接不建）？
2. **全文存储**：`contracts.full_text` 直接存 Postgres `TEXT`（简单、够用），还是只存对象存储路径 + 仅留 embedding？（建议前者）
3. **AI 分析模型分配**：分析服务扇出多个 `feature`——`contract_review`（分析/Claude）、`case_summary`（摘要/GPT）、`law_explain`（法律依据/DeepSeek）。这要求 AI 能力中心已配置对应 `routing_rules`。是否认可这种「多 feature 扇出」策略？还是只用一个 `contract_review` 一次性产出全部字段？
4. **文件类型**：合同模块使用独立允许列表 `[.pdf,.docx,.txt,.md,.png,.jpg,.jpeg]`（新增 `.md` 与更全图片类型），**不改全局** `allowed_extensions`。是否认可？
5. **OCR 策略**：图片/扫描件优先用 `AIManager.vision(feature="ocr_analysis")` 多模态提取（对中文扫描件更稳），回退 `pytesseract`。是否认可？（pytesseract 需要系统装 tesseract + 中文包；缺失时跳过，不阻断上传）
6. **提醒系统交付方式**（Step6）：先存储 `contract_tasks` + 提供「到期/即将到期」查询端点，还是本次就做定时扫描 + 站内信/邮件推送？（建议先存 + 查询，定时推送作为增强）

---

## 7. 实施进度（已落地）

| Step | 内容 | 状态 | 产物 |
|---|---|---|---|
| Step1 | 数据库设计 | ✅ 完成 | 本文档 |
| **Step2** | **OCR 与文件解析** | **✅ 完成（2026-07-22）** | 见下 |
| Step3 | AI 分析（风险/条款/摘要/评分） | ✅ 完成（2026-07-22） | 见下 |
| Step4 | 前端页面 | ✅ 完成（2026-07-23） | 见下 |
| Step5 | 报告生成 | ✅ 完成（2026-07-23） | 见下 |
| Step6 | 提醒中心 | ✅ 完成（2026-07-23） | 见下 |
| Step7 | 模板中心 | ⬜ 待开发 | 待建 `contract_templates` + 模板端点 |

### Step2 落地清单
- `backend/app/models/contract.py`：`contracts` 主表（完整字段，含后续分析列预留）+ 共享常量 `CONTRACT_TYPES` / `CONTRACT_STATUS` / `CONTRACT_ALLOWED_EXTENSIONS` 等。
- `backend/app/models/__init__.py`：注册 `Contract` 与常量。
- `backend/alembic/versions/c0ntr4ct0001_add_contracts_table.py`：仅 `create_table` 迁移（down_revision = playground），零 ALTER 已有表；已 `alembic upgrade head` 通过。
- `backend/app/contract/parser.py`：文本提取（pdf/docx/txt/md）、OCR（优先 `AIManager.vision(feature="ocr_analysis")`，回退 `pytesseract`）、AI 自动分类（优先 `contract_review` json_mode，回退关键词启发式）。全程优雅降级。
- `backend/app/contract/service.py`：`ContractService`（create / update_after_parse / get / list_for_user / delete）。
- `backend/app/schemas/contract.py`：`ContractOut` / `ContractDetailOut` / `ContractUploadResponse`。
- `backend/app/contract/router.py`：`POST /api/contracts/upload`、`GET /api/contracts`、`GET /api/contracts/{id}`、`DELETE /api/contracts/{id}`；`main.py` 挂载 + OpenAPI tag `contracts`。
- 验证：`py_compile` 通过；`Base.metadata` 含 `contracts`；openapi 含 4 路由且均要求 Bearer；TestClient 端到端跑通（上传/列表/详情/删除，fake key 下分类优雅回退为 `rent`）。

> 已知约束：运行中的后端需**重启**才能加载新增的 `/api/contracts/*` 路由（旧进程无此路由）。

### Step3 落地清单（AI 分析）
- `backend/app/models/contract.py`：新增 `ContractRisk`（风险明细，category/risk_level/score/reason/suggestion/suggested_text/king_clause）+ `ContractClause`（逐条款，clause_no/section/clause_text/explanation/risk_level/risk_note/suggested_version），均 CASCADE FK → contracts；注册到 `__init__.py` + `__all__`。
- `backend/alembic/versions/c0ntr4ct0002_add_risks_clauses.py`：仅 `create_table` 建 `contract_risks` + `contract_clauses`（down_revision=c0ntr4ct0001），零 ALTER 已有表；已 `alembic upgrade head` 通过。
- `backend/app/contract/analyzer.py`（NEW）：`analyze_contract(contract, db, mgr, user_id)` 编排：
  - 扇出 `contract_review`（json_mode）→ 风险清单/评分/摘要/涉及法律/霸王条款/付款·违约·赔偿风险/检查清单；优先 `AIManager.chat_model`（取 token/延迟/模型）回退 `AIManager.chat`（settings 回退）；
  - 扇出 `law_explain`（json_mode）→ 逐条款解释；
  - 启发式 `split_clauses()` 切分中文条款（第一条/1./一、/（一）），AI 不可用也能产出条款骨架；
  - 写入子表前先 `delete` 旧 risks/clauses 保证可重入；回写 contracts 分析列；`analysis_meta.ai_available` 标记 AI 是否可用。
  - 全程 try/except 优雅降级：AI 返回 None → `ai_available=False`，仍完成结构化解（无 risk、有 clause 骨架），合同标记 `analyzed`。
- `backend/app/contract/service.py`：新增 `get_risks` / `get_clauses`（按 score 降序 / order_index 升序）。
- `backend/app/schemas/contract.py`：新增 `ContractRiskOut` / `ContractClauseOut`；`ContractDetailOut` 增加 `risks` / `clauses` 列表字段。
- `backend/app/contract/router.py`：新增 `POST /api/contracts/{id}/analyze`、`GET /api/contracts/{id}/risks`、`GET /api/contracts/{id}/clauses`；详情端点补全 risks/clauses；新增 `_build_detail` 组装助手。
- 验证：`py_compile` 通过；`Base.metadata` 含两张新表；`openapi()` 含 3 新路由；`alembic upgrade head` 成功；TestClient 端到端（上传→分析→risks→clauses→detail→重入 analyze→删除→404）全过，fake key 下 `ai_available=False` 但条款切分正常（8 条）。另顺手修正分类启发式顺序（nda 移至最后，避免正文含「保密」误判整份为保密协议）。

> 备注：`POST /api/contracts/analyze` 需要真实 AI key（配置 `routing_rules` 的 `contract_review` / `law_explain` feature，或 settings 回退）才能产出 risks / 条款解释；当前演示环境为 fake key，已验证优雅降级路径。

### Step5 落地清单（报告生成）
- `backend/app/models/contract.py`：新增 `ContractReport`（report_type/title/content/content_json/format/generated_by/model_id/file_path，CASCADE FK→contracts，generated_by/model_id SET NULL）；注册到 `__init__.py` + `__all__`。
- `backend/alembic/versions/c0ntr4ct0003_add_reports.py`：仅 `create_table` 建 `contract_reports`（down_revision=c0ntr4ct0002），零 ALTER 已有表；已 `alembic upgrade head`。**注意**：首版漏写 `created_at`/`updated_at` 的 `server_default`，导致插入报 NOT NULL；已补 `server_default=sa.text('now()')` 并 `downgrade c0ntr4ct0002` + `upgrade head` 重放（dev 空表）。
- `backend/app/contract/report.py`（NEW）：`build_report_markdown(contract, risks, clauses, report_type, narrative)`（按 review/summary/full/checklist 拼装 Markdown + content_json）+ `generate_report(contract, db, mgr, user_id, report_type, regenerate)`（加载 risks/clauses，可选 AI 叙事 `case_summary`，存 `contract_reports`，同类型先删后插保证唯一，可重入），全程优雅降级（`ai_assisted=False` 时仍产出完整规则报告）。
- `backend/app/contract/service.py`：新增 `get_report`（指定类型最新一条）/ `list_reports`（倒序）。
- `backend/app/schemas/contract.py`：新增 `ContractReportOut`。
- `backend/app/contract/router.py`：新增 `GET /api/contracts/{id}/report`（report_type + regenerate）与 `GET /api/contracts/{id}/reports`（列表）；更新模块 docstring。
- 前端：`frontend/src/lib/api.ts` 新增 `ContractReportOut` + `api.contracts.report/reports`；`frontend/src/components/Markdown.tsx`（NEW，自包含、XSS 安全、React 节点渲染，支持标题/加粗/列表/引用/代码围栏/分隔线/`<details>` 折叠）；详情页新增「审查报告」按钮跳 `/contracts/[id]/report`；`frontend/src/app/contracts/[id]/report/page.tsx`（NEW，类型 Tab + Markdown 渲染 + 重新生成 + 降级徽章）。
- 验证：`py_compile` 全过；`Base.metadata` 含 `contract_reports`；`openapi()` 含 2 新路由；`alembic upgrade head` 成功；TestClient 端到端（上传→分析→report(review/summary)→缓存命中→regenerate→列表→删除→404）全过，fake key 下 `ai_assisted=False` 规则生成正常。前端 `npx tsc --noEmit` 0 错误；`next build` 通过（/contracts/[id]/report 动态编译成功）。

### Step6 落地清单（提醒中心）
- `backend/app/models/contract.py`：新增 `ContractTask`（type/title/category/due_date/remind_before_days/done/priority/note，CASCADE FK→contracts，索引 `(due_date,done)`）；引入 `Date`；注册到 `__init__.py` + `__all__`；常量 `CONTRACT_TASK_TYPES=["reminder","checklist"]`、`CONTRACT_REMINDER_CATEGORIES=["expiry","payment","renewal","sign_check","other"]`。
- `backend/alembic/versions/c0ntr4ct0004_add_tasks.py`（NEW）：仅 `create_table` 建 `contract_tasks`（down_revision=c0ntr4ct0003），时间戳与默认值均带 `server_default`；已 `alembic upgrade head`。**注意**：首版 `ContractTask` 用 `Date` 但 `models/contract.py` 未 import `Date` → `NameError`；已补 `from sqlalchemy import ... Date`。
- `backend/app/contract/service.py`：新增 `create_task` / `get_task` / `list_tasks(contract_id, type)`（按 due_date 升序 null 最后）/ `list_upcoming(user_id, days=30)`（JOIN contracts，过滤 `type=reminder, done=False, due_date<=today+days`，含逾期，返回 `(task, contract_title)`）/ `update_task`（字段白名单）/ `delete_task`。
- `backend/app/schemas/contract.py`：新增 `ContractTaskOut`（含 `contract_title?: string|null`）/ `ContractTaskCreate` / `ContractTaskUpdate`。
- `backend/app/contract/router.py`：新增 5 个端点——`GET /api/contracts/{id}/tasks`（type 过滤）、`POST /api/contracts/{id}/tasks`（201，回填 contract_title）、`PATCH /api/contracts/{id}/tasks/{task_id}`、`DELETE /api/contracts/{id}/tasks/{task_id}`、`GET /api/contracts/tasks/upcoming`（聚合当前用户提醒，Query `days=30`）。更新模块 docstring。
- 前端：`frontend/src/lib/api.ts` 新增 `ContractTaskType` / `ContractTaskPriority` / `ContractTaskCategory` / `ContractTaskOut` / `ContractTaskCreate` / `ContractTaskUpdate`；`api.contracts` 新增 `tasks(id, type?)` / `createTask(id, body)` / `updateTask(id, tid, body)` / `deleteTask(id, tid)` / `upcoming(days=30)`。
- `frontend/src/lib/constants.ts`：新增 `contractReminderCategoryLabels`+`contractReminderCategoryTone`（expiry/payment/renewal/sign_check/other）、`contractPriorityLabels`+`contractPriorityTone`（low/normal/high/urgent）、`contractTaskTypeLabels`，取值与后端一致。
- `frontend/src/app/contracts/reminders/page.tsx`（NEW）：提醒中心聚合页——按 `days`(7/30/90) 拉取 `upcoming`，区分「逾期 / 临近到期」两组，卡片含分类/优先级徽章、距今天数、关联合同链接；支持勾选完成、删除、以及「新建提醒」弹窗（选合同 + 标题 + 分类 + 到期日 + 优先级 + 提前提醒天数 + 备注，调用 `createTask`）。
- `frontend/src/app/contracts/page.tsx`：首页头部新增「🔔 提醒中心」入口按钮（链 `/contracts/reminders`）。
- `frontend/src/app/contracts/[id]/page.tsx`：详情页新增「提醒 / 待办」面板（加载 `tasks(id)`，内联新建提醒/待办、勾选完成、删除、链「🔔 提醒中心」）。
- 验证：`py_compile` 全过；`Base.metadata` 含 `contract_tasks`；`openapi()` 含 3 新路由；`alembic upgrade head` 成功；聚焦端到端脚本 `scripts/e2e_step6_upcoming.py` 全过（上传→建 10 天提醒→upcoming 返回 1 且 contract_title 正确→标记 done→upcoming 归 0→建逾期提醒→upcoming 含逾期项→删合同→404）。前端 `npx tsc --noEmit` 0 错误；`next build` 进行中。

### Step4 落地清单（前端页面）
- `frontend/src/lib/api.ts`：新增 `ContractType` / `ContractStatus` / `ContractRiskLevel` / `ContractRiskCategory` 类型，`ContractOut` / `ContractRiskOut` / `ContractClauseOut` / `ContractDetailOut` / `ContractUploadResponse`；`api.contracts` 对象（upload / list / get / analyze / risks / clauses / remove）。upload 复用 uploadEvidence 的手动 fetch 模式（FormData 不强制 JSON）。
- `frontend/src/lib/constants.ts`：新增 `contractTypeLabels` / `contractStatusLabels`+`contractStatusTone` / `contractRiskLevelLabels`+`contractRiskLevelTone` / `contractRiskCategoryLabels` / `contractAllowedExtensions`，取值与后端 contract.py 常量一致。
- `frontend/src/components/AppShell.tsx`：顶部导航新增「📄 合同中心」→ /contracts（与「我的案件」同级，所有用户可见）。
- `frontend/src/app/contracts/page.tsx`（NEW）：合同中心首页——拖拽/点击上传（含支持类型提示 + 客户端扩展名校验）、上传后跳转详情；类型/状态筛选（后端过滤）+ 标题客户端过滤；卡片列表含类型/状态/风险等级徽章、摘要、删除（确认）。
- `frontend/src/app/contracts/[id]/page.tsx`（NEW）：详情页左右布局——左列「合同全文」+「条款导航树」（点击选中并高亮）；右列「AI 分析总览」（风险评分条 + 摘要 + 分析时间）、「风险看板」（按 score 降序，含类别/等级/霸王条款/原因/建议）、「Clause Analyzer」（选中条款的解释/风险/推荐修改）、「签署前检查清单」；右上「AI 分析 / 重新分析」按钮；`ai_available=false` 时显示「AI 暂不可用（演示降级）」徽章。
- 验证：`npx tsc --noEmit` 0 错误；`npx next build` 成功（/contracts 静态预渲染、/contracts/[id] 动态编译均通过）。运行期 `next start` 因沙箱 fork 资源限制（errno 11）未能起服务，但 build 静态生成已证明 SSR 不抛错。
