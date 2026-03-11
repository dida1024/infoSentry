# Source Discovery Agent：信息源智能检索与添加

## 1. 背景与目标

### 1.1 现状问题

当前用户添加信息源的流程是**纯手动**的：

1. 用户需要自行找到目标平台的 RSS feed URL 或网页列表页地址
2. 手动填写完整的源配置（feed_url、CSS selectors 等）
3. 技术门槛高，非技术用户难以使用

这意味着系统已有的三种信息源类型（NEWSNOW、RSS、SITE）虽然覆盖面广，但**发现和配置的成本全部转嫁给了用户**。

### 1.2 目标

新增一个**对话式 Source Discovery Agent**，用户只需用自然语言描述想关注的信息源（如"深圳的政务平台"、"深圳房产相关消息"），Agent 自动：

1. 理解用户意图，制定检索策略
2. 按优先级链搜索候选信息源（内置目录 → 原生 RSS → RSSHub → 网页抓取）
3. 验证候选源的可用性（能连通、有数据）
4. 展示结果，**经用户明确确认后**才添加到系统

### 1.3 用户输入预期

预期用户输入偏**模糊型**：
- "深圳房产相关的消息"
- "国内科技新闻"
- "GitHub 热门项目动态"

对于非常具体的小众需求（如"网易云评论区"），找不到是可接受的，Agent 应如实告知。

---

## 2. 核心流程

```
用户: "我想关注深圳房产相关的消息"
  │
  ▼
┌──────────────────────────────────────────────────────────────┐
│  Source Discovery Agent (Pydantic AI + tool-use loop)         │
│                                                              │
│  Step 1: 意图理解                                             │
│  └─ LLM 解析 → 关键词: 深圳, 房产                              │
│     → 推断平台: 深圳住建局, 深圳房地产信息网, ...                  │
│                                                              │
│  Step 2: 内置目录搜索 (search_catalog)                         │
│  └─ 搜索 NEWSNOW 源库 → 匹配已有源                              │
│                                                              │
│  Step 3: RSS 发现 (probe_rss)                                 │
│  └─ 探测候选 URL 的原生 RSS/Atom feed                           │
│                                                              │
│  Step 4: RSSHub 路由查询 (search_rsshub)                       │
│  └─ 查询 RSSHub 是否有匹配路由                                   │
│                                                              │
│  Step 5: 网页分析 (analyze_site)                               │
│  └─ LLM 分析网页 DOM → 生成 CSS selectors → SITE 类型配置       │
│                                                              │
│  Step 6: 验证 (validate_source)                               │
│  └─ 实际抓取，确认能通且有数据                                    │
│                                                              │
│  Step 7: 展示结果，等待用户确认                                  │
│  └─ 用户同意 → add_source 写入系统                               │
└──────────────────────────────────────────────────────────────┘
```

Agent 自主编排工具调用顺序，并通过 SSE 流式输出思考过程和中间结果。

---

## 3. 架构设计概要

### 3.1 模块归属

新增为 `modules/agent/` 下的子能力，目录结构：

```
src/modules/agent/
├── application/
│   ├── discovery/              # 新增
│   │   ├── agent.py            # Pydantic AI Agent 定义
│   │   ├── tools/              # Agent 工具集
│   │   │   ├── catalog_search.py
│   │   │   ├── rss_probe.py
│   │   │   ├── rsshub_lookup.py
│   │   │   ├── site_analyzer.py
│   │   │   ├── source_validator.py
│   │   │   └── web_search.py
│   │   └── session_service.py  # 会话管理
│   └── ...（现有推送决策 Agent）
├── domain/
│   └── discovery_entities.py   # DiscoverySession, CandidateSource
├── infrastructure/
│   └── discovery/
│       ├── models.py           # DB 模型（会话持久化）
│       └── repositories.py
└── interfaces/
    └── discovery_router.py     # SSE 端点
```

### 3.2 技术选型

| 决策项 | 选择 | 理由 |
|--------|------|------|
| Agent 框架 | Pydantic AI | 轻量，与项目 Pydantic v2 生态契合，原生 streaming |
| 交互方式 | SSE (Server-Sent Events) | 单向流式输出足够，前端轮询用户回复，比 WebSocket 简单 |
| 运行时 | 独立异步进程 | 不占 Celery worker 槽位，长时间运行不阻塞 |
| 会话持久化 | PostgreSQL | 可回溯发现历史，断线恢复 |
| 外部搜索 | Web Search API | Agent tool 调用搜索引擎 |
| RSSHub 查询 | 直接构造路由 + 请求验证 | 最简方案，不维护本地索引 |

### 3.3 与现有系统的交互

```
Discovery Agent
  │
  ├─ 读 ─→ NEWSNOW 源目录 (resources/sources/newsnow_sources_snapshot.json)
  ├─ 读 ─→ 已有 Source 列表 (避免重复添加)
  ├─ 调用 → 现有 Fetcher (RSSFetcher/SiteFetcher) 做验证
  └─ 写 ─→ Source + SourceSubscription (通过现有 SourceService)
```

