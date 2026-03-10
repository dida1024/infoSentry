# infoSentry 系统架构规格

版本：v0.3
日期：2025-12-28
部署：单机 VM（2c4g）
默认时区：Asia/Shanghai（v0 固定；v1 支持可配）
信息源：NewsNow（约 30 个 source，全启用）+ RSS + SITE（list-only）
推送：站内 + Email（SMTP）
AI：OpenAI API 协议（embedding + 边界判别；便宜小模型 + 不确定升级）
预算：LLM 月成本 ≤ $10（单人）

---

## Purpose

infoSentry 是一个信息追踪 Agent 系统，闭环跑通：Ingest → Dedupe → Embed → Match → Agent Decide → Notify → Click/Feedback → 收敛。系统采用模块化单体 + 队列隔离架构，在单机 2c4g VM 上交付 v0 MVP，支持三层推送决策（Immediate/Batch/Digest）和可回放的 Agent Runtime。

---

## Architecture & Modules

### REQ-ARCH-001: 模块化单体 + 队列隔离

系统 MUST 采用模块化单体架构，通过 Celery 队列实现模块间隔离，不做微服务拆分。

**理由**：单人、两周交付、单机部署下 ROI 最优；微服务治理成本高于收益。
**退出条件**：多用户/高吞吐/多团队并行时再拆服务。

#### Scenario: 模块间通过队列通信

```
Given 系统部署为模块化单体
When 一个模块需要触发另一个模块的处理逻辑
Then 该模块 MUST 通过 Celery 队列投递任务
  And 不得通过进程内直接函数调用跨模块边界
```

#### Scenario: 队列拆分保证隔离

```
Given Celery 配置了以下独立队列：q_ingest、q_embed、q_match、q_agent、q_email
When 任一队列出现堆积或故障
Then 其他队列的处理 MUST NOT 受影响
  And 各队列 MUST 由独立的 worker 进程消费
```

### REQ-ARCH-002: 模块划分

系统 MUST 包含以下模块，各模块职责明确。

| 模块 | 技术选型 | 职责 |
|------|---------|------|
| Web | Next.js | 极简配置/查看/反馈 |
| API | FastAPI | Auth/CRUD/查询/回放 |
| Workers | Celery（按队列拆容器） | ingest/embed/match/agent/email |
| Scheduler | Celery Beat | Batch windows & Digest tick |
| Storage | PostgreSQL + pgvector, Redis | 持久化 + 向量存储 + 缓存 |
| SMTP | 邮件发送 | 外部邮件投递 |

#### Scenario: Worker 按队列拆分容器

```
Given Workers 模块使用 Celery
When 系统启动 worker 进程
Then ingest worker MUST 仅消费 q_ingest 队列
  And embed worker MUST 仅消费 q_embed 队列
  And match worker MUST 仅消费 q_match 队列
  And agent worker MUST 仅消费 q_agent 队列
  And email worker MUST 仅消费 q_email 队列
```

### REQ-ARCH-003: 并发配置（2c4g 单机）

系统 MUST 遵守以下默认并发配置以适配 2c4g 资源限制。

| Worker | 并发数 |
|--------|--------|
| worker_ingest | concurrency=2 |
| worker_embed_match | concurrency=1（或拆成 embed=1, match=1） |
| worker_agent | concurrency=1 |
| worker_email | concurrency=1 |
| API (uvicorn) | workers=1~2（根据 CPU） |

#### Scenario: 资源受限时保持稳定

```
Given 系统运行在 2c4g 单机 VM 上
When 所有 worker 同时运行
Then 总内存占用 SHOULD 不超过 3.5GB（留余量给 OS 和 PostgreSQL）
  And CPU 使用率 SHOULD 保持在 80% 以下（均值）
```

### REQ-ARCH-004: Agent 实现策略

v0 MUST 自研轻量 Agent Runtime，不引入外部编排框架。

#### Scenario: Agent Runtime 自研实现

```
Given v0 阶段不引入 LangGraph 等框架
When 实现 Agent Runtime
Then Runtime MUST 包含 state 管理、tools 注册、ledger 记录三个核心能力
  And 流程 MUST 拆成独立 nodes（可迁移）
  And 每个 node SHOULD 可独立测试
```

