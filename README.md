# LawPilot

> 让每个人都拥有自己的 AI 法律办事助手

LawPilot 不是法律聊天机器人，也不是 AI 律师或法条查询网站，而是一个 **法律问题解决平台（Legal Workflow Platform）**。

产品的使命是：让一个完全不懂法律的人，输入自己的遭遇后，最终能够清楚知道——

- 我属于什么问题
- 我的权益是什么
- 我要准备什么
- 我应该去哪里
- 我要找哪个部门
- 下一步怎么办
- 什么时候起诉

AI 负责陪伴用户的整个维权过程，而不只是回答问题。

---

## 产品理念

> AI 不是回答问题，AI 负责解决问题。

用户真正想得到的是「今天我要干什么」，而不是「民法典第 XXX 条」。

---

## ✨ 功能模块

LawPilot 由多个可独立使用的法律能力模块组成，统一通过前端导航访问：

| 模块 | 说明 | 前端路由 |
| --- | --- | --- |
| 智能维权助手（Agent） | 对话式流程引擎：识别问题 → 追问澄清 → 生成行动报告与路线图 | `/` |
| 法律法规检索 | 法条检索、收藏与检索历史，支持向量 + 关键词混合检索 | `/laws` |
| 案例检索 | 司法案例 / 裁判要旨检索与详情阅读 | `/case-search` |
| 案件中心 | 个人案件管理（材料、时间线、待办），分为「我的案件」与「案件工作台」 | `/cases`、`/case-center` |
| 合同智能审查 | 上传合同 → 条款解析 → 风险标注 → 审查报告 + 到期提醒 | `/contracts` |
| 🗂️ 证据中心 | 证据上传 / OCR / 智能分析 / 关联关系链 / 时间线 / 一键生成证据报告 | `/evidence-center` |
| AI 能力中心 | 大模型供应商、模型、提示词、路由与调用统计的统一管理后台 | `/settings/ai-center` |
| AI Playground | 提示词 / 单测 / 对比 / 评测 / 路由测试的一体化实验台 | `/settings/playground` |
| 法律研究 | 围绕特定主题的多轮研究任务管理与结果沉淀 | `/research` |
| 账户体系 | 注册、登录、JWT 鉴权 | `/login`、`/register` |

> 各模块后端均提供 RESTful API，文档见运行后的 `http://localhost:8000/docs`（OpenAPI）。

---

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Next.js 14 (App Router) · React 18 · TypeScript · Tailwind CSS · Radix UI |
| 后端 | FastAPI · Python (async) · Pydantic v2 · SQLAlchemy 2 (async) |
| 数据库 | PostgreSQL（含 pgvector 向量扩展） |
| 缓存 / 队列 | Redis |
| 向量检索 | pgvector + BGE-M3 Embedding + 混合检索 + Rerank |
| 大模型 | OpenAI Compatible API（可切换多家供应商） |
| 迁移 | Alembic |
| 部署 | Docker · Docker Compose · Nginx |

---

## 目录结构

