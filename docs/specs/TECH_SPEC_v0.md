# infoSentry Tech Spec v0（MVP）

版本：v0.3  
日期：2025-12-28  
部署：单机 VM（2c4g）  
默认时区：Asia/Shanghai（v0 固定；v1 支持可配）  
信息源：NewsNow（约 30 个 source，全启用）+ RSS + SITE（list-only）  
推送：站内 + Email（SMTP）  
AI：OpenAI API 协议（embedding + 边界判别；便宜小模型 + 不确定升级）  
预算：LLM 月成本 ≤ $10（单人）

---

## 1. 结论摘要（建议怎么做、为什么）

1) v0 采用 **模块化单体 + 队列隔离**，不做微服务：单人、2c4g、两周交付下 ROI 最优。  
2) AI 层落为 **决策型 Agent Runtime**：不是"调用 LLM 分析"，而是有 state/tools/ledger 的可回放行动系统；LLM 仅是其中一个推理节点。  
3) NewsNow 约 30 源 **全启用**可行：通过"抓取节流 + 每源拉取上限 + 预算熔断"保证单机稳定。  
4) embedding 必做：用 pgvector 存向量，match_score = 语义相似度 + term 命中 + recency + source_trust（可解释 reasons）。  
5) "超高价值"判定：规则守门（STRICT / blocked / negative）优先；边界才 LLM 判别，输出必须 **解释 + 引用证据**，失败保守降级到 Batch/Digest。  
6) 成本护栏：日预算熔断（embedding/judge 分开）；命中熔断后系统仍可运行（降级策略明确、可回放）。

---

## 2. 目标与范围（v0）

### 2.1 v0 目标
- 闭环跑通：Ingest → Dedupe → Embed → Match → Agent Decide → Notify → Click/Feedback → 收敛
- 三层推送：Immediate（事件触发+合并）/ Batch（窗口）/ Digest（每日）
- Agent 可控：结构化输入输出、记录 run、可回放、可降级

### 2.2 v0 明确不做
- SITE 抓详情页（v0 list-only）
- 多用户/团队权限
- 自动执行高风险动作（例如自动屏蔽源/自动改 Goal，仅可"建议"）
- 全文存储（仅元信息 + snippet + summary（可选） + embedding）

---

## 3. 系统架构（模块划分 + 数据流）

### 3.1 模块划分
- Web：Next.js（极简配置/查看/反馈）
- API：FastAPI（Auth/CRUD/查询/回放）
- Workers：Celery（按队列拆容器）
  - ingest（newsnow/rss/site）
  - embed
  - match
  - agent
  - email
- Scheduler：Celery Beat（Batch windows & Digest tick）
- Storage：PostgreSQL + pgvector、Redis
- SMTP：邮件发送

### 3.2 数据流（ASCII）

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

---

## 4. 关键技术决策（ADR）

### ADR-001：架构形态（模块化单体 + 队列隔离，不做微服务）
- 原因：单人、两周交付、单机部署；微服务治理成本高于收益
- 退出条件：多用户/高吞吐/多团队并行时再拆服务

### ADR-002：Agent 实现策略（v0 不引入编排框架，v1 可引入）
- v0：自研轻量 Agent Runtime（state + tools + ledger），将流程拆成 nodes（可迁移）
- v1：若引入 LangGraph 等框架，只替换编排层 wiring，nodes/tools 不重写

### ADR-003：NewsNow 约 30 源全启用（可控）
- 采用每源拉取上限、全局节流、错误退避
- 单机 2c4g 目标：稳定性优先，允许长尾源更新不那么实时

### ADR-004：存储与向量
- PostgreSQL 为主库
- pgvector 存 embedding，match 侧优先 DB 计算相似度（便于调试、简化架构）

### ADR-005：LLM 调用策略（便宜小模型 + 不确定升级）
- 边界样本才调用
- 输出强制 JSON Schema（失败 fallback）
- 超预算熔断：禁用 judge，边界全降级 Batch