#### Scenario: v1 框架引入时保持兼容

```
Given v1 决定引入 LangGraph 等编排框架
When 替换编排层
Then 仅替换 wiring（编排逻辑）
  And nodes/tools 实现 MUST NOT 需要重写
```

---

## Data Flow & Pipeline

### REQ-FLOW-001: 端到端数据流

系统 MUST 实现以下完整数据流水线：

```
[NewsNow/RSS/SITE]
        |
        v
ingest_* workers  –> items(upsert+dedupe) –> embed_queue
        |
        v
embed worker (pgvector)
        |
        v
match worker -> goal_item_matches
        |
        v
Agent Runtime (rules+tools+LLM boundary)
        |           |
        |           +–> agent_runs/tool_calls/action_ledger
        v
push_decisions -> coalesce buffer (5m)
        |
        v
email worker (SMTP)
        |
        v
click redirect -> click_events ; feedback -> item_feedback/blocked_sources
```

#### Scenario: 正常抓取到推送闭环

```
Given NewsNow/RSS/SITE 信息源正常可达
  And 用户已创建至少一个 Goal
When ingest worker 抓取到新 item
Then 系统 MUST 按顺序执行：upsert + dedupe → embed → match → agent decide → push
  And 每一步的输出 MUST 作为下一步的输入
  And 最终产出 push_decision 记录
```

#### Scenario: 去重（Dedupe）

```
Given items 表存在 url_hash unique 约束
When ingest worker 抓取到一个已存在 url_hash 的 item
Then 系统 MUST 跳过该 item 的重复插入
  And MUST NOT 触发后续 embed/match 流程
```

### REQ-FLOW-002: 三层推送决策

系统 MUST 支持三层推送决策模型。

#### Scenario: Immediate 推送（事件触发 + 合并）

```
Given Agent Runtime 判定某 match 为 IMMEDIATE 级别
When 产出 push_decision（decision=IMMEDIATE）
Then 系统 MUST 将该 decision 放入 coalesce buffer
  And buffer 窗口为 5 分钟
  And 窗口内同一 goal 的多个 IMMEDIATE decision SHOULD 合并为一封邮件
```

#### Scenario: Batch 推送（窗口触发）

```
Given Celery Beat 调度 Batch 窗口 tick
When 窗口时间到达
Then 系统 MUST 收集该窗口内所有 decision=BATCH 的 push_decisions
  And 按 goal 分组打包推送
```

#### Scenario: Digest 推送（每日汇总）

```
Given Celery Beat 调度 Digest tick
When 每日汇总时间到达
Then 系统 MUST 收集过去 24 小时内所有 decision=DIGEST 的 push_decisions
  And 生成汇总摘要推送给用户
```

### REQ-FLOW-003: Embedding 与匹配

embedding MUST 使用 pgvector 存储向量，match_score 为多信号综合评分。

#### Scenario: 向量生成与存储

```
Given 一个新 item 完成 ingest
When embed worker 处理该 item
Then MUST 调用 embedding 模型生成向量
  And MUST 将向量存入 items.embedding 字段（pgvector）
  And MUST 更新 embedding_status 为 done
  And MUST 记录 embedding_model
```

#### Scenario: 匹配评分计算

```
Given 一个 item 已完成 embedding
When match worker 计算该 item 与某 goal 的匹配度
Then match_score MUST 综合以下信号：语义相似度 + term 命中 + recency + source_trust
  And MUST 在 reasons_json 中给出可解释的评分依据
  And MUST 在 features_json 中记录各维度原始分值
```

### REQ-FLOW-004: Agent Runtime 决策流程

Agent Runtime MUST 是决策型系统，具备 state/tools/ledger 的可回放能力。LLM 仅是其中一个推理节点。

#### Scenario: 规则守门优先

```
Given 一个 goal_item_match 进入 Agent Runtime
When match 命中 STRICT 规则、blocked 名单或 negative 关键词
Then 系统 MUST 直接按规则决策（不调用 LLM）
  And MUST 在 reason_json 中记录规则命中的具体条件
```

#### Scenario: 边界样本 LLM 判别

