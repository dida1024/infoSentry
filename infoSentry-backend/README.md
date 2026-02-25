# infoSentry Backend

信息追踪 Agent 系统后端服务 - 抓取、匹配、推送一体化解决方案。

## 技术栈

- **框架**: FastAPI + SQLModel
- **数据库**: PostgreSQL + pgvector
- **任务队列**: Celery + Redis
- **AI**: OpenAI API (embedding + 边界判别)
- **认证**: JWT + Magic Link

## 项目结构

```
src/
├── core/                    # 核心模块
│   ├── config.py           # 配置管理
│   ├── domain/             # 领域基类
│   ├── infrastructure/     # 基础设施
│   └── interfaces/         # HTTP 接口
├── modules/                 # 业务模块
│   ├── users/              # 用户管理
│   ├── sources/            # 信息源管理
│   ├── goals/              # 追踪目标
│   ├── items/              # 信息条目
│   ├── push/               # 推送决策
│   └── agent/              # Agent 运行
├── alembic/                # 数据库迁移
└── tests/                  # 测试
```

---

## 生产部署（推荐）

使用 Docker Compose 一键部署，适用于 2c4g 单机环境。

### 1. 配置环境变量

```bash
# 在仓库根目录复制配置模板
cd ..
cp .env.example .env

# 编辑配置（必填项请参考 .env.example 中的注释）
vim .env
```

### 2. 启动服务

```bash
# 返回项目根目录
cd ..

# 启动所有服务
docker-compose -f docker-compose.prod.yml up -d

# 初始化数据库
docker-compose -f docker-compose.prod.yml exec api uv run alembic upgrade head

# 验证部署
curl http://localhost:8000/health
```

### 3. 查看日志

```bash
docker-compose -f docker-compose.prod.yml logs -f
```

详细部署文档请参考 [docs/ops/DEPLOYMENT.md](../docs/ops/DEPLOYMENT.md)

---

## 本地开发

### 环境准备

1. 安装 Python 3.12+
2. 安装 PostgreSQL 15+ (with pgvector extension)
3. 安装 Redis

### 安装依赖

使用 uv (推荐):

```bash
uv sync
```

或使用 pip:

```bash
pip install -e .
```

### 配置环境变量

复制环境变量示例文件并修改:

```bash
cp .env.example .env
# 编辑 .env 文件
```

### 启动依赖服务（Docker）

```bash
docker-compose up -d  # 启动 PostgreSQL 和 Redis
```

### 数据库迁移

```bash
# 创建 pgvector 扩展
psql -d infosentry -c "CREATE EXTENSION IF NOT EXISTS vector"

# 运行迁移
uv run alembic upgrade head
```

### 启动服务

开发模式:

```bash
uv run python main.py
```

或使用 uvicorn:

```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 启动 Worker

```bash
# 启动所有 Worker（开发环境）
uv run celery -A src.core.infrastructure.celery.app worker -Q q_ingest,q_embed,q_match,q_agent,q_email -c 2 -l INFO

# 启动 Beat（定时任务调度）
uv run celery -A src.core.infrastructure.celery.app beat -l INFO
```

### API 文档

启动服务后访问:

- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc

## 核心概念

### 信息源 (Sources)

支持三种类型:
- **NEWSNOW**: NewsNow 聚合源
- **RSS**: RSS Feed
- **SITE**: 网页列表抓取

NEWSNOW 默认公共源在服务启动时自动同步（可通过配置关闭）：
- 启动时拉取上游目录：`NEWSNOW_CATALOG_URL`
- 抓取接口：`{NEWSNOW_API_BASE_URL}{NEWSNOW_API_PATH}?id=<source_id>`
- 目录拉取失败时回退本地快照：`resources/sources/newsnow_sources_snapshot.json`
- 同步仅维护公共源，不会自动为用户创建订阅

### 追踪目标 (Goals)

用户定义的追踪目标，包含:
- 描述和优先词条
- 优先模式 (STRICT/SOFT)
- 推送配置 (窗口时间、摘要时间)

### 推送三桶

- **IMMEDIATE**: 事件触发，超高价值
- **BATCH**: 窗口合并推送
- **DIGEST**: 每日汇总兜底

### Agent Runtime

- 可控的决策系统
- 结构化输入输出
- 完整的运行记录和可回放能力

## 开发指南

### 代码风格

使用 ruff 进行代码检查和格式化:

```bash
uv run ruff check .
uv run ruff format .
```

### 运行测试

```bash
uv run pytest
```

### 添加新迁移

```bash
uv run alembic revision --autogenerate -m "description"
```

## API 端点

### 认证

- `POST /api/v1/auth/request_link` - 请求 Magic Link
- `GET /api/v1/auth/consume` - 消费 Magic Link

### 用户

- `GET /api/v1/users/me` - 获取当前用户
- `PUT /api/v1/users/me` - 更新用户资料

### 信息源

- `GET /api/v1/sources` - 获取信息源列表
- `POST /api/v1/sources` - 创建信息源
- `PUT /api/v1/sources/{id}` - 更新信息源
- `POST /api/v1/sources/{id}/enable` - 启用信息源
- `POST /api/v1/sources/{id}/disable` - 禁用信息源

### 追踪目标

- `GET /api/v1/goals` - 获取 Goal 列表
- `POST /api/v1/goals` - 创建 Goal
- `GET /api/v1/goals/{id}` - 获取 Goal 详情
- `PUT /api/v1/goals/{id}` - 更新 Goal
- `POST /api/v1/goals/{id}/pause` - 暂停 Goal
- `POST /api/v1/goals/{id}/resume` - 恢复 Goal

### 通知

- `GET /api/v1/notifications` - 获取通知列表
- `POST /api/v1/items/{id}/feedback` - 提交反馈
- `GET /api/v1/r/{item_id}` - 点击跟踪重定向

### Agent

- `GET /api/v1/agent/runs` - 获取 Agent 运行记录
- `GET /api/v1/agent/runs/{id}` - 获取运行详情
- `GET /api/v1/admin/budget` - 获取预算状态

## License

MIT