---

## 5. 核心数据模型（PostgreSQL + pgvector）

> 主键/索引/幂等键是 v0 稳定性核心

### 5.1 表清单（核心）
- users
- auth_magic_links（一次性 token）
- sessions（可选，或 JWT）
- sources
- items
- goals
- goal_push_configs
- goal_priority_terms
- goal_item_matches
- push_decisions
- agent_runs（增强）
- agent_tool_calls（新增）
- agent_action_ledger（新增）
- click_events
- item_feedback
- blocked_sources
- budget_daily（建议）

### 5.2 关键表（字段要点）

#### sources
- id (uuid pk)
- type: NEWSNOW|RSS|SITE
- name
- enabled bool (v0: 默认 true)
- fetch_interval_sec int
- next_fetch_at timestamptz (index)
- last_fetch_at timestamptz
- error_streak int, empty_streak int
- config jsonb
  - NEWSNOW: {base_url, source_id}
  - RSS: {feed_url}
  - SITE: {list_url, selectors...}

索引：
- (enabled, next_fetch_at)
- (type, enabled)

#### items
- id uuid pk
- source_id fk
- url text
- url_hash text unique
- title text
- snippet text
- published_at timestamptz
- ingested_at timestamptz
- embedding vector(...)
- embedding_status: pending|done|skipped_budget
- embedding_model text

索引：
- unique(url_hash)
- (published_at desc)
- (source_id, published_at desc)

#### goal_item_matches
- goal_id fk
- item_id fk
- match_score float
- features_json jsonb
- reasons_json jsonb
- computed_at timestamptz

PK: (goal_id, item_id)
Index: (goal_id, match_score desc, computed_at desc)

#### push_decisions
- id uuid pk
- goal_id, item_id
- decision: IMMEDIATE|BATCH|DIGEST|IGNORE
- status: PENDING|SENT|FAILED|SKIPPED
- channel: EMAIL|IN_APP
- reason_json jsonb (必须含 evidence)
- decided_at, sent_at
- dedupe_key text unique (goal+item+decision)

#### agent_runs（增强）
- id uuid pk (run_id)
- trigger: MatchComputed|BatchWindowTick|DigestTick
- goal_id
- status: SUCCESS|TIMEOUT|ERROR|FALLBACK
- plan_json jsonb (可选)
- input_snapshot_json jsonb (脱敏)
- output_snapshot_json jsonb
- final_actions_json jsonb
- budget_snapshot_json jsonb
- llm_used bool, model_name text
- latency_ms int
- created_at timestamptz

#### agent_tool_calls（新增）
- id uuid pk
- run_id fk
- tool_name text
- input_json jsonb
- output_json jsonb
- status: SUCCESS|ERROR
- latency_ms int
- created_at timestamptz

Index: (run_id, created_at)

#### agent_action_ledger（新增，不可变）
- id uuid pk
- run_id fk
- action_type: EMIT_DECISION|ENQUEUE_EMAIL|SUGGEST_TUNING
- payload_json jsonb
- created_at timestamptz

Index: (run_id, created_at)

#### budget_daily（建议）
- date (pk)
- embedding_tokens_est int
- judge_tokens_est int
- usd_est float
- embedding_disabled bool
- judge_disabled bool

---

## 6. 核心接口设计（REST）

### 6.1 Auth
- POST /api/auth/request_link  {email}
- GET  /api/auth/consume?token=...

### 6.2 Goals
- GET  /api/goals
- POST /api/goals
- GET  /api/goals/{id}
- PUT  /api/goals/{id}
- POST /api/goals/{id}/pause | /resume

### 6.3 Sources
- GET  /api/sources?type=
- POST /api/sources
- PUT  /api/sources/{id}
- POST /api/sources/{id}/enable | /disable

### 6.4 Notifications / Inbox
- GET /api/notifications?goal_id=&cursor=
返回必须包含：
- decision/status
- reason_json（含 evidence: source/url/published_at/matched_terms/snippet_quote）
- actions（例如 open url / like / block）