```
Given 一个 goal_item_match 未命中明确规则（处于边界区间）
When Agent Runtime 需要判定推送级别
Then MUST 调用 LLM 进行判别
  And LLM 输出 MUST 为强制 JSON Schema 格式
  And 输出 MUST 包含解释（explanation）和引用证据（evidence）
  And 若 LLM 调用失败，MUST 保守降级到 Batch 或 Digest
```

#### Scenario: Agent Run 可回放

```
Given Agent Runtime 完成一次决策
When 记录该次运行
Then MUST 创建 agent_runs 记录，包含：trigger、status、input_snapshot_json、output_snapshot_json、final_actions_json、budget_snapshot_json
  And MUST 记录所有 tool_calls（input/output/status/latency）
  And MUST 在 action_ledger 中记录所有产出的 action（不可变）
```

### REQ-FLOW-005: 反馈闭环

#### Scenario: 点击追踪

```
Given 用户收到推送邮件
When 用户点击邮件中的链接 /r/{item_id}?goal_id=...&channel=...
Then 系统 MUST 记录 click_event
  And MUST 302 重定向到原始 URL
```

#### Scenario: 用户反馈

```
Given 用户在 Inbox 页面对某 item 进行反馈
When 用户提交 feedback（like/dislike）或 block_source
Then 系统 MUST 记录到 item_feedback 表
  And 若 block_source=true，MUST 同步写入 blocked_sources 表
```

---

## Data Model Invariants

### REQ-DATA-001: Sources 表结构

sources 表 MUST 包含以下核心字段和索引。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | uuid pk | 主键 |
| type | enum | NEWSNOW / RSS / SITE |
| name | text | 源名称 |
| enabled | bool | v0 默认 true |
| fetch_interval_sec | int | 抓取间隔（秒） |
| next_fetch_at | timestamptz | 下次抓取时间（indexed） |
| last_fetch_at | timestamptz | 上次抓取时间 |
| error_streak | int | 连续错误次数 |
| empty_streak | int | 连续空结果次数 |
| config | jsonb | 源特定配置 |

config 按 type 区分结构：
- NEWSNOW: `{base_url, source_id}`
- RSS: `{feed_url}`
- SITE: `{list_url, selectors...}`

索引：`(enabled, next_fetch_at)`, `(type, enabled)`

#### Scenario: Sources 幂等与调度

```
Given sources 表已配置索引 (enabled, next_fetch_at)
When Scheduler 查询下一批待抓取的 source
Then 查询 MUST 使用 WHERE enabled=true AND next_fetch_at <= now()
  And 结果 MUST 按 next_fetch_at 升序排列
```

### REQ-DATA-002: Items 表结构

items 表 MUST 包含以下核心字段和约束。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | uuid pk | 主键 |
| source_id | fk | 关联 sources |
| url | text | 原始 URL |
| url_hash | text unique | URL 去重键 |
| title | text | 标题 |
| snippet | text | 摘要片段 |
| published_at | timestamptz | 发布时间 |
| ingested_at | timestamptz | 入库时间 |
| embedding | vector(...) | pgvector 向量 |
| embedding_status | enum | pending / done / skipped_budget |
| embedding_model | text | 使用的模型名 |

索引：`unique(url_hash)`, `(published_at desc)`, `(source_id, published_at desc)`

#### Scenario: Item 去重键唯一性

```
Given items 表存在 unique(url_hash) 约束
When 两个 ingest worker 并发插入相同 URL 的 item
Then 仅一个插入 MUST 成功
  And 另一个 MUST 因唯一约束冲突而跳过（upsert）
  And MUST NOT 产生重复记录
```

### REQ-DATA-003: Goal-Item Matches 表结构

goal_item_matches 表 MUST 使用复合主键 `(goal_id, item_id)`。

| 字段 | 类型 | 说明 |
|------|------|------|
| goal_id | fk | 关联 goals |
| item_id | fk | 关联 items |
| match_score | float | 综合匹配分 |
| features_json | jsonb | 各维度分值 |
| reasons_json | jsonb | 可解释评分依据 |
| computed_at | timestamptz | 计算时间 |

PK: `(goal_id, item_id)`
索引：`(goal_id, match_score desc, computed_at desc)`

#### Scenario: Match 结果可解释

