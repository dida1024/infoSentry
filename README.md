# infoSentry

infoSentry 是一个面向目标追踪场景的信息追踪 Agent 系统。它把分散的信息源接入、内容去重与匹配、Agent 决策、站内/邮件推送、点击与反馈收敛串成一条可运行、可回放、可迭代的闭环。

仓库采用 monorepo 组织，统一维护后端、前端、异步任务、部署配置、运行规范，以及供外部 AI Agent 调用的 Skill。

## 它解决什么问题

当你持续关注某个主题、公司、产品、岗位、技术方向时，信息通常分散在 RSS、聚合源和站点列表里。infoSentry 的目标不是“抓更多”，而是把真正值得看的内容筛出来，并以合适的节奏推给你。

核心链路：

`Ingest -> Dedupe -> Embed -> Match -> Agent Decide -> Notify -> Click/Feedback`

## 核心能力

- 多源接入：支持 NewsNow 公共源、RSS 和 SITE 抓取。
- Goal 驱动追踪：围绕用户定义的 Goal、priority terms 和推送策略进行匹配。
- 三层推送决策：支持 `IMMEDIATE`、`BATCH`、`DIGEST` 三种推送桶。
- Agent Runtime：规则优先、LLM 仅处理边界样本，并保留运行记录、工具调用和动作账本。
- 异步流水线：基于 Celery 队列拆分 `q_ingest`、`q_embed`、`q_match`、`q_agent`、`q_email`。
- 外部 Agent 接入：提供零依赖 Python Skill，让 Claude Code 等 Agent 通过 API Key 管理 Goals、Sources、Notifications。

## 仓库结构

- `infoSentry-backend/`：FastAPI + SQLModel + Alembic + Celery，承载 API、领域逻辑和异步任务。
- `infosentry-web/`：Next.js 15 前端，提供登录、Goals、Sources、Inbox、Settings 等界面。
- `infosentry-skill/`：供外部 AI Agent 使用的 Skill 与 CLI。
- `openspec/`：OpenSpec 规格、变更提案与架构约束。
- `docs/`：产品、开发规范、架构决策等文档。
- `runbooks/`：部署、队列、邮件、运行排障手册。
- `docker-compose.yml`：仓库级生产编排入口。
- `Makefile`：本地开发与基础检查命令。

## 系统架构

当前版本采用“模块化单体 + 队列隔离”架构：

- Web：Next.js，负责配置、查看与反馈。
- API：FastAPI，负责认证、CRUD、查询与运行回放。
- Workers：Celery，按队列拆分异步任务。
- Scheduler：Celery Beat，触发 Batch 与 Digest 调度。
- Storage：PostgreSQL + pgvector + Redis。
- Delivery：站内通知与 SMTP 邮件推送。

这一设计优先服务单机可交付、可运维、可迭代的 MVP，同时为后续 Agent 编排层演进保留边界。

## 快速开始

### 方式一：本地完整开发

1. 准备依赖：

```bash
cd infoSentry-backend
uv sync

cd ../infosentry-web
npm install
```

2. 启动基础设施并执行迁移：

```bash
cd ..
make dev-infra
```

3. 启动 API、Web、Worker、Beat：

```bash
make dev
```

默认地址：

- Web: `http://localhost:3000`
- API: `http://localhost:8000`
- API Docs: `http://localhost:8000/api/v1/docs`

开发进程由 [`Procfile.dev`](/Users/ray/Documents/code/infoSentry/Procfile.dev) 管理，启动项包含：

- `api`
- `web`
- `worker`
- `beat`

### 方式二：单机部署 / 生产编排

1. 在仓库根目录复制配置：

```bash
cp .env.example .env
```

2. 补齐至少这些关键变量：

- `POSTGRES_PASSWORD`
- `SECRET_KEY`
- `FRONTEND_HOST`
- `BACKEND_HOST`
- `OPENAI_API_KEY`（如启用 LLM/embedding）
- `SMTP_*` 与 `EMAILS_FROM_*`（如启用邮件）

3. 启动服务：

```bash
docker-compose up -d
```

4. 首次部署执行迁移：

```bash
docker-compose exec api uv run alembic upgrade head
```

生产编排默认同时包含 API、Web、PostgreSQL、Redis、各类 Worker。

## 面向开发者

### 工作流

本项目采用 OpenSpec 驱动变更：

- `/opsx:propose <description>`：创建 proposal、design、tasks 与 delta specs
- `/opsx:explore <topic>`：先探索问题与方案
- `/opsx:apply <name>`：按已有变更实现
- `/opsx:archive <name>`：完成后归档

涉及实现前，请先阅读 [`AGENTS.md`](/Users/ray/Documents/code/infoSentry/AGENTS.md)。其中定义了：

- DDD 分层与依赖方向
- 异步通知链路修复的强制 guardrails
- 测试、迁移、日志、配置、安全约束
- 前后端与 Agent Runtime 的硬规则

### 常用命令

```bash
make format
make lint
make test
```

项目约定的关键检查：

- Backend: `cd infoSentry-backend && uv run pytest && uv run mypy src`
- Frontend: `cd infosentry-web && npm run lint && npm run build`

## AI Agent Skill 接入

`infosentry-skill/` 提供一个零依赖 Python Skill，方便外部 Agent 直接接入 infoSentry API。

快速体验：

```bash
cd infosentry-skill
python3 scripts/setup.py
python3 scripts/infosentry.py goals list
```

适用场景：

- 在 Claude Code 中把 infoSentry 当作可调用工具
- 让外部 Agent 读取/创建 Goals
- 查询 Sources、Notifications，或执行原始 API 调用

详细说明见 [`infosentry-skill/README.md`](/Users/ray/Documents/code/infoSentry/infosentry-skill/README.md)。

## 文档入口

- 文档索引：[`docs/README.md`](/Users/ray/Documents/code/infoSentry/docs/README.md)
- 后端说明：[`infoSentry-backend/README.md`](/Users/ray/Documents/code/infoSentry/infoSentry-backend/README.md)
- 前端说明：[`infosentry-web/README.md`](/Users/ray/Documents/code/infoSentry/infosentry-web/README.md)
- 系统架构规格：[`openspec/specs/system-architecture/spec.md`](/Users/ray/Documents/code/infoSentry/openspec/specs/system-architecture/spec.md)
- Agent Runtime 规格：[`openspec/specs/agent-runtime/spec.md`](/Users/ray/Documents/code/infoSentry/openspec/specs/agent-runtime/spec.md)
- 部署 Runbook：[`runbooks/DEPLOYMENT.md`](/Users/ray/Documents/code/infoSentry/runbooks/DEPLOYMENT.md)

## 当前状态

项目已具备以下基础能力：

- Magic Link 登录
- Goals 创建、编辑、详情查看
- Sources 管理
- Inbox / Notifications 展示与反馈
- API Key 与外部 Skill 接入
- Agent Runtime、Prompt Regression、异步任务基础设施

README 只做全局入口。更细的模块细节、环境变量和运行方式，请进入对应子目录文档查看。
