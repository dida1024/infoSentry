# infoSentry Backend

`infoSentry-backend/` 是 infoSentry 的后端与异步任务核心，负责认证、目标与信息源管理、内容抓取、向量化、匹配、Agent 决策、通知与运行记录。

技术栈：

- FastAPI
- SQLModel + Alembic
- PostgreSQL + pgvector
- Celery + Redis
- OpenAI API 协议模型（embedding + 边界判别）

## 后端负责什么

后端承载整条业务闭环：

`Source ingest -> item dedupe -> embedding -> goal match -> agent decide -> push -> click/feedback`

它不仅暴露 REST API，也负责异步队列、调度任务、Agent Runtime 和关键业务持久化。

## 目录结构

```text
src/
├── core/                    # 核心配置、基础设施、跨模块能力
├── modules/
│   ├── users/              # 用户、登录、会话
│   ├── sources/            # 信息源接入与抓取
│   ├── goals/              # Goal 管理与辅助生成
│   ├── items/              # Item、embedding、match
│   ├── push/               # 推送决策与邮件发送
│   └── agent/              # Agent Runtime、运行记录与工具编排
├── alembic/                # 数据库迁移
└── tests/                  # unit / integration / e2e
```

## 快速开始

### 本地开发

1. 安装依赖：

```bash
uv sync
```

2. 复制环境变量：

```bash
cp .env.example .env
```

3. 启动 PostgreSQL 和 Redis：

```bash
docker-compose up -d
```

4. 初始化数据库：

```bash
uv run alembic upgrade head
```

5. 启动 API：

```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

6. 启动 Worker 和 Beat：

```bash
uv run celery -A src.core.infrastructure.celery.app worker -Q q_ingest,q_embed,q_match,q_agent,q_email -c 2 -l INFO
uv run celery -A src.core.infrastructure.celery.app beat -l INFO
```

接口地址：

- Swagger UI: `http://localhost:8000/api/v1/docs`
- ReDoc: `http://localhost:8000/api/v1/redoc`
- Health: `http://localhost:8000/health`

### 仓库级一键开发

如果你在仓库根目录协同开发前后端，优先使用：

```bash
make dev-infra
make dev
```

这会按 [`../Procfile.dev`](/Users/ray/Documents/code/infoSentry/Procfile.dev) 同时拉起 API、Web、Worker、Beat。

### 单机部署

生产环境推荐使用仓库根目录编排：

```bash
cd ..
cp .env.example .env
docker-compose up -d
docker-compose exec api uv run alembic upgrade head
```

更完整的部署与运行验证见 [`../runbooks/DEPLOYMENT.md`](/Users/ray/Documents/code/infoSentry/runbooks/DEPLOYMENT.md)。

## 核心概念

### Sources

支持三类信息源：

- `NEWSNOW`
- `RSS`
- `SITE`

默认公共源可以在服务启动时自动同步。若上游目录拉取失败，会回退本地快照 `resources/sources/newsnow_sources_snapshot.json`。

### Goals

Goal 是追踪入口，通常包含：

- `name`
- `description`
- `priority_terms`
- `priority_mode`
- `batch_windows`
- `digest_send_time`

### 三层推送

- `IMMEDIATE`：高优先级事件触发，支持短窗口合并
- `BATCH`：窗口聚合推送
- `DIGEST`：每日汇总兜底

### Agent Runtime

Agent Runtime 负责边界区间的推送判定，并保留：

- `agent_runs`
- `tool_calls`
- `action_ledger`

规则优先于 LLM，LLM 只处理不确定样本，失败时保守降级。

## 开发约束

本项目不是“普通 FastAPI 项目”，实现时要遵守仓库级规则：

- 遵循 DDD 分层：`interfaces -> application -> domain`
- domain 不依赖 infrastructure
- 路由层只做校验和依赖注入，不承载业务逻辑
- 使用完整类型标注并满足 mypy strict
- 异步通知链路修改必须补齐回归测试和运行证据

实现前先看 [`../AGENTS.md`](/Users/ray/Documents/code/infoSentry/AGENTS.md)。

## 常用命令

```bash
uv run ruff format .
uv run ruff check .
uv run pytest
uv run mypy src
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"
```

## API 范围

当前后端主要暴露这些能力：

- Auth / Magic Link
- Users / Sessions
- Goals / Goal Draft / Goal Email
- Sources / Source Subscription
- Notifications / Feedback / Redirect Tracking
- Agent Runs / Monitoring / Budget
- API Keys

更详细的行为规格见：

- [`../openspec/specs/api-contracts/spec.md`](/Users/ray/Documents/code/infoSentry/openspec/specs/api-contracts/spec.md)
- [`../openspec/specs/system-architecture/spec.md`](/Users/ray/Documents/code/infoSentry/openspec/specs/system-architecture/spec.md)
- [`../openspec/specs/agent-runtime/spec.md`](/Users/ray/Documents/code/infoSentry/openspec/specs/agent-runtime/spec.md)

## 相关文档

- 仓库入口：[`../README.md`](/Users/ray/Documents/code/infoSentry/README.md)
- 文档索引：[`../docs/README.md`](/Users/ray/Documents/code/infoSentry/docs/README.md)
- 队列与 Worker：[`../runbooks/celery-queues-and-workers.md`](/Users/ray/Documents/code/infoSentry/runbooks/celery-queues-and-workers.md)
- 邮件投递：[`../runbooks/email-delivery.md`](/Users/ray/Documents/code/infoSentry/runbooks/email-delivery.md)