```
Given match worker 计算出一个 goal_item_match
When 写入 goal_item_matches 表
Then reasons_json MUST NOT 为空
  And reasons_json MUST 包含评分各维度的解释
  And features_json MUST 包含语义相似度、term 命中、recency、source_trust 的原始值
```

### REQ-DATA-004: Push Decisions 表结构

push_decisions 表 MUST 包含决策记录和幂等去重键。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | uuid pk | 主键 |
| goal_id | fk | 关联 goals |
| item_id | fk | 关联 items |
| decision | enum | IMMEDIATE / BATCH / DIGEST / IGNORE |
| status | enum | PENDING / SENT / FAILED / SKIPPED |
| channel | enum | EMAIL / IN_APP |
| reason_json | jsonb | 决策原因（MUST 含 evidence） |
| decided_at | timestamptz | 决策时间 |
| sent_at | timestamptz | 发送时间 |
| dedupe_key | text unique | goal+item+decision 组合去重 |

#### Scenario: Push Decision 幂等

```
Given push_decisions 表存在 unique(dedupe_key) 约束
When Agent Runtime 对同一 goal+item+decision 组合重复产出决策
Then 第二次写入 MUST 因 dedupe_key 冲突而跳过
  And MUST NOT 产生重复推送
```

#### Scenario: Push Decision 必须包含证据

```
Given Agent Runtime 产出一个 push_decision
When 写入 reason_json 字段
Then reason_json MUST 包含 evidence 对象
  And evidence MUST 包含：source、url、published_at、matched_terms、snippet_quote
```

### REQ-DATA-005: Agent 可观测性表结构

agent_runs、agent_tool_calls、agent_action_ledger 三表 MUST 完整记录 Agent 运行过程。

#### agent_runs

| 字段 | 类型 | 说明 |
|------|------|------|
| id | uuid pk | run_id |
| trigger | enum | MatchComputed / BatchWindowTick / DigestTick |
| goal_id | fk | 关联 goals |
| status | enum | SUCCESS / TIMEOUT / ERROR / FALLBACK |
| plan_json | jsonb | 可选 |
| input_snapshot_json | jsonb | 输入快照（脱敏） |
| output_snapshot_json | jsonb | 输出快照 |
| final_actions_json | jsonb | 最终动作列表 |
| budget_snapshot_json | jsonb | 预算快照 |
| llm_used | bool | 是否调用了 LLM |
| model_name | text | 使用的模型名 |
| latency_ms | int | 耗时（毫秒） |
| created_at | timestamptz | 创建时间 |

#### agent_tool_calls

| 字段 | 类型 | 说明 |
|------|------|------|
| id | uuid pk | 主键 |
| run_id | fk | 关联 agent_runs |
| tool_name | text | 工具名 |
| input_json | jsonb | 工具输入 |
| output_json | jsonb | 工具输出 |
| status | enum | SUCCESS / ERROR |
| latency_ms | int | 耗时（毫秒） |
| created_at | timestamptz | 创建时间 |

索引：`(run_id, created_at)`

#### agent_action_ledger（不可变）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | uuid pk | 主键 |
| run_id | fk | 关联 agent_runs |
| action_type | enum | EMIT_DECISION / ENQUEUE_EMAIL / SUGGEST_TUNING |
| payload_json | jsonb | 动作负载 |
| created_at | timestamptz | 创建时间 |

索引：`(run_id, created_at)`

#### Scenario: Action Ledger 不可变

```
Given agent_action_ledger 表设计为不可变审计日志
When 一条 action 记录写入后
Then 该记录 MUST NOT 被 UPDATE 或 DELETE
  And 所有修正 MUST 通过追加新记录实现
```

#### Scenario: Agent Run 完整性

```
Given Agent Runtime 完成一次运行
When 记录 agent_run
Then agent_runs 记录 MUST 包含 input_snapshot_json（脱敏后的输入）
  And MUST 包含 budget_snapshot_json（当次预算状态）
  And 所有关联的 tool_calls MUST 通过 run_id 关联
  And 所有关联的 action_ledger MUST 通过 run_id 关联
```

### REQ-DATA-006: Budget Daily 表结构

budget_daily 表 SHOULD 按日追踪 LLM 使用成本。

