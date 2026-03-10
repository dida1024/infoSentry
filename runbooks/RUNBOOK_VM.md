# infoSentry Runbook（单机 VM / 2c4g）

目标：可部署、可监控、可回滚、可恢复

---

## 1. 部署拓扑（docker-compose）

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    # ...

  redis:
    image: redis:7-alpine
    # ...

  api:
    build: ./infoSentry-backend
    command: uvicorn main:app --host 0.0.0.0 --port 8000
    # ...

  web:
    build: ./infoSentry-web
    # Next.js
    # ...

  worker_ingest:
    build: ./infoSentry-backend
    command: celery -A app.celery worker -Q q_ingest -c 2
    # ...

  worker_embed_match:
    build: ./infoSentry-backend
    command: celery -A app.celery worker -Q q_embed,q_match -c 1
    # ...

  worker_agent:
    build: ./infoSentry-backend
    command: celery -A app.celery worker -Q q_agent -c 1
    # ...

  worker_email:
    build: ./infoSentry-backend
    command: celery -A app.celery worker -Q q_email -c 1
    # ...

  beat:
    build: ./infoSentry-backend
    command: celery -A app.celery beat
    # ...

  nginx:
    image: nginx:alpine
    # 可选，反向代理
    # ...
```

---

## 2. 关键环境变量（示例）

```bash
# Database
DATABASE_URL=postgresql+psycopg://user:pass@postgres:5432/infosentry

# Redis
REDIS_URL=redis://redis:6379/0

# Timezone
TZ=Asia/Shanghai

# OpenAI API
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-...
OPENAI_EMBED_MODEL=text-embedding-3-small
OPENAI_JUDGE_MODEL_SMALL=gpt-4o-mini
OPENAI_JUDGE_MODEL_LARGE=gpt-4o

# SMTP
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASS=...
SMTP_FROM=infoSentry <noreply@example.com>

# Feature Flags
LLM_ENABLED=true
EMBEDDING_ENABLED=true
IMMEDIATE_ENABLED=true
EMAIL_ENABLED=true

# Budget & Throttle
DAILY_USD_BUDGET=0.33
JUDGE_PER_DAY=200
EMBED_PER_MIN=300
ITEMS_PER_SOURCE_PER_FETCH=20
NEWSNOW_FETCH_INTERVAL_SEC=1800
```

---

## 3. 推荐并发（2c4g）

| 服务 | 并发数 | 说明 |
|------|--------|------|
| worker_ingest | 2 | 抓取任务，I/O 密集 |
| worker_embed_match | 1 | 向量计算，API 调用 |
| worker_agent | 1 | LLM 调用，需控制 |
| worker_email | 1 | SMTP 发送 |
| api (uvicorn) | 1-2 | 根据 CPU 调整 |

---

## 4. 监控与告警（最低要求）

### 4.1 必须告警

| 指标 | 阈值 | 处理 |
|------|------|------|
| 队列积压 | q_embed/q_agent/q_email > 100 | 检查 worker 状态 |
| SMTP 连续失败 | > 3 次 | 检查 SMTP 配置 |
| LLM 429/5xx | > 10 次/小时 | 触发降级 |
| budget_daily 熔断 | 触发 | 确认降级策略生效 |
| sources error_streak | > 5 | 检查源可用性 |

### 4.2 监控命令

```bash
# 检查队列长度
celery -A app.celery inspect active_queues

# 检查 worker 状态
celery -A app.celery inspect ping

# 检查 Redis 队列
redis-cli LLEN q_embed
redis-cli LLEN q_agent
redis-cli LLEN q_email
```

---

## 5. 回滚开关（最重要）

### 5.1 关闭 LLM
```bash
# 边界全降级 BATCH
LLM_ENABLED=false
```

### 5.2 关闭 Immediate 推送
```bash
# 仅 Batch/Digest
IMMEDIATE_ENABLED=false
```

### 5.3 关闭 Email
```bash
# 只站内
EMAIL_ENABLED=false
```

### 5.4 热更新（无需重启）
```bash
# 通过 API 更新配置
curl -X POST http://localhost:8000/api/admin/config \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"LLM_ENABLED": false}'
```

---

## 6. 备份与恢复

### 6.1 PostgreSQL 备份
```bash
# 每日备份
pg_dump -h localhost -U user infosentry > backup_$(date +%Y%m%d).sql

# 压缩备份
pg_dump -h localhost -U user infosentry | gzip > backup_$(date +%Y%m%d).sql.gz

# 恢复
psql -h localhost -U user infosentry < backup_20251228.sql
```

### 6.2 Redis
- 不做强依赖（可丢，最多影响 buffer/队列）
- 生产建议持久化 AOF：
```
# redis.conf
appendonly yes
appendfsync everysec
```

---

## 7. 故障演练（建议每周一次）

### 7.1 断网/禁用 OpenAI
```bash
# 模拟
iptables -A OUTPUT -d api.openai.com -j DROP

# 验证
- 系统仍能 Batch/Digest
- agent_runs.status = FALLBACK
- 无 Immediate 推送

# 恢复
iptables -D OUTPUT -d api.openai.com -j DROP
```

### 7.2 SMTP 密码错误
```bash
# 模拟
SMTP_PASS=wrong_password

# 验证
- 站内仍可看 push_decisions
- email worker 重试告警
- push_decisions.status = FAILED

# 恢复
SMTP_PASS=correct_password
```

### 7.3 Redis 重启
```bash
# 模拟
docker restart redis

# 验证
- worker 能恢复消费
- 无任务丢失（最多重复执行）
```

---

## 8. 常用运维命令

### 8.1 日志查看
```bash
# API 日志
docker logs -f api

# Worker 日志
docker logs -f worker_agent

# 全部日志
docker-compose logs -f
```

### 8.2 服务重启
```bash
# 重启单个服务
docker-compose restart worker_agent

# 重启全部
docker-compose restart
```

### 8.3 数据库操作
```bash
# 进入 psql
docker exec -it postgres psql -U user infosentry

# 查看活跃连接
SELECT * FROM pg_stat_activity WHERE datname = 'infosentry';

# 查看表大小
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
```

### 8.4 清理操作
```bash
# 清理 30 天前的 agent_runs（保留 ledger）
DELETE FROM agent_tool_calls WHERE created_at < NOW() - INTERVAL '30 days';

# 清理旧的 items（可选）
DELETE FROM items WHERE ingested_at < NOW() - INTERVAL '90 days';
```

---

## 9. 健康检查

### 9.1 API 健康检查
```bash
curl http://localhost:8000/health
# {"status": "ok", "db": "ok", "redis": "ok"}
```

### 9.2 Worker 健康检查
```bash
celery -A app.celery inspect ping
# -> celery@worker_ingest: OK
# -> celery@worker_agent: OK
```

### 9.3 完整系统检查脚本
```bash
#!/bin/bash
echo "=== infoSentry Health Check ==="

# API
curl -s http://localhost:8000/health | jq .

# DB
docker exec postgres pg_isready

# Redis
docker exec redis redis-cli ping

# Workers
docker exec worker_ingest celery -A app.celery inspect ping

echo "=== Done ==="
```