```text
LawPilot/
├── README.md                 # 本文件
├── .env.example              # 环境变量模板（复制为 .env 后填写）
├── .gitignore
├── docker-compose.yml        # 通用基线（生产倾向：不暴露内部端口，仅 Nginx 80）
├── docker-compose.dev.yml    # 开发叠加（暴露端口 + 后端源码热重载）
├── docker-compose.prod.yml   # 生产叠加（production 环境 / 前端构建参数）
├── Makefile                  # 常用命令（dev / deploy / seed / migrate / lint）
├── scripts/
│   └── init.sh               # 一键生产部署（迁移 + 灌库 + 起服务）
├── nginx/                    # Nginx 反代配置
│   └── nginx.conf
├── docs/
│   ├── db-design/            # 各模块数据库设计文档（markdown）
│   └── competition/          # 赛事材料（差距评估 / One Pager / AI 与数据来源说明）
├── .github/workflows/        # CI（后端规范与测试、前端构建、编排校验）
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── main.py           # 应用入口（ASGI）
│   │   ├── core/             # 配置、数据库、安全、加密、依赖注入
│   │   │   ├── config.py     # 配置（来自环境变量）
│   │   │   ├── database.py   # 异步数据库引擎 / Session
│   │   │   ├── security.py   # JWT / 密码哈希
│   │   │   ├── crypto.py     # 字段级加密（敏感数据）
│   │   │   ├── keys.py       # 密钥管理
│   │   │   └── deps.py       # 路由依赖（当前用户、事务等）
│   │   ├── api/              # 路由层
│   │   │   ├── v1/           # 版本化 REST API（agent/auth/cases/evidence/...）
│   │   │   ├── case_center.py, laws.py, legal_cases.py, research.py, ai_center.py
│   │   ├── models/           # SQLAlchemy ORM 模型（user/case/contract/evidence/...）
│   │   ├── schemas/          # Pydantic 输入 / 输出模型
│   │   ├── services/         # 业务逻辑（agent / ai / rag / llm + 各模块 service）
│   │   ├── repositories/     # 数据访问层
│   │   ├── contract/         # 合同智能模块（解析 / 分析 / 报告 / 路由）
│   │   ├── playground/       # AI Playground 模块（单测 / 评测 / 路由测试）
│   │   └── utils/            # 工具（文件存储等）
│   ├── alembic/              # 数据库迁移（versions/ 存放迁移脚本）
│   ├── scripts/              # 种子 / 校验 / 建库脚本
│   │   ├── make_superuser.py # 创建管理员账号
│   │   ├── ingest_knowledge.py
│   │   ├── seed_*.py         # 各模块种子数据
│   │   └── verify_*.py       # 各模块自检脚本
│   ├── sample_data/          # 种子数据（legal_seed.jsonl 等）
│   ├── reports_sample/       # 报告样例
│   ├── tests/
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── .dockerignore
└── frontend/                 # Next.js 前端
    ├── src/
    │   ├── app/              # 路由页面（首页 / 案件 / 合同 / 证据中心 / 设置 ...）
    │   ├── components/       # UI 组件（AppShell、ui、Markdown、ai-center/、playground/）
    │   ├── lib/             # 工具与 API 客户端（api.ts、auth.tsx、constants.ts、utils.ts）
    │   └── styles/
    ├── package.json
    ├── tsconfig.json
    ├── next.config.mjs
    ├── tailwind.config.ts
    ├── postcss.config.js
    ├── Dockerfile
    └── .dockerignore
```

---

## 研发阶段（Phase）

本项目采用真实软件工程流程，分阶段交付：

| Phase | 内容 | 状态 |
| --- | --- | --- |
| Phase 1 | 项目初始化（工程地基 / 基础设施编排） | ✅ 已完成 |
| Phase 2 | 数据库设计（Schema / 模型 / 迁移） | ✅ 已完成 |
| Phase 3 | 后端 API（RESTful / OpenAPI） | ✅ 已完成 |
| Phase 4 | 前端 UI（苹果风极简 / 各功能模块） | ✅ 已完成 |
| Phase 5 | RAG 知识库（切块 / Embedding / 混合检索 / Rerank） | ✅ 已完成 |
| Phase 6 | Agent 流程引擎（识别 → 追问 → 报告） | ✅ 已完成 |
| Phase 7 | Docker 部署（编排 / Nginx / 生产配置） | ✅ 已完成 |
| 扩展模块 | 证据中心 / 合同智能 / AI 能力中心 / Playground / 研究 | ✅ 已完成 |
| **v1.1 质量升级** | **个性化报告引擎 / 99 项自动化测试 / CI / 生产安全自检** | ✅ 已完成 |

---

## 质量保障

本项目把"能跑通"当作可验证的工程指标，而不是口头承诺。

| 手段 | 命令 | 当前状态 |
| --- | --- | --- |
| 后端静态检查 | `cd backend && ruff check app` | 全部通过 |
| 后端单元测试 | `cd backend && pytest -q` | **99 项通过** |
| 前端类型检查 | `cd frontend && npx tsc --noEmit` | 0 错误 |
| 前端生产构建 | `cd frontend && npm run build` | 23 条路由通过 |
| 编排配置校验 | `docker compose config -q` | 三套叠加均通过 |
| CI 流水线 | `.github/workflows/ci.yml` | 三个 job 覆盖上述全部 |

测试不依赖 PostgreSQL / Redis / 模型密钥，可在裸环境与 CI 中秒级全量运行，覆盖：

- **安全**：JWT 签发/篡改/过期/受众校验、bcrypt 加盐、生产环境弱密钥拦截
- **RAG**：RRF 融合的单调性与去重、引用可回溯、摘要截断
- **业务完整性**：8 类案由的追问脚本与知识模板无空壳、字段 id 无重复
- **防幻觉**：法条引用越界即作废、JSON 破损回退、模型超时不抛异常
- **API 契约**：134 个操作的 operationId 唯一、分组标签齐备、关键端点已挂载