| 字段 | 类型 | 说明 |
|------|------|------|
| date | date pk | 日期（主键） |
| embedding_tokens_est | int | embedding 预估 token 数 |
| judge_tokens_est | int | judge 预估 token 数 |
| usd_est | float | 预估美元成本 |
| embedding_disabled | bool | embedding 是否被熔断 |
| judge_disabled | bool | judge 是否被熔断 |

#### Scenario: 每日预算记录更新

```
Given budget_daily 表以 date 为主键
When 系统在一天内多次消耗 LLM token
Then 每次消耗 MUST 累加到当天的 embedding_tokens_est 或 judge_tokens_est
  And usd_est MUST 同步更新
```

---

## REST API Endpoints

### REQ-API-001: Auth 接口

系统 MUST 提供 Magic Link 认证。

- `POST /api/auth/request_link` — 请求登录链接，body: `{email}`
- `GET /api/auth/consume?token=...` — 消费一次性 token

#### Scenario: Magic Link 一次性消费

```
Given 用户请求了一个 magic link
When 用户通过 GET /api/auth/consume?token=... 消费该 token
Then 系统 MUST 验证 token 有效性并建立会话
  And 该 token MUST 被标记为已使用
  And 再次使用同一 token MUST 返回错误
```

### REQ-API-002: Goals 接口

系统 MUST 提供 Goal CRUD 和暂停/恢复操作。

- `GET /api/goals` — 列表
- `POST /api/goals` — 创建
- `GET /api/goals/{id}` — 详情
- `PUT /api/goals/{id}` — 更新
- `POST /api/goals/{id}/pause` — 暂停
- `POST /api/goals/{id}/resume` — 恢复

#### Scenario: Goal 暂停后停止匹配

```
Given 用户暂停了一个 Goal
When 新 item 进入 match 阶段
Then 系统 MUST NOT 对暂停的 Goal 计算匹配
  And 恢复后 MUST 对新 item 重新参与匹配
```

### REQ-API-003: Sources 接口

系统 MUST 提供 Source 管理接口。

- `GET /api/sources?type=` — 按类型筛选列表
- `POST /api/sources` — 创建
- `PUT /api/sources/{id}` — 更新
- `POST /api/sources/{id}/enable` — 启用
- `POST /api/sources/{id}/disable` — 禁用

### REQ-API-004: Notifications / Inbox 接口

系统 MUST 提供通知查询接口。

- `GET /api/notifications?goal_id=&cursor=` — 分页查询通知

#### Scenario: Notification 返回内容完整性

```
Given 用户查询 Inbox 通知列表
When GET /api/notifications 返回结果
Then 每条通知 MUST 包含 decision 和 status
  And MUST 包含 reason_json（含 evidence: source/url/published_at/matched_terms/snippet_quote）
  And MUST 包含可用 actions（例如 open url / like / block）
```

### REQ-API-005: Feedback & Click 接口

系统 MUST 提供反馈收集和点击追踪接口。

- `POST /api/items/{item_id}/feedback` — 提交反馈，body: `{goal_id, feedback, block_source?}`
- `GET /r/{item_id}?goal_id=...&channel=...` — 点击追踪 + 302 重定向

#### Scenario: Click Redirect 记录并跳转

```
Given 用户点击推送邮件中的追踪链接
When GET /r/{item_id}?goal_id=...&channel=...
Then 系统 MUST 记录 click_event（item_id, goal_id, channel）
  And MUST 返回 302 重定向到 item 的原始 URL
  And 记录与重定向 MUST 在同一请求中完成
```

### REQ-API-006: Replay / Observability 接口

系统 MUST 提供 Agent 运行记录查询接口。

- `GET /api/agent/runs?goal_id=&cursor=` — 分页查询 Agent 运行记录
- `GET /api/agent/runs/{run_id}` — 单次运行详情（包含 tool_calls + ledger）

#### Scenario: Agent Run 回放

```
Given 用户查询某个 Agent Run 的详情
When GET /api/agent/runs/{run_id}
Then 响应 MUST 包含完整的 agent_run 记录
  And MUST 包含该 run 下所有 tool_calls（按 created_at 排序）
  And MUST 包含该 run 下所有 action_ledger 条目（按 created_at 排序）
```

