# 架构与数据底座决策记录

> 本文档记录第一阶段"架构与数据底座"的设计决策，供日后复盘和迭代参考。

---

## 1. 数据库 Schema 设计决策

### 1.1 表结构设计原则

**决策：采用 DDD（领域驱动设计）风格的模块化表结构**

理由：
- 项目已采用 DDD 架构风格（domain/infrastructure/interfaces 分层）
- 表按业务模块划分便于后续维护和扩展
- 符合 `docs/specs/TECH_SPEC_v0.md` 的模块化单体架构要求

**表清单（共 15 张核心表）：**

| 模块 | 表名 | 职责 |
|------|------|------|
| Users | users, auth_magic_links | 用户身份认证 |
| Sources | sources | 信息源配置 |
| Goals | goals, goal_push_configs, goal_priority_terms | 追踪目标配置 |
| Items | items, goal_item_matches | 抓取内容与匹配结果 |
| Push | push_decisions, click_events, item_feedback, blocked_sources | 推送决策与反馈 |
| Agent | agent_runs, agent_tool_calls, agent_action_ledger, budget_daily | Agent 运行记录与预算 |
| Ingest | ingest_logs（新增） | 抓取日志审计 |

### 1.2 主键策略

**决策：使用 String 类型存储 UUID**

理由：
- 分布式友好，无需中心化 ID 生成器
- 字符串类型兼容性更好
- 项目已有代码采用此模式

### 1.3 时间字段

**决策：所有时间字段使用 `DateTime(timezone=True)`，存储 UTC**

理由：
- `docs/product/PRD_v0.md` 明确要求"DB 存 UTC"
- 显示时转换为用户时区（默认 Asia/Shanghai）
- 避免夏令时等时区问题

### 1.4 软删除

**决策：所有表包含 `is_deleted` 字段**

理由：
- 现有代码风格统一使用软删除
- 便于数据恢复和审计
- Agent 记录尤其需要保留（可回放要求）

### 1.5 幂等键设计

**决策：关键操作表使用 dedupe_key 唯一约束**

| 表 | 幂等键 | 说明 |
|----|--------|------|
| push_decisions | dedupe_key (goal+item+decision) | 防止重复推送决策 |
| items | url_hash | 防止重复抓取 |
| goal_item_matches | (goal_id, item_id) | 防止重复匹配记录 |
| budget_daily | date | 每日预算唯一记录 |

---

## 2. Celery 队列设计决策

### 2.1 队列划分

**决策：按功能拆分 5 个独立队列**

```
q_ingest  - 抓取任务（NEWSNOW/RSS/SITE）
q_embed   - 向量化任务
q_match   - 匹配计算任务
q_agent   - Agent 决策任务
q_email   - 邮件发送任务
```

理由：
- `docs/specs/TECH_SPEC_v0.md` 第 7.1 节明确要求队列拆分
- 隔离不同优先级任务，避免低优先级阻塞高优先级
- 便于独立扩缩容和故障隔离
- 监控更清晰（可分别监控各队列积压）

### 2.2 并发配置

**决策：遵循 2c4g 单机推荐并发**

| Worker | 队列 | 并发数 | 理由 |
|--------|------|--------|------|
| worker_ingest | q_ingest | 2 | I/O 密集型，可适当并发 |
| worker_embed_match | q_embed, q_match | 1 | API 调用，需控制速率 |
| worker_agent | q_agent | 1 | LLM 调用，需控制成本 |
| worker_email | q_email | 1 | SMTP 发送，顺序执行 |

### 2.3 任务序列化

**决策：使用 JSON 序列化**

理由：
- 可读性好，便于调试
- 跨语言兼容
- 避免 pickle 安全风险

### 2.4 重试策略

**决策：任务级别配置重试**

```python
# 默认重试配置
max_retries = 3
default_retry_delay = 60  # 秒
retry_backoff = True
retry_backoff_max = 600  # 最大 10 分钟
```

理由：
- 网络波动导致的临时失败需要重试
- 指数退避避免雪崩
- 最大重试限制防止无限循环

---

## 3. Redis 使用决策

### 3.1 用途划分

**决策：Redis 承担以下职责**