### 6.5 Feedback & Click
- POST /api/items/{item_id}/feedback {goal_id, feedback, block_source?}
- GET  /r/{item_id}?goal_id=...&channel=...  -> 记录 click_events 并 302

### 6.6 Replay / Observability
- GET /api/agent/runs?goal_id=&cursor=
- GET /api/agent/runs/{run_id} （包含 tool_calls + ledger）

---

## 7. 性能与扩展（2c4g 单机默认配置）

### 7.1 队列拆分（Celery）
- q_ingest
- q_embed
- q_match
- q_agent
- q_email

### 7.2 推荐并发（2c4g）
- worker_ingest: concurrency=2
- worker_embed_match: concurrency=1（或拆成 embed=1, match=1）
- worker_agent: concurrency=1
- worker_email: concurrency=1
- api: uvicorn workers=1~2（根据 CPU）

### 7.3 节流与上限（默认）
- NEWSNOW_FETCH_INTERVAL_SEC=1800（30min）
- ITEMS_PER_SOURCE_PER_FETCH=20（单源单轮最多 20 条）
- INGEST_SOURCES_PER_MIN=60（上限；30 源很宽裕）
- EMBED_PER_MIN=300（上限）
- JUDGE_PER_DAY=200（上限，预算导向）
- DAILY_USD_BUDGET=0.33（$10/月）

### 7.4 降级策略
- embedding 超预算：embedding_disabled=true，新 item 标记 skipped_budget，match 降级为 term/recency/source_trust（reasons 标注降级）
- judge 超预算：judge_disabled=true，边界样本不调用 LLM，统一 BATCH
- SMTP 故障：email worker 重试 + 站内 Inbox 仍可用（push_decisions 不丢）

---

## 8. 安全与合规

- 外部内容（网页/snippet）永远作为"数据"，不作为指令执行
- LLM 不允许直接执行副作用动作：只能产出 Action Proposal；执行由 Runtime 工具完成
- secrets（SMTP/OpenAI/DB/Redis）仅环境变量或 secret 文件，不落库
- 审计与回放：agent_runs + tool_calls + action_ledger 永久留存（v0）
- PII：v0 仅 email；日志中对 email 做 hash 或脱敏

---

## 9. 交付计划（两周上线）

Week 1：底座 + 数据链路
- schema + migrations + pgvector
- sources/items ingest（newsnow/rss/site）+ dedupe
- embedding + match + reasons
- Next.js 基础页（Goals/Sources/Inbox）

Week 2：Agent + Push + 闭环
- Agent Runtime（state/tools/ledger）
- Immediate/Batch/Digest + coalesce
- SMTP 发送 + 幂等
- click redirect + feedback
- 预算熔断 + 监控与回放页面

---

## 10. 测试策略

- 单测：去重、阈值桶、STRICT/SOFT、合并策略、预算熔断、schema 校验
- 集成：端到端（ingest→push）+ LLM/SMTP mock
- 压测（轻量）：30 源跑 48h，队列不增长；邮件不重复轰炸
- 回滚：
  - LLM_ENABLED=false
  - IMMEDIATE_ENABLED=false（仅 batch/digest）
  - EMAIL_ENABLED=false（仅站内）

---

## 11. 风险清单（Top 10）
1) NewsNow 返回波动/异常：退避 + 空结果计数
2) embedding 成本超标：预算熔断 + 降级
3) judge 成本超标：边界区间收窄 + 日上限
4) SMTP 失败：重试 + 站内兜底
5) 队列堆积：节流 + 并发调优
6) 误报：阈值上调 + STRICT 引导
7) 漏报：digest 兜底 + 放宽 match
8) prompt injection：工具只读为主 + 严格 schema + 引用限制
9) pgvector 性能：v0 不建 ANN；规模上来再建 HNSW/IVF
10) 单机宕机：systemd 守护 + 定期备份