---

## Performance & Throttling

### REQ-PERF-001: 节流与上限配置

系统 MUST 遵守以下默认节流参数。

| 参数 | 默认值 | 说明 |
|------|--------|------|
| NEWSNOW_FETCH_INTERVAL_SEC | 1800 | NewsNow 抓取间隔（30min） |
| ITEMS_PER_SOURCE_PER_FETCH | 20 | 单源单轮最多 20 条 |
| INGEST_SOURCES_PER_MIN | 60 | 每分钟抓取源上限（30 源很宽裕） |
| EMBED_PER_MIN | 300 | 每分钟 embedding 上限 |
| JUDGE_PER_DAY | 200 | 每日 LLM 判别上限（预算导向） |
| DAILY_USD_BUDGET | 0.33 | 日预算上限（$10/月） |

#### Scenario: NewsNow 源节流

```
Given NEWSNOW_FETCH_INTERVAL_SEC 设为 1800
When 上一次抓取某 NewsNow source 不足 30 分钟
Then Scheduler MUST NOT 再次调度该 source
  And 该 source 的 next_fetch_at MUST 设为 last_fetch_at + 1800s
```

#### Scenario: 单源单轮上限

```
Given ITEMS_PER_SOURCE_PER_FETCH 设为 20
When ingest worker 从某 source 抓取 item
Then 单轮最多处理 20 条 item
  And 超出部分 MUST 被丢弃或延迟到下一轮
```

#### Scenario: 全局 embed 速率限制

```
Given EMBED_PER_MIN 设为 300
When 当前分钟内 embed 请求数达到 300
Then 后续 embed 请求 MUST 被限流（排队等待下一分钟）
  And MUST NOT 因限流导致任务丢失
```

### REQ-PERF-002: NewsNow 30 源全启用可控

约 30 个 NewsNow 源全启用是可行的，通过节流机制保证稳定。

#### Scenario: 30 源并发稳定性

```
Given 系统配置了约 30 个 NewsNow 源且全部 enabled=true
When 所有源按 fetch_interval_sec 正常调度
Then 系统 MUST 保持稳定运行
  And 队列深度 SHOULD 不持续增长
  And 允许长尾源更新不那么实时（稳定性优先）
```

#### Scenario: 源错误退避

```
Given 某 source 连续抓取失败（error_streak 递增）
When error_streak 超过阈值
Then 系统 MUST 自动增大该 source 的 fetch_interval_sec
  And SHOULD 按指数退避策略延长间隔
  And MUST 在恢复正常后重置退避
```

---

## Budget & Degradation

### REQ-BUDGET-001: 日预算熔断

系统 MUST 实现 embedding 和 judge 分开的日预算熔断机制。

#### Scenario: Embedding 超预算熔断

```
Given budget_daily 表记录当日 embedding token 消耗
When 当日 embedding 消耗超过预算阈值
Then 系统 MUST 设置 embedding_disabled=true
  And 新 item 的 embedding_status MUST 标记为 skipped_budget
  And match 阶段 MUST 降级为仅使用 term/recency/source_trust 信号
  And reasons_json MUST 标注"降级"说明
```

#### Scenario: Judge 超预算熔断

```
Given budget_daily 表记录当日 judge token 消耗
When 当日 judge 消耗超过预算阈值
Then 系统 MUST 设置 judge_disabled=true
  And 所有边界样本 MUST NOT 调用 LLM
  And 边界样本 MUST 统一降级为 BATCH 决策
```

#### Scenario: 熔断后系统仍可运行

```
Given embedding_disabled=true 且 judge_disabled=true
When 新 item 持续流入
Then 系统 MUST 仍然正常运行
  And ingest 和 dedupe MUST NOT 受影响
  And match MUST 使用降级评分策略
  And 推送决策 MUST 使用规则（无 LLM）
  And 所有降级行为 MUST 可回放
```

### REQ-BUDGET-002: SMTP 故障降级

#### Scenario: SMTP 故障时站内兜底

```
Given SMTP 服务不可用
When email worker 尝试发送邮件失败
Then 系统 MUST 进行重试（按配置的重试策略）
  And push_decision 的 status MUST 更新为 FAILED
  And 站内 Inbox MUST 仍然可用（push_decisions 不丢）
  And 用户 MUST 能在 Inbox 中查看所有未成功发送的通知
```