### 报告生成的两段式设计

案件报告的正文由两段构成，保证"有 AI 时更聪明，没有 AI 时不出错"：

1. **确定性底座**：案由模板 + RAG 检索法条。任何时候都成立。
2. **个性化增强**：把逐条追问收集到的事实连同法条交给模型，生成针对本案的结论、权益、对方责任、风险与取证建议。

模型未配置、超时或输出不合规时自动回退第 1 段，**报告不会降级为空白**。`report.meta` 记录本次实际使用的生成来源，前端在报告页顶部标注「AI 个性化分析」或「规则模板生成」。

防幻觉三道闸门（任一道不通过即整份作废并回退）：

| 闸门 | 机制 |
| --- | --- |
| 事实封闭 | 只允许使用用户亲口陈述的内容 |
| 法条封闭 | 只能引用给定编号 `【法条N】`，越界即作废 |
| 结构可校验 | 强制 JSON，五字段非空，超长截断 |

详见 `backend/app/services/agent/llm_report.py` 与 `backend/tests/test_llm_report.py`。

### 生产环境安全自检

`ENVIRONMENT=production` 时，应用启动前会校验并**拒绝启动**于以下配置：

- `SECRET_KEY` 仍为开发默认值，或长度不足 32 字符
- `POSTGRES_PASSWORD` 仍为 `lawpilot_secret`
- `CORS_ORIGINS` 含通配符 `*`

生产环境默认不暴露 `/docs`、`/redoc`、`/openapi.json`；如需保留，显式设置 `EXPOSE_DOCS=true` 并在网关层加访问控制。

---

## 快速开始（本地开发）

### 方式一：Docker Compose（推荐）

```bash
# 1. 准备环境变量
cp .env.example .env
# 按需修改 .env（数据库密码、LLM API Key 等）

# 2. 一键启动完整开发环境（含端口暴露与后端热重载）
make up
```

访问地址：

- 前端：http://localhost:3000
- 后端 API 文档：http://localhost:8000/docs
- Nginx 网关（生产）：http://localhost

### 方式二：本地直接运行（前后端分离）

```bash
# 1. 环境变量
cp .env.example .env

# 2. 基础设施（数据库 + Redis，需要 Docker）
make infra-up

# 3. 后端（需本地 Python 3.12+）
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# 首次运行需建表并灌入种子数据
alembic upgrade head
python -m scripts.ingest_knowledge
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 4. 前端（需本地 Node 20+）
cd frontend
npm install
npm run dev
```

> 前端默认连接 `http://localhost:8000`（见 `.env` 的 `NEXT_PUBLIC_API_BASE_URL`）。
> 若前端运行在其他端口（如 3100），请在 `.env` 的 `CORS_ORIGINS` 中加入对应来源，例如
> `http://localhost:3100`，并重启后端使 CORS 配置生效。

### 创建管理员账号

后端提供脚本创建超级管理员（用于访问 AI 能力中心等需要权限的功能）：

```bash
cd backend
python -m scripts.make_superuser
# 默认账号：admin@lawpilot.dev / admin1234（首次运行会提示创建）
```

---

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `make up` | 启动完整开发环境（含端口与热重载） |
| `make infra-up` | 仅启动数据库与 Redis |
| `make backend-dev` | 仅启动后端开发服务 |
| `make frontend-dev` | 仅启动前端开发服务 |
| `make migrate` | 执行数据库迁移（alembic upgrade head） |
| `make seed` | 迁移数据库并灌入知识库 |
| `make test` | 运行后端测试 |
| `make lint` | 后端代码检查（ruff） |
| `make format` | 后端代码格式化（ruff） |
| `make deploy` | 生产构建并启动 |
| `make logs` | 查看全部服务日志 |

---

## 生产部署

生产环境采用「镜像内打包代码 + Nginx 统一入口」的形态，与开发编排（源码热重载）隔离。
所有对外流量仅经 Nginx（80 / 可选 443），后端、前端、数据库均不暴露到宿主机。

