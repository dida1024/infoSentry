# infoSentry 部署指南

本文档涵盖部署、发布、回滚和运维操作的完整流程。

---

## 目录

1. [环境要求](#1-环境要求)
2. [首次部署](#2-首次部署)
3. [日常发布流程](#3-日常发布流程)
4. [回滚流程](#4-回滚流程)
5. [降级开关](#5-降级开关)
6. [监控与告警](#6-监控与告警)
7. [故障处理](#7-故障处理)

---

## 1. 环境要求

### 1.1 硬件要求

| 规格 | 最低要求 | 推荐配置 |
|------|----------|----------|
| CPU | 2 核 | 4 核 |
| 内存 | 4 GB | 8 GB |
| 存储 | 20 GB SSD | 50 GB SSD |
| 网络 | 公网 IP | 公网 IP + 域名 |

### 1.2 软件要求

- Docker 24.0+
- Docker Compose 2.20+
- Git

### 1.3 外部服务

| 服务 | 必需 | 说明 |
|------|------|------|
| OpenAI API | 推荐 | embedding + 边界判别 |
| SMTP 服务 | 推荐 | 邮件推送 |
| 域名 + SSL | 推荐 | HTTPS 访问 |

---

## 2. 首次部署

### 2.1 克隆代码

```bash
git clone https://github.com/your-org/infoSentry.git
cd infoSentry
```

### 2.2 配置环境变量

```bash
# 复制配置模板（仓库根目录）
cp .env.example .env

# 编辑配置（必填项用 [必填] 标记）
vim .env

# 必须配置的关键变量：
# - SECRET_KEY: 应用密钥
# - POSTGRES_PASSWORD: 数据库密码
# - FRONTEND_HOST / BACKEND_HOST: 访问 URL
```

### 2.3 生成密钥

```bash
# 生成 SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# 生成数据库密码
openssl rand -base64 24
```

### 2.4 配置 Nginx（可选）

```bash
# 如果启用 HTTPS，配置 SSL 证书
mkdir -p nginx/ssl
cp /path/to/cert.pem nginx/ssl/
cp /path/to/key.pem nginx/ssl/

# 编辑 nginx/nginx.conf 启用 SSL 配置
```

### 2.5 启动服务

```bash
# 拉取镜像并启动
docker-compose -f docker-compose.prod.yml up -d

# 查看服务状态
docker-compose -f docker-compose.prod.yml ps
```

### 2.6 初始化数据库

```bash
# 等待 PostgreSQL 就绪
docker-compose -f docker-compose.prod.yml exec api uv run alembic upgrade head
```

### 2.7 验证部署

```bash
# API 健康检查
curl http://localhost:8000/health

# 检查所有服务
docker-compose -f docker-compose.prod.yml ps

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f
```

---

## 3. 日常发布流程

### 3.1 发布前准备

```bash
# 1. 备份数据
./scripts/backup.sh

# 2. 检查当前状态
docker-compose -f docker-compose.prod.yml ps
./scripts/chaos.sh status

# 3. 拉取最新代码
git fetch origin
git log origin/main --oneline -5  # 查看变更
```

### 3.2 执行发布

```bash
# 1. 切换到新版本
git checkout main
git pull origin main

# 2. 重建并更新服务
docker-compose -f docker-compose.prod.yml up -d --build

# 3. 执行数据库迁移（如果有）
docker-compose -f docker-compose.prod.yml exec api uv run alembic upgrade head
```

### 3.3 发布后验证

```bash
# 1. 检查服务健康
curl http://localhost:8000/health

# 2. 检查 Worker 状态
docker-compose -f docker-compose.prod.yml logs --tail=50 worker_agent

# 3. 检查队列
docker exec infosentry-redis redis-cli LLEN q_agent

# 4. 测试关键功能
curl http://localhost:8000/api/v1/admin/health -H "Authorization: Bearer $TOKEN"
```

### 3.4 灰度发布（可选）

对于重大变更，建议先关闭部分功能再逐步开放：

```bash
# 1. 发布前关闭 Immediate 推送
curl -X POST http://localhost:8000/api/v1/admin/config \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"IMMEDIATE_ENABLED": false}'

# 2. 执行发布
docker-compose -f docker-compose.prod.yml up -d --build

# 3. 验证无异常后开放
curl -X POST http://localhost:8000/api/v1/admin/config \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"IMMEDIATE_ENABLED": true}'
```

---

## 4. 回滚流程

### 4.1 快速回滚（代码回滚）

```bash
# 1. 确定回滚目标版本
git log --oneline -10

# 2. 回滚代码
git checkout <commit-hash>

# 3. 重建服务
docker-compose -f docker-compose.prod.yml up -d --build

# 4. 验证
curl http://localhost:8000/health
```

### 4.2 数据库回滚

如果迁移导致问题：

```bash
# 1. 查看迁移历史
docker-compose -f docker-compose.prod.yml exec api uv run alembic history

# 2. 回滚到指定版本
docker-compose -f docker-compose.prod.yml exec api uv run alembic downgrade <revision>

# 3. 如果需要完全恢复，使用备份
./scripts/backup.sh --restore pg /path/to/backup.sql.gz
```

### 4.3 紧急降级

当系统异常时，快速降级以保证基础功能：

```bash
# 关闭所有高级功能，仅保留站内通知
curl -X POST http://localhost:8000/api/v1/admin/config \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "LLM_ENABLED": false,
    "IMMEDIATE_ENABLED": false,
    "EMAIL_ENABLED": false
  }'
```

---

## 5. 降级开关

### 5.1 可用开关

| 开关 | 说明 | 降级效果 |
|------|------|----------|
| `LLM_ENABLED` | LLM 边界判别 | 边界区间全部降级 Batch |
| `EMBEDDING_ENABLED` | 向量化 | 跳过 embedding 计算 |
| `IMMEDIATE_ENABLED` | 即时推送 | 只有 Batch/Digest |
| `EMAIL_ENABLED` | 邮件发送 | 只有站内通知 |

### 5.2 通过 API 热更新

```bash
# 查询当前配置
curl http://localhost:8000/api/v1/admin/config \
  -H "Authorization: Bearer $TOKEN"

# 更新配置（无需重启）
curl -X POST http://localhost:8000/api/v1/admin/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"LLM_ENABLED": false}'
```

### 5.3 通过环境变量

如果 API 不可用，可以直接修改环境变量：

```bash
# 编辑 .env 文件
vim infoSentry-backend/.env

# 重启相关服务
docker-compose -f docker-compose.prod.yml restart api worker_agent
```

---

## 6. 监控与告警

### 6.1 关键指标

| 指标 | 阈值 | 告警级别 |
|------|------|----------|
| 队列积压 (q_embed/q_agent/q_email) | > 100 | 警告 |
| SMTP 连续失败 | > 3 次 | 警告 |
| LLM 429/5xx | > 10 次/小时 | 警告 |
| budget_daily 熔断 | 触发 | 通知 |
| sources error_streak | > 5 | 警告 |
| Worker 心跳 | 超时 60s | 严重 |

### 6.2 监控命令

```bash
# 检查队列长度
docker exec infosentry-redis redis-cli LLEN q_embed
docker exec infosentry-redis redis-cli LLEN q_agent
docker exec infosentry-redis redis-cli LLEN q_email

# 检查 Worker 状态
docker exec infosentry-worker-agent celery -A src.core.infrastructure.celery.app inspect ping

# 检查预算状态
curl http://localhost:8000/api/v1/admin/budget -H "Authorization: Bearer $TOKEN"

# 完整健康检查
curl http://localhost:8000/api/v1/admin/health -H "Authorization: Bearer $TOKEN"
```

### 6.3 日志查看

```bash
# 实时查看所有日志
docker-compose -f docker-compose.prod.yml logs -f

# 查看特定服务日志
docker-compose -f docker-compose.prod.yml logs -f api
docker-compose -f docker-compose.prod.yml logs -f worker_agent

# 查看最近错误
docker-compose -f docker-compose.prod.yml logs --tail=100 | grep -i error
```

---

## 7. 故障处理

### 7.1 常见故障处理

#### API 无响应

```bash
# 检查服务状态
docker-compose -f docker-compose.prod.yml ps

# 重启 API
docker-compose -f docker-compose.prod.yml restart api

# 检查日志
docker-compose -f docker-compose.prod.yml logs --tail=100 api
```

#### 队列堆积

```bash
# 检查 Worker 是否运行
docker-compose -f docker-compose.prod.yml ps | grep worker

# 重启 Worker
docker-compose -f docker-compose.prod.yml restart worker_ingest worker_embed_match worker_agent worker_email

# 检查队列处理情况
watch -n 5 'docker exec infosentry-redis redis-cli LLEN q_agent'
```

#### 数据库连接问题

```bash
# 检查 PostgreSQL
docker-compose -f docker-compose.prod.yml logs postgres

# 检查连接数
docker exec infosentry-postgres psql -U infosentry -d infosentry -c \
  "SELECT count(*) FROM pg_stat_activity WHERE datname = 'infosentry';"

# 重启数据库
docker-compose -f docker-compose.prod.yml restart postgres
```

### 7.2 故障演练

定期执行故障演练以验证系统韧性：

```bash
# 使用故障演练脚本
./scripts/chaos.sh openai   # 模拟 OpenAI 故障
./scripts/chaos.sh smtp     # 模拟 SMTP 故障
./scripts/chaos.sh redis    # 模拟 Redis 重启
./scripts/chaos.sh recover  # 恢复配置
```

### 7.3 恢复检查清单

故障恢复后，确认以下各项：

- [ ] API 健康检查通过 (`/health`)
- [ ] 所有 Worker 运行中
- [ ] 队列无异常积压
- [ ] 数据库连接正常
- [ ] Redis 连接正常
- [ ] 最近的 agent_runs 状态正常
- [ ] 预算未熔断

---

## 附录

### A. 目录结构

```
infoSentry/
├── .env.example               # 生产环境变量模板（根目录）
├── docker-compose.prod.yml    # 生产环境编排
├── nginx/
│   └── nginx.conf             # Nginx 配置
├── scripts/
│   ├── backup.sh              # 备份脚本
│   └── chaos.sh               # 故障演练脚本
├── infoSentry-backend/
│   ├── .env.example            # 后端本地开发模板
│   ├── Dockerfile             # 后端镜像
│   └── ...
└── infosentry-web/
    ├── Dockerfile             # 前端镜像
    └── ...
```

### B. 常用命令速查

```bash
# 启动/停止
docker-compose -f docker-compose.prod.yml up -d
docker-compose -f docker-compose.prod.yml down

# 更新
docker-compose -f docker-compose.prod.yml up -d --build

# 日志
docker-compose -f docker-compose.prod.yml logs -f [service]

# 重启
docker-compose -f docker-compose.prod.yml restart [service]

# 进入容器
docker-compose -f docker-compose.prod.yml exec api bash

# 数据库
docker exec -it infosentry-postgres psql -U infosentry -d infosentry

# Redis
docker exec -it infosentry-redis redis-cli
```

### C. 环境变量清单

详见 `.env.example`