### REQ-BUDGET-003: 回滚开关

系统 MUST 提供以下回滚开关用于紧急降级。

| 开关 | 效果 |
|------|------|
| LLM_ENABLED=false | 完全禁用 LLM 调用 |
| IMMEDIATE_ENABLED=false | 仅保留 batch/digest，禁用 immediate |
| EMAIL_ENABLED=false | 仅站内推送，禁用邮件 |

#### Scenario: LLM 开关关闭

```
Given LLM_ENABLED 设为 false
When Agent Runtime 遇到边界样本
Then MUST NOT 调用任何 LLM API
  And 所有边界样本 MUST 降级到 BATCH
  And agent_runs.llm_used MUST 记录为 false
```

#### Scenario: Immediate 开关关闭

```
Given IMMEDIATE_ENABLED 设为 false
When Agent Runtime 判定某 match 为 IMMEDIATE
Then MUST 自动降级为 BATCH
  And push_decision.decision MUST 记录为 BATCH
  And reason_json MUST 说明降级原因
```

#### Scenario: Email 开关关闭

```
Given EMAIL_ENABLED 设为 false
When push_decision 需要发送
Then MUST NOT 尝试 SMTP 发送
  And 通知 MUST 仅通过站内 Inbox 展示
  And push_decision.channel MUST 设为 IN_APP
```

---

## Security & Compliance

### REQ-SEC-001: 外部内容隔离

外部内容（网页/snippet）MUST 永远作为"数据"处理，不得作为指令执行。

#### Scenario: Prompt Injection 防护

```
Given 外部 item 的 title 或 snippet 中包含类似指令的文本
When 该内容传入 LLM 进行判别
Then 系统 MUST 将其作为引用数据传入（非指令区域）
  And LLM 输出 MUST 通过严格 JSON Schema 校验
  And 工具调用 MUST 以只读为主
  And 引用内容 MUST 有长度限制
```

### REQ-SEC-002: LLM 副作用隔离

LLM MUST NOT 直接执行副作用动作。

#### Scenario: LLM 产出必须通过 Runtime 执行

```
Given LLM 作为 Agent Runtime 的推理节点
When LLM 判定需要采取某个动作
Then LLM MUST 仅产出 Action Proposal（结构化描述）
  And 实际执行 MUST 由 Runtime 的 Tools 完成
  And 每个执行 MUST 记录到 action_ledger
```

### REQ-SEC-003: Secrets 管理

secrets（SMTP/OpenAI/DB/Redis 凭证）MUST 仅通过环境变量或 secret 文件注入，不得落库。

#### Scenario: Secrets 不落库

```
Given 系统需要 SMTP/OpenAI/DB/Redis 等凭证
When 配置这些凭证
Then MUST 通过环境变量或 secret 文件提供
  And 数据库中 MUST NOT 存储任何凭证
  And 代码中 MUST NOT 硬编码凭证
```

### REQ-SEC-004: 审计与回放

agent_runs + tool_calls + action_ledger MUST 永久留存（v0）。

#### Scenario: 审计记录完整保留

```
Given v0 阶段所有 Agent 运行记录为审计需要
When agent_runs、agent_tool_calls、agent_action_ledger 中产生记录
Then 这些记录 MUST NOT 被物理删除
  And MUST 支持按 run_id 完整回放
```

### REQ-SEC-005: PII 保护

v0 仅存储 email 作为 PII，日志中 MUST 脱敏。

#### Scenario: 日志中 Email 脱敏

```
Given 系统日志中可能包含用户 email
When 写入日志
Then email MUST 做 hash 或脱敏处理（如 u***@example.com）
  And 原始 email MUST NOT 出现在日志文件中
```

---

## v0 Scope Boundaries

### REQ-SCOPE-001: v0 明确不做

以下功能 v0 MUST NOT 实现。

#### Scenario: 不做详情页抓取

```
Given SITE 类型信息源
When 抓取内容
Then MUST 仅抓取列表页（list-only）
  And MUST NOT 抓取详情页内容
```

#### Scenario: 不做多用户