> **编排结构（三文件拆分）**：`docker-compose.yml` 为通用基线，本身**不定义** db/redis/backend/frontend 的宿主机端口（仅 Nginx 暴露 80）；
> 开发期用 `docker-compose.dev.yml` 叠加暴露端口与源码热重载；生产期用 `docker-compose.prod.yml` 叠加 production 环境。
> 之所以不采用「在覆盖里写 `ports: []` 去删除端口」的方式，是因为 Docker Compose 会忽略空序列、无法删除父文件已定义的端口，必须从源头（基线）就不暴露。

### 1. 准备环境变量

```bash
cp .env.example .env
```

生产环境**必须**覆盖以下变量（其余保持默认即可）：

| 变量 | 说明 | 示例 |
| --- | --- | --- |
| `ENVIRONMENT` | 设为 `production`（关闭自动建表，改用迁移） | `production` |
| `SECRET_KEY` | JWT 签名密钥，务必强随机：`openssl rand -hex 32` | `****` |
| `POSTGRES_PASSWORD` | 数据库密码（强随机） | `****` |
| `CORS_ORIGINS` | 允许的浏览器来源（逗号分隔） | `https://lawpilot.example.com` |
| `NEXT_PUBLIC_API_BASE_URL` | 前端调用的 API 基地址（Nginx 对外域名） | `https://lawpilot.example.com` |
| `LLM_API_KEY` / `EMBEDDING_API_KEY` | 大模型与 Embedding 的 API Key | `sk-...` |

> 注意：Nginx 已代理 `/api` → 后端、`/` → 前端。因此前端的 `NEXT_PUBLIC_API_BASE_URL`
> 应填 Nginx 的对外地址（同源），而非 `localhost:8000`。

### 2. 一键部署（推荐）

```bash
chmod +x scripts/init.sh
./scripts/init.sh
```

脚本将依次执行：启动 db/redis/backend → 等待数据库就绪 →
`alembic upgrade head`（建表）→ 灌入种子知识库 → 启动 frontend/nginx。

### 3. 手动部署

```bash
# 构建并以生产形态启动（合并开发编排与 prod 覆盖）
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 迁移数据库 + 灌入知识库
make seed
```

### 4. 数据持久化

以下 Docker 卷在容器重建后保留数据，请勿随意删除：

- `pgdata`：PostgreSQL 数据目录
- `redisdata`：Redis AOF 持久化
- `uploads`：用户上传的证据文件

### 5. HTTPS 部署（可选）

1. 申请证书（如 Let's Encrypt），将 `fullchain.pem` 与 `privkey.pem` 放入项目根 `certs/` 目录。
2. 编辑 `docker-compose.prod.yml`，取消 `nginx` 服务下 `443` 端口与 `certs` 卷挂载的注释。
3. 编辑 `nginx/nginx.conf`，取消 `listen 443 ssl;` 与 `ssl_certificate*` 两行注释，
   并建议将 80 端口重定向至 443：

   ```nginx
   server {
       listen 80;
       server_name lawpilot.example.com;
       return 302 https://$host$request_uri;
   }
   ```

4. 重新部署：`make deploy`。

> 安全提示：生产环境建议进一步限制 `/docs` 与 `/openapi.json`（在 `nginx.conf` 中加
> `allow`/`deny` 或改为仅内网监听）。数据库与 Redis 端口已在 prod 覆盖中关闭对外暴露。

---

## 环境变量说明

详见 `.env.example`，核心变量包括：

- `POSTGRES_*`：数据库账户、密码、库名
- `REDIS_*`：Redis 连接
- `LLM_*`：大模型基础地址、模型名、API Key
- `EMBEDDING_*`：Embedding 模型（BGE-M3）配置
- `RERANK_*`：重排模型（可选）
- `SECURITY_*`：JWT 密钥与过期时间
- `CORS_*`：跨域白名单

> ⚠️ `.env` 已被 `.gitignore` 忽略，**请勿将真实密钥提交到仓库**。生产环境请通过密钥管理服务或 CI Secret 注入。

---

## 赛事材料

面向 OPC（一人公司）系列 AI 创新大赛的准备材料位于 `docs/competition/`：

| 文件 | 内容 |
| --- | --- |
| `OPC-参赛差距评估.md` | 按评审维度的现状评分、差距分析与分级行动清单 |
| `01-One-Pager.md` | 一页纸：问题 / 方案 / 差异 / AI 作用 / 进度 |
| `02-AI使用说明.md` | 产品内 AI 的三个角色与防幻觉机制；开发过程中的人机分工 |
| `03-数据来源说明.md` | 法条与案例数据的来源、规模、处理方式与已知局限 |