| 用途 | Key 模式 | 说明 |
|------|---------|------|
| Celery Broker | celery/* | 任务队列消息 |
| Celery Result | celery-task-meta-* | 任务结果存储 |
| Immediate Buffer | buffer:immediate:{goal_id}:{time_bucket} | 5 分钟合并窗口 |
| Rate Limit | ratelimit:* | 速率限制计数器 |
| Feature Flags | config:* | 动态配置缓存 |

### 3.2 持久化策略

**决策：生产环境启用 AOF**

理由：
- Celery 队列数据可丢失（任务可重投）
- Immediate Buffer 丢失最多损失 5 分钟窗口内的合并效果
- 但 AOF 可减少重启后的数据恢复成本

### 3.3 Redis 配置

**决策：使用 Redis DB 分区**

```
DB 0 - Celery Broker
DB 1 - Application Cache（Buffer/RateLimit/Config）
```

理由：
- 逻辑隔离
- 便于清理和调试
- 避免 key 命名冲突

---

## 4. 配置管理决策

### 4.1 配置来源

**决策：环境变量优先，支持 .env 文件**

理由：
- 12-Factor App 最佳实践
- Docker/K8s 部署友好
- 敏感信息不入代码仓库

### 4.2 Feature Flags

**决策：支持以下功能开关**

| 开关 | 默认值 | 影响 |
|------|--------|------|
| LLM_ENABLED | true | 关闭后边界判别全部降级 Batch |
| EMBEDDING_ENABLED | true | 关闭后 embedding 跳过 |
| IMMEDIATE_ENABLED | true | 关闭后只有 Batch/Digest |
| EMAIL_ENABLED | true | 关闭后只站内通知 |

### 4.3 节流配置

**决策：配置化所有节流参数**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| NEWSNOW_FETCH_INTERVAL_SEC | 1800 | 30分钟 |
| RSS_FETCH_INTERVAL_SEC | 900 | 15分钟 |
| ITEMS_PER_SOURCE_PER_FETCH | 20 | 单源单轮上限 |
| INGEST_SOURCES_PER_MIN | 60 | 源/分钟上限 |
| EMBED_PER_MIN | 300 | 嵌入/分钟上限 |
| JUDGE_PER_DAY | 200 | 判别/日上限 |
| DAILY_USD_BUDGET | 0.33 | 日预算（美元） |

---

## 5. 健康检查设计

### 5.1 检查项

**决策：/health 端点检查所有关键依赖**

```json
{
  "status": "healthy|degraded|unhealthy",
  "db": "ok|error",
  "redis": "ok|error",
  "environment": "local|staging|production",
  "version": "0.1.0"
}
```

### 5.2 降级策略

**决策：组件故障时的降级行为**

| 组件 | 故障时行为 |
|------|-----------|
| PostgreSQL | 服务不可用（核心依赖） |
| Redis | 降级运行（队列/缓存不可用，但 API 可响应） |
| OpenAI | 边界判别降级 Batch |
| SMTP | 站内通知仍可用 |

---

## 6. 新增表：ingest_logs

### 6.1 设计理由

`docs/product/PRD_v0.md` 第 5.1 节提到 `ingest_logs（可选但建议）`，我决定在 v0 就实现它：

理由：
- 便于监控抓取健康状况
- 便于排查抓取失败原因
- 符合可观测性要求

### 6.2 表结构

```sql
ingest_logs (
  id STRING PK,
  source_id STRING FK,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  status ENUM(success, partial, failed),
  items_fetched INT,
  items_new INT,
  items_duplicate INT,
  error_message TEXT,
  created_at TIMESTAMP
)
```

---

## 7. 迁移决策

### 7.1 迁移工具

**决策：继续使用 Alembic**

理由：
- 项目已配置好 Alembic
- SQLAlchemy 官方推荐
- 支持异步迁移

### 7.2 迁移版本管理

**决策：使用语义化版本号前缀**

格式：`{序号}_{描述}.py`，例如：
- `0001_init.py`
- `0002_add_ingest_logs.py`

---

## 8. 测试架构设计

### 8.1 测试分层策略

根据 `docs/specs/TECH_SPEC_v0.md` 第 10 节的测试策略要求，采用三层测试架构：

```
tests/
├── conftest.py          # 共享 fixtures
├── unit/                # 单元测试（不依赖外部服务）
│   ├── domain/          # 领域逻辑测试
│   ├── application/     # 应用服务测试
│   └── infrastructure/  # 基础设施测试（with mock）
├── integration/         # 集成测试（需要 DB/Redis）
│   ├── repositories/    # 仓储层测试
│   ├── api/             # API 端点测试
│   └── workers/         # Worker 任务测试
└── e2e/                 # 端到端测试（完整流程）
    └── flows/           # 业务流程测试
```

### 8.2 测试策略矩阵

| 测试类型 | 覆盖范围 | 依赖 | 运行频率 |
|----------|----------|------|----------|
| 单元测试 | 去重、阈值分桶、STRICT/SOFT 规则、合并策略、预算熔断、Schema 校验 | 无 | 每次提交 |
| 集成测试 | Repository、API、Worker | DB/Redis（Docker） | PR 合并前 |
| 端到端测试 | 抓取→推送→反馈完整流程 | 全部服务 | 发布前 |

### 8.3 关键测试场景

**必须覆盖的单测：**
- [ ] URL 去重逻辑（`url_hash` 唯一性）
- [ ] 阈值分桶（≥0.93→Immediate, 0.75~0.88→Batch, <0.75→Ignore）
- [ ] STRICT/SOFT 模式规则
- [ ] Immediate 合并策略（5分钟窗口，最多3条）
- [ ] 预算熔断逻辑
- [ ] LLM 输出 Schema 校验

**必须覆盖的集成测试：**
- [ ] 完整的 CRUD 流程（Goal/Source）
- [ ] 匹配计算流程
- [ ] 推送决策流程
- [ ] 反馈处理流程

**必须覆盖的端到端测试：**
- [ ] 模拟抓取 → 入库 → 匹配 → 推送 → 反馈

### 8.4 测试 Fixtures 设计

已在 `tests/conftest.py` 中实现：

| Fixture | 用途 | 级别 |
|---------|------|------|
| `test_settings` | 测试环境配置 | function |
| `test_engine` | 测试数据库引擎 | session |
| `db_session` | 事务回滚的数据库会话 | function |
| `mock_db_session` | Mock 数据库会话 | function |
| `redis_client` | 真实 Redis 客户端 | function |
| `mock_redis_client` | Mock Redis 客户端 | function |
| `async_client` | HTTP 测试客户端 | function |
| `mock_openai_client` | Mock OpenAI | function |
| `mock_smtp_client` | Mock SMTP | function |
| `sample_*_data` | 各种领域对象样本 | function |

### 8.5 测试运行命令

```bash
# 运行所有测试
uv run pytest

# 只运行单元测试
uv run pytest tests/unit/

# 只运行集成测试（需要 Docker）
uv run pytest tests/integration/ -m integration

# 运行带覆盖率
uv run pytest --cov=src --cov-report=html

# 运行特定模块测试
uv run pytest tests/unit/domain/test_bucket_logic.py -v
```

### 8.6 覆盖率要求

当前配置（`pyproject.toml`）：
- 最低覆盖率：30%（v0 阶段）
- 分支覆盖：启用
- 覆盖报告：HTML 格式

v1 目标覆盖率：
- 单元测试：60%+
- 关键路径：80%+

---

## 9. 验证步骤

### 8.1 本地开发环境启动

```bash
# 1. 启动 PostgreSQL 和 Redis
cd infoSentry-backend
docker-compose up -d postgres redis

# 2. 等待服务就绪
docker-compose exec postgres pg_isready
docker-compose exec redis redis-cli ping

# 3. 创建 .env 文件
cp .env.example .env
# 编辑 .env 配置数据库密码等

# 4. 运行数据库迁移
uv run alembic upgrade head

# 5. 启动 API 服务
uv run uvicorn main:app --reload

# 6. 验证健康检查
curl http://localhost:8000/health
```

### 8.2 验证清单

- [x] 迁移脚本语法正确（`python -m py_compile alembic/versions/*.py`）
- [x] 所有模块可正确导入
- [x] Celery 队列配置正确（5 个队列）
- [x] Redis 客户端封装正确
- [x] 健康检查端点配置正确
- [x] Feature Flags 配置正确

### 8.3 完成标准验证

| 标准 | 状态 | 说明 |
|------|------|------|
| `db migrate` 一键完成 | ✅ | `alembic upgrade head` |
| API 可启动并连通 DB/Redis | ✅ | 健康检查端点验证 |
| 基础配置在 `.env` 模板中列出 | ✅ | `.env.example` 已创建 |

---

## 9. 文件变更清单

### 新增文件

| 文件路径 | 说明 |
|----------|------|
| `src/core/infrastructure/celery/__init__.py` | Celery 模块初始化 |
| `src/core/infrastructure/celery/app.py` | Celery 应用配置 |
| `src/core/infrastructure/celery/queues.py` | 队列定义与路由 |
| `src/core/infrastructure/redis/__init__.py` | Redis 模块初始化 |
| `src/core/infrastructure/redis/client.py` | Redis 客户端封装 |
| `src/core/infrastructure/redis/keys.py` | Redis Key 命名规范 |
| `alembic/versions/0002_add_ingest_logs.py` | ingest_logs 表迁移 |
| `.env.example` | 环境变量模板 |
| `docker-compose.yml` | 本地开发环境编排 |

### 修改文件

| 文件路径 | 变更说明 |
|----------|----------|
| `src/core/config.py` | 添加 Feature Flags、节流配置、Celery 配置 |
| `src/modules/sources/infrastructure/models.py` | 添加 IngestLogModel |
| `alembic/env.py` | 导入 IngestLogModel |
| `main.py` | 增强健康检查端点 |
| `src/core/infrastructure/database/session.py` | 添加 check_db_health 函数 |

---

## 10. 信息摄取（Ingest）设计决策

### 10.1 抓取器架构

**决策：采用策略模式 + 工厂模式**

```
BaseFetcher (抽象基类)
    │
    ├── NewsNowFetcher   (HTML 解析)
    ├── RSSFetcher       (RSS/Atom 解析)
    └── SiteFetcher      (CSS 选择器)

FetcherFactory.create(source_type, config) → BaseFetcher
```

理由：
- 不同源类型需要不同的抓取和解析逻辑
- 工厂模式统一创建入口，便于扩展新类型
- 策略模式使抓取逻辑可替换、可测试

### 10.2 URL 去重策略

**决策：使用 SHA-256 哈希前 32 位作为 url_hash**

```python
def _compute_url_hash(url: str) -> str:
    normalized = url.strip().lower().rstrip("/")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]
```

理由：
- 标准化 URL（小写、移除尾部斜杠）避免重复
- SHA-256 碰撞概率极低
- 32 字符长度够用且节省存储

### 10.3 抓取调度策略

**决策：Celery Beat + 按源独立任务**

- `check_and_dispatch_fetches`: 每分钟检查到期源
- `ingest_source`: 每个源独立任务，支持重试

理由：
- 源之间相互隔离，一个失败不影响其他
- 可独立重试和追踪
- 便于控制并发和节流

### 10.4 错误处理与退避

**决策：指数退避 + 连续错误计数**

```python
backoff_multiplier = min(2 ** error_streak, 8)
delay_seconds = min(fetch_interval * backoff_multiplier, 14400)  # 最大 4 小时
```

理由：
- 避免对故障源频繁请求
- 错误恢复后自动回归正常调度
- 可配置的最大退避时间

### 10.5 解析降级策略

**决策：优先使用专业库，降级使用基础解析**

| 抓取器 | 主要方案 | 降级方案 |
|--------|----------|----------|
| RSS | feedparser | xml.etree.ElementTree |
| NewsNow | BeautifulSoup | 正则表达式 |
| SITE | BeautifulSoup | - (必须依赖) |

理由：
- 提高系统容错性
- 减少对可选依赖的强依赖
- 降级时记录日志便于排查

### 10.6 新增文件清单

| 文件路径 | 说明 |
|----------|------|
| `src/modules/sources/infrastructure/fetchers/__init__.py` | 抓取器模块导出 |
| `src/modules/sources/infrastructure/fetchers/base.py` | 抓取器基类 |
| `src/modules/sources/infrastructure/fetchers/newsnow.py` | NewsNow 抓取器 |
| `src/modules/sources/infrastructure/fetchers/rss.py` | RSS 抓取器 |
| `src/modules/sources/infrastructure/fetchers/site.py` | SITE 抓取器 |
| `src/modules/sources/infrastructure/fetchers/factory.py` | 抓取器工厂 |
| `src/modules/sources/application/ingest_service.py` | 抓取协调服务 |
| `src/modules/sources/infrastructure/ingest_log_repository.py` | 抓取日志仓储 |
| `src/modules/sources/tasks.py` | Celery 任务 |
| `tests/unit/test_ingest.py` | 单元测试（35 个用例） |

---

## 11. 向量化与匹配（Embed & Match）设计决策

### 11.1 整体架构

**决策：采用服务层 + Celery 任务的分离架构**

```
EmbeddingService (嵌入服务)
    └── 调用 OpenAI API
    └── 检查预算熔断
    └── 更新 Item 状态

BudgetService (预算熔断服务)
    └── Redis 存储日预算状态
    └── 检查/记录 embedding 和 judge 使用量

MatchService (匹配计算服务)
    └── 计算匹配分数
    └── 生成可解释原因
    └── 保存匹配结果
```

理由：
- 服务层封装业务逻辑，Celery 任务负责调度
- 服务类可被多处复用（API、任务、事件处理器）
- 便于单元测试（Mock 依赖即可）

### 11.2 嵌入服务设计

**决策：延迟初始化 OpenAI 客户端 + 重试机制**

```python
@retry(
    retry=retry_if_exception_type((Exception,)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def _generate_embedding(self, text: str) -> tuple[list[float], int]:
    ...
```

理由：
- 延迟初始化避免启动时创建无用连接
- 指数退避重试提高成功率
- 最多重试 3 次避免无限循环

### 11.3 预算熔断策略

**决策：Redis 存储 + 日粒度预算**

```python
BudgetStatus(
    date: str,              # 日期 YYYY-MM-DD
    embedding_tokens: int,  # embedding 使用的 tokens
    judge_tokens: int,      # LLM judge 使用的 tokens
    usd_est: float,         # 费用估算（美元）
    embedding_disabled: bool,  # embedding 熔断标志
    judge_disabled: bool,      # judge 熔断标志
)
```

检查逻辑：
1. 检查全局开关（`EMBEDDING_ENABLED`/`LLM_ENABLED`）
2. 检查熔断标志
3. 检查日预算（`DAILY_USD_BUDGET`）
4. 检查次数限制（`EMBED_PER_DAY`/`JUDGE_PER_DAY`）

理由：
- Redis 存储支持分布式部署
- 日粒度符合预算控制需求
- 多重检查防止超预算

### 11.4 匹配分数计算

**决策：多因子加权模型**

```python
WEIGHT_COSINE = 0.40   # 语义相似度权重
WEIGHT_TERMS = 0.30    # 词条命中权重
WEIGHT_RECENCY = 0.20  # 时效性权重
WEIGHT_SOURCE = 0.10   # 来源可信度权重
```

时效性衰减：
- 6 小时内：满分
- 6-48 小时：线性衰减到 0.5
- 48 小时-7 天：继续衰减
- 7 天后：零分

理由：
- 多因子模型比单一指标更全面
- 权重可配置化（后续可调整）
- 时效性衰减反映新闻价值规律

### 11.5 可解释性设计

**决策：结构化 reasons + evidence**

```python
MatchReasons(
    summary: str,           # 简短摘要（如：命中关键词「AI」；语义相关）
    evidence: list[dict],   # 证据列表（TERM_HIT, SEMANTIC_MATCH, FRESH_CONTENT）
    is_blocked: bool,       # 是否被阻止
    block_reason: str,      # 阻止原因
)
```

证据类型：
- `TERM_HIT`: 命中优先词
- `SEMANTIC_MATCH`: 语义相似度高
- `FRESH_CONTENT`: 新鲜内容

理由：
- 用户可理解为什么推荐
- 便于调试和优化模型
- 符合 PRD 的 explainable match_reasons 要求

### 11.6 STRICT/SOFT 模式处理

**决策：模式在匹配时检查，影响是否阻止**

| 模式 | 行为 |
|------|------|
| STRICT | 未命中任何 must term → 阻止匹配 |
| SOFT | must term 作为加分项，不强制 |

负面词统一处理：
- 命中任何 negative term → 阻止匹配

理由：
- STRICT 模式提供精确控制
- SOFT 模式更宽松，适合探索性目标
- 负面词优先级最高，任何模式下都阻止

### 11.7 Celery 任务设计

**决策：单项任务 + 批量任务 + 事件触发**

| 任务 | 队列 | 触发方式 |
|------|------|----------|
| `embed_item` | q_embed | ItemIngested 事件 |
| `embed_pending_items` | q_embed | Celery Beat (每分钟) |
| `match_item` | q_match | embed_item 完成后 |
| `match_items_for_goal` | q_match | Goal 创建/更新后 |

理由：
- 事件触发保证及时性
- 定时批量处理兜底遗漏
- Goal 更新后重新匹配保证一致性

### 11.8 新增文件清单

| 文件路径 | 说明 |
|----------|------|
| `src/modules/items/application/__init__.py` | 应用层模块初始化 |
| `src/modules/items/application/embedding_service.py` | 嵌入服务 |
| `src/modules/items/application/budget_service.py` | 预算熔断服务 |
| `src/modules/items/application/match_service.py` | 匹配计算服务 |
| `src/modules/items/tasks.py` | Celery 任务 |
| `tests/unit/test_embedding_match.py` | 单元测试（26 个用例） |

### 11.9 测试覆盖

单元测试覆盖：
- [x] BudgetStatus 序列化/反序列化
- [x] BudgetService 预算检查逻辑
- [x] BudgetService 使用量记录
- [x] MatchFeatures/MatchReasons 序列化
- [x] MatchService 词条命中检测
- [x] MatchService 时效性计算
- [x] MatchService 原因生成
- [x] MatchService 分数计算
- [x] STRICT/SOFT 模式处理
- [x] MatchResult 有效性检查

---

## 12. Push Orchestrator Agent Runtime 设计决策

### 12.1 整体架构

**决策：采用 Node Pipeline + Tool Registry 的模块化架构**

```
AgentState (状态对象)
    │
    v
┌─────────────────┐
│ LoadContextNode │ 加载 Goal/Item/Budget 上下文
└────────┬────────┘
         │
         v
┌─────────────────┐
│  RuleGateNode   │ 规则守门（blocked_sources/negative_terms/STRICT）
└────────┬────────┘
         │
         v
┌─────────────────┐
│   BucketNode    │ 阈值分桶（IMMEDIATE/BOUNDARY/BATCH/IGNORE）
└────────┬────────┘
         │
         v (仅 BOUNDARY)
┌─────────────────────┐
│ BoundaryJudgeNode   │ LLM 边界判别（失败降级 BATCH）
└────────┬────────────┘
         │
         v (仅 IMMEDIATE)
┌─────────────────┐
│  CoalesceNode   │ 5 分钟合并窗口
└────────┬────────┘
         │
         v
┌─────────────────┐
│ EmitActionsNode │ 发出决策动作
└─────────────────┘
```

理由：
- 每个 Node 职责单一，易于测试和维护
- Pipeline 编排灵活，可按需组合
- 符合 AGENT_RUNTIME_SPEC.md 的"可图化"设计

### 12.2 阈值分桶策略

**决策：四级分桶 + 可配置阈值**

```python
ThresholdConfig(
    immediate_threshold=0.93,  # >= 此值直通 IMMEDIATE
    boundary_lower=0.88,       # >= 此值进入 BOUNDARY（LLM 判别）
    batch_threshold=0.75,      # >= 此值进入 BATCH
)
# < batch_threshold → IGNORE
```

| 分桶 | 分数范围 | 处理方式 |
|------|----------|----------|
| IMMEDIATE | >= 0.93 | 直接推送 |
| BOUNDARY | 0.88 ~ 0.93 | LLM 判别后决定 |
| BATCH | 0.75 ~ 0.88 | 批量窗口推送 |
| IGNORE | < 0.75 | 不推送 |

理由：
- 高分直通减少 LLM 调用
- 边界区域用 LLM 精细判别
- 阈值可配置，便于调优

### 12.3 规则守门设计

**决策：三重守门 + 短路返回**

检查顺序：
1. `blocked_sources`: 来源被用户屏蔽 → 阻止
2. `negative_terms`: 命中负面词 → 阻止
3. `STRICT` 模式: 未命中任何 must_term → 阻止

```python
class BlockReason(str, Enum):
    BLOCKED_SOURCE = "BLOCKED_SOURCE"
    NEGATIVE_TERM = "NEGATIVE_TERM"
    STRICT_NO_HIT = "STRICT_NO_HIT"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
```

理由：
- 规则守门在分桶之前，避免无效计算
- 阻止原因记录便于调试
- 短路返回提高性能

### 12.4 边界 LLM 判别

**决策：Cheap Model + 结构化输出 + 失败降级**

```python
BoundaryJudgeOutput(
    label: "IMMEDIATE" | "BATCH",
    confidence: float,  # 0.0 ~ 1.0
    uncertain: bool,
    reason: str,
    evidence: list[dict],
)
```

失败处理：
- Schema 校验失败 → 降级 BATCH
- API 超时/429 → 降级 BATCH
- judge_disabled=True → 跳过，降级 BATCH

理由：
- 使用 cheap model（如 gpt-4o-mini）控制成本
- 结构化输出便于校验和使用
- 保守降级策略，宁可批量不可漏推

### 12.5 Tool Registry 设计

**决策：只读/写分权 + 自动记录**

只读工具（默认允许）：
- `get_goal_context`: 获取 Goal 上下文
- `get_item`: 获取 Item 信息
- `get_history`: 获取历史决策
- `check_budget`: 检查预算状态

写工具（严格控制）：
- `emit_decision`: 创建推送决策
- `enqueue_email`: 加入邮件队列

所有调用自动记录到 `agent_tool_calls` 表。

理由：
- 分权控制副作用
- 完整记录便于回放和审计
- 便于扩展新工具

### 12.6 回放设计

**决策：Input Snapshot + Tool Calls + Diff**

```python
async def replay(run_id: str) -> dict:
    # 1. 读取原始 input_snapshot
    # 2. 重建 AgentState
    # 3. 重新执行 Pipeline
    # 4. 对比原始动作与重放动作
    return {
        "original_actions": [...],
        "replayed_actions": [...],
        "diff": [...],
    }
```

用途：
- 定位误报/漏报
- 调优阈值
- 验证新策略

理由：
- 完整快照支持精确重放
- Diff 输出便于分析差异
- 符合 AGENT_RUNTIME_SPEC.md 的回放要求

### 12.7 Celery 任务设计

| 任务 | 队列 | 触发方式 |
|------|------|----------|
| `handle_match_computed` | q_agent | MatchComputed 事件 |
| `check_and_trigger_batch_windows` | q_agent | Celery Beat (每分钟) |
| `check_and_send_digest` | q_agent | Celery Beat (每 5 分钟) |
| `check_and_update_budget` | q_agent | Celery Beat (每小时) |

理由：
- 事件驱动处理即时判别
- 定时任务处理窗口推送
- 预算同步保持一致性

### 12.8 新增文件清单

| 文件路径 | 说明 |
|----------|------|
| `src/modules/agent/application/__init__.py` | 应用层模块初始化 |
| `src/modules/agent/application/state.py` | AgentState 数据结构 |
| `src/modules/agent/application/nodes.py` | Node 实现（6 个节点） |
| `src/modules/agent/application/tools.py` | Tool Registry |
| `src/modules/agent/application/llm_service.py` | LLM 判别服务 |
| `src/modules/agent/application/orchestrator.py` | Agent 编排器 |
| `src/modules/agent/infrastructure/mappers.py` | 数据映射器 |
| `src/modules/agent/infrastructure/repositories.py` | 仓储实现 |
| `src/modules/agent/tasks.py` | Celery 任务 |
| `tests/unit/test_agent.py` | 单元测试（37 个用例） |

### 12.9 测试覆盖

单元测试覆盖：
- [x] ThresholdConfig 分桶逻辑（5 个用例）
- [x] AgentState 创建和序列化
- [x] RuleGateNode 规则守门（5 个用例）
- [x] BucketNode 分桶（5 个用例）
- [x] BoundaryJudgeNode LLM 判别和降级
- [x] EmitActionsNode 动作发出
- [x] NodePipeline 管道执行
- [x] ToolRegistry 工具注册和调用
- [x] BoundaryJudgeOutput Schema 校验
- [x] ActionProposal 序列化

---

## 更新日志

| 日期 | 内容 |
|------|------|
| 2025-01-06 | 初始版本，记录架构与数据底座阶段决策 |
| 2025-01-06 | 添加信息摄取（Ingest）模块设计决策 |
| 2025-01-06 | 添加向量化与匹配（Embed & Match）模块设计决策 |
| 2025-01-06 | 添加 Push Orchestrator Agent Runtime 设计决策 |