```
Given v0 为单用户系统
When 任何 API 请求进入
Then 系统 MUST NOT 实现多用户权限隔离
  And MUST NOT 实现团队功能
```

#### Scenario: 不做自动高风险动作

```
Given Agent Runtime 可能识别到需要调整的配置
When Agent 认为需要屏蔽源或修改 Goal
Then Agent MUST NOT 自动执行（仅可"建议"）
  And 建议 MUST 通过 SUGGEST_TUNING action_type 记录
  And 最终执行 MUST 由用户手动确认
```

#### Scenario: 不做全文存储

```
Given v0 存储策略为精简元信息
When 存储 item
Then MUST 仅存储：元信息 + snippet + summary（可选）+ embedding
  And MUST NOT 存储全文内容
```

---

## Delivery & Testing

### REQ-DEL-001: 两周交付计划

v0 MUST 在两周内完成交付。

**Week 1**：底座 + 数据链路
- schema + migrations + pgvector
- sources/items ingest（newsnow/rss/site）+ dedupe
- embedding + match + reasons
- Next.js 基础页（Goals/Sources/Inbox）

**Week 2**：Agent + Push + 闭环
- Agent Runtime（state/tools/ledger）
- Immediate/Batch/Digest + coalesce
- SMTP 发送 + 幂等
- click redirect + feedback
- 预算熔断 + 监控与回放页面

### REQ-DEL-002: 测试策略

#### Scenario: 单元测试覆盖

```
Given 系统核心逻辑需要单测覆盖
When 编写单元测试
Then MUST 覆盖：去重逻辑、阈值桶分类、STRICT/SOFT 规则、合并策略、预算熔断逻辑、JSON Schema 校验
```

#### Scenario: 集成测试端到端

```
Given 系统需要端到端集成测试
When 运行集成测试
Then MUST 覆盖 ingest → push 完整链路
  And LLM 调用 MUST 使用 mock
  And SMTP 发送 MUST 使用 mock
```

#### Scenario: 压测（轻量）验证

```
Given 系统需要在 30 源环境下稳定运行
When 执行 48 小时压测
Then 队列深度 MUST NOT 持续增长
  And 邮件 MUST NOT 重复轰炸同一用户
```

---

## Risk Mitigations

### REQ-RISK-001: 已识别风险与缓解措施

系统 MUST 对以下 Top 10 风险有明确的缓解策略。

| # | 风险 | 缓解措施 |
|---|------|---------|
| 1 | NewsNow 返回波动/异常 | 退避 + 空结果计数（error_streak, empty_streak） |
| 2 | Embedding 成本超标 | 预算熔断 + 降级（REQ-BUDGET-001） |
| 3 | Judge 成本超标 | 边界区间收窄 + 日上限（REQ-BUDGET-001） |
| 4 | SMTP 失败 | 重试 + 站内兜底（REQ-BUDGET-002） |
| 5 | 队列堆积 | 节流 + 并发调优（REQ-PERF-001） |
| 6 | 误报（False Positive） | 阈值上调 + STRICT 引导 |
| 7 | 漏报（False Negative） | Digest 兜底 + 放宽 match 阈值 |
| 8 | Prompt Injection | 工具只读为主 + 严格 schema + 引用限制（REQ-SEC-001） |
| 9 | pgvector 性能瓶颈 | v0 不建 ANN 索引；规模上来再建 HNSW/IVF |
| 10 | 单机宕机 | systemd 守护 + 定期备份 |

#### Scenario: NewsNow 异常退避

```
Given 某 NewsNow source 返回波动或异常
When error_streak 或 empty_streak 超过阈值
Then 系统 MUST 自动增大 fetch_interval_sec（退避）
  And MUST 记录异常到 source 的 error_streak/empty_streak 字段
  And MUST NOT 因单一源异常影响其他源的正常抓取
```

#### Scenario: 误报与漏报平衡

```
Given 系统需要平衡误报和漏报
When 用户报告误报过多
Then 系统 SHOULD 支持上调匹配阈值
  And SHOULD 引导用户使用 STRICT 模式的 priority_terms
When 用户报告漏报过多
Then Digest 汇总 MUST 作为兜底（降低漏报风险）
  And 系统 SHOULD 支持放宽 match 阈值
```