不引入新的 Celery 队列。Agent 运行在 API 进程内（FastAPI 异步），通过 SSE 端点提供服务。

---

## 4. 影响评估

### 4.1 DDD 模块边界

- **agent 模块**：新增 discovery 子能力，不影响现有推送决策 Agent
- **sources 模块**：复用现有 `SourceService.create_source()`、`FetcherFactory`、`BaseFetcher.validate_config()`，不修改 sources 模块代码
- **跨模块调用**：discovery agent → sources application service（通过 DI 注入，不违反 DDD 方向）

### 4.2 Celery 队列

不涉及。Discovery Agent 在 API 进程的异步事件循环中运行。

### 4.3 推送/交付保障链

不涉及。此功能不触碰 push/items/match 管线。

### 4.4 新增依赖

- `pydantic-ai`：Agent 框架
- 可能需要一个搜索 API 的 SDK（视具体选择的搜索服务而定）

### 4.5 数据库变更

新增表：
- `discovery_sessions`：会话记录（session_id, user_id, status, messages, created_at, updated_at）
- `discovery_candidates`：候选源记录（session_id, source_type, config, validation_result, accepted）

### 4.6 资源影响

- LLM 调用：每次发现会话约 5-15 次 LLM 调用（意图理解 + tool 编排 + 网页分析）
- 网络请求：探测候选 URL、RSSHub 路由，每次会话约 10-30 次 HTTP 请求
- 耗时：单次会话预估 15-60 秒

---

## 5. API 端点

```
POST /api/discovery/sessions          # 创建发现会话
GET  /api/discovery/sessions/{id}/stream  # SSE 流式获取 Agent 输出
POST /api/discovery/sessions/{id}/messages  # 用户发送消息（确认/追问）
GET  /api/discovery/sessions/{id}     # 获取会话详情（含历史消息）
GET  /api/discovery/sessions          # 列出用户的发现会话历史
```

### 交互协议

1. 前端 `POST /sessions` 创建会话，附带用户初始描述
2. 前端 `GET /sessions/{id}/stream` 建立 SSE 连接，接收 Agent 流式输出
3. Agent 需要用户确认时，发送特殊事件（如 `event: confirm_required`）
4. 前端通过 `POST /sessions/{id}/messages` 发送用户回复
5. Agent 收到回复后继续执行，前端继续通过 SSE 接收输出

---

## 6. Agent 工具清单

| 工具 | 类型 | 说明 |
|------|------|------|
| `search_catalog` | 只读 | 搜索内置 NEWSNOW 源目录，语义匹配 |
| `web_search` | 只读 | 调用搜索引擎 API，找目标平台 URL |
| `probe_rss` | 只读 | 探测给定 URL 是否有原生 RSS/Atom feed |
| `search_rsshub` | 只读 | 构造 RSSHub 路由并验证是否可用 |
| `analyze_site` | 只读 | 请求网页 HTML，LLM 分析生成 CSS selectors |
| `validate_source` | 只读 | 用现有 Fetcher 实际抓取，验证能通且有数据 |
| `add_source` | 写入 | 将验证通过的源写入系统（需用户先确认） |

---

## 7. 验收标准

### 7.1 功能

1. 用户输入模糊描述，Agent 能理解意图并搜索候选源
2. 找到的候选源经过实际抓取验证（能通 + 有数据）
3. 用户明确确认后才添加到系统
4. 添加的源能正常被 ingest 调度器抓取
5. 找不到时如实告知用户，说明尝试了什么

### 7.2 体验

1. SSE 流式输出 Agent 思考过程，用户可实时看到进展
2. 单次发现会话在 60 秒内完成（不含等待用户确认的时间）
3. 会话可恢复（刷新页面后重新连接 SSE 可继续）

### 7.3 可靠性

1. Agent 工具调用失败不崩溃，优雅降级到下一个策略
2. 会话状态持久化到 DB，进程重启不丢失
3. 不会添加重复的源（检查已有源列表）

---

## 8. 不做的事（v0 边界）

1. **不做定时自动发现**：仅用户主动发起
2. **不做源质量评估**：只验证"能通有数据"，不评价内容质量
3. **不做批量发现**：每次会话处理一个用户需求
4. **不做源推荐**：不主动向用户推荐源，只响应请求
5. **不做前端 UI**：本提案只覆盖后端 API，前端单独提案

---

## 9. 实施建议

建议拆 3 个 PR：

1. **PR-1：基础设施** — DB 模型、会话管理、SSE 端点骨架
2. **PR-2：Agent 核心** — Pydantic AI Agent 定义、7 个工具实现、tool-use loop
3. **PR-3：集成验证** — 端到端测试、与现有 SourceService 的集成、错误处理完善
