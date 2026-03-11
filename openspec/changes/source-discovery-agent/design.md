# Source Discovery Agent — 技术设计

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                      │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Discovery Chat UI                                     │  │
│  │  POST /sessions → GET /stream (SSE) → POST /messages  │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP + SSE
┌──────────────────────────▼───────────────────────────────────┐
│                    API (FastAPI)                              │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  discovery_router.py                                    │ │
│  │  • POST /api/discovery/sessions                         │ │
│  │  • GET  /api/discovery/sessions/{id}/stream   (SSE)     │ │
│  │  • POST /api/discovery/sessions/{id}/messages           │ │
│  │  • GET  /api/discovery/sessions/{id}                    │ │
│  │  • GET  /api/discovery/sessions                         │ │
│  └────────────────────────┬────────────────────────────────┘ │
│                           │                                  │
│  ┌────────────────────────▼────────────────────────────────┐ │
│  │  DiscoverySessionService (application)                  │ │
│  │  • 会话生命周期管理                                       │ │
│  │  • 启动/恢复 Agent 运行                                  │ │
│  │  • 消息路由                                              │ │
│  └────────────────────────┬────────────────────────────────┘ │
│                           │                                  │
│  ┌────────────────────────▼────────────────────────────────┐ │
│  │  DiscoveryAgent (Pydantic AI)                           │ │
│  │  • System prompt + tool definitions                     │ │
│  │  • run_stream() → SSE events                            │ │
│  │  • Tools: search_catalog, web_search, probe_rss,        │ │
│  │    search_rsshub, analyze_site, validate_source,        │ │
│  │    add_source                                           │ │
│  └─────────┬──────────┬──────────┬─────────────────────────┘ │
│            │          │          │                            │
│       ┌────▼───┐ ┌───▼────┐ ┌──▼──────┐                     │
│       │Catalog │ │Fetcher │ │ Source  │                      │
│       │Provider│ │Factory │ │Service  │                      │
│       └────────┘ └────────┘ └─────────┘                      │
│       (sources)  (sources)   (sources)                       │
└──────────────────────────────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │ PostgreSQL  │
                    │ • sessions  │
                    │ • candidates│
                    └─────────────┘
```

---

## 2. 领域模型 (domain layer)

**文件**: `src/modules/agent/domain/discovery_entities.py`

### 2.1 DiscoverySession

```python
class SessionStatus(str, Enum):
    ACTIVE = "active"              # Agent 运行中
    WAITING_USER = "waiting_user"  # 等待用户确认
    COMPLETED = "completed"        # 完成
    FAILED = "failed"              # 失败
    EXPIRED = "expired"            # 超时过期

@dataclass
class DiscoverySession:
    id: str                        # UUID
    user_id: str
    status: SessionStatus
    initial_query: str             # 用户初始描述
    messages: list[SessionMessage] # 完整对话历史
    candidates: list[CandidateSource]
    created_at: datetime
    updated_at: datetime
    expires_at: datetime           # 会话过期时间（如 1 小时）
```

### 2.2 SessionMessage

```python
class MessageRole(str, Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"

@dataclass
class SessionMessage:
    role: MessageRole
    content: str
    timestamp: datetime
    metadata: dict[str, Any] | None = None  # tool_calls, confirm_request 等
```

### 2.3 CandidateSource

```python
class CandidateStatus(str, Enum):
    DISCOVERED = "discovered"      # 发现但未验证
    VALIDATING = "validating"      # 验证中
    VALID = "valid"                # 验证通过
    INVALID = "invalid"            # 验证失败
    ACCEPTED = "accepted"          # 用户已确认，已添加
    REJECTED = "rejected"          # 用户拒绝

@dataclass
class CandidateSource:
    id: str                        # UUID
    source_type: SourceType        # NEWSNOW / RSS / SITE
    name: str                      # 源名称（人类可读）
    url: str                       # 主 URL
    config: dict[str, Any]         # 完整的源配置
    status: CandidateStatus
    validation_result: dict[str, Any] | None  # 验证结果快照
    discovered_via: str            # 发现渠道: catalog/rss_probe/rsshub/site_analysis
    source_id: str | None          # 添加后的 Source ID
```

---

## 3. 数据库模型 (infrastructure layer)

**文件**: `src/modules/agent/infrastructure/discovery/models.py`

### 3.1 discovery_sessions 表

| 列 | 类型 | 说明 |
|---|---|---|
| id | VARCHAR(36) PK | UUID |
| user_id | VARCHAR(36) FK | 关联 users |
| status | VARCHAR(20) | active/waiting_user/completed/failed/expired |
| initial_query | TEXT | 用户初始描述 |
| messages_json | JSONB | 完整对话历史 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |
| expires_at | TIMESTAMPTZ | 过期时间 |

索引：
- `(user_id, created_at DESC)` — 用户会话列表

### 3.2 discovery_candidates 表

| 列 | 类型 | 说明 |
|---|---|---|
| id | VARCHAR(36) PK | UUID |
| session_id | VARCHAR(36) FK | 关联 session |
| source_type | VARCHAR(20) | NEWSNOW/RSS/SITE |
| name | VARCHAR(255) | 源名称 |
| url | TEXT | 主 URL |
| config_json | JSONB | 源配置 |
| status | VARCHAR(20) | discovered/valid/accepted/... |
| validation_result_json | JSONB | 验证快照 |
| discovered_via | VARCHAR(30) | 发现渠道 |
| source_id | VARCHAR(36) | 添加后的 Source ID |
| created_at | TIMESTAMPTZ | |

索引：
- `(session_id)` — 会话下的候选列表

---

## 4. Agent 设计 (application layer)

**文件**: `src/modules/agent/application/discovery/agent.py`

### 4.1 Pydantic AI Agent 定义

```python
from pydantic_ai import Agent

discovery_agent = Agent(
    model="openai:gpt-4o-mini",  # 够用且便宜
    system_prompt=DISCOVERY_SYSTEM_PROMPT,
    tools=[
        search_catalog,
        web_search,
        probe_rss,
        search_rsshub,
        analyze_site,
        validate_source,
        add_source,
    ],
)
```

### 4.2 System Prompt 要点

```
你是信息源发现助手。用户会描述想关注的信息，你需要帮他们找到合适的信息源。

工作流程：
1. 理解用户意图，推断可能的平台或网站
2. 按优先级搜索：内置目录 → 原生 RSS → RSSHub → 网页抓取
3. 找到候选后，验证其可用性
4. 展示结果，等待用户确认后才添加

规则：
- 每个候选源必须经过 validate_source 验证
- 未经用户明确同意，不得调用 add_source
- 如果所有策略都找不到可靠源，如实告知用户
- 用中文和用户交流
- 简洁地汇报进展，不要啰嗦
```

### 4.3 Tool 运行时依赖注入

Pydantic AI 支持通过 `deps` 参数注入运行时依赖：

```python
@dataclass
class DiscoveryDeps:
    catalog_provider: NewsNowCatalogProvider
    fetcher_factory: FetcherFactory
    source_service: SourceService
    http_client: httpx.AsyncClient
    session: DiscoverySession
    rsshub_base_url: str
```

每个 tool 通过 `RunContext[DiscoveryDeps]` 访问这些依赖，保持 DDD 层次。

---

## 5. 工具详细设计

### 5.1 search_catalog

**输入**: `keywords: list[str]`
**逻辑**:
1. 从 `NewsNowCatalogProvider` 加载全量目录
2. 用关键词模糊匹配 `name` 和 `title` 字段
3. 同时检查系统已有 Source 列表，标记"已存在"的
4. 返回匹配结果（最多 10 条）

**输出**: 匹配的源列表 `[{source_id, name, title, already_exists}]`

### 5.2 web_search

**输入**: `query: str`
**逻辑**:
1. 调用搜索引擎 API（如 Tavily/Exa）
2. 返回搜索结果摘要（URL + 标题 + 描述）

**输出**: 搜索结果 `[{url, title, snippet}]`（最多 5 条）

### 5.3 probe_rss

**输入**: `url: str`
**逻辑**:
1. SSRF 校验 URL（复用现有 `_is_allowed_url`）
2. GET 请求目标 URL
3. 检查 HTML 中的 `<link rel="alternate" type="application/rss+xml">`
4. 尝试常见 RSS 路径：`/rss`, `/feed`, `/atom.xml`, `/rss.xml`, `/feed.xml`
5. 对找到的 URL 尝试 feedparser 解析验证

**输出**: `{found: bool, feed_urls: [{url, title, format}]}`

### 5.4 search_rsshub

**输入**: `keywords: list[str], domain: str | None`
**逻辑**:
1. 根据关键词和域名构造可能的 RSSHub 路由
2. 直接请求 `{RSSHUB_BASE_URL}/{route}` 验证
3. 构造策略：
   - 域名转路由：`gov.cn/shenzhen` → `/gov/shenzhen`
   - 常见模式：`/government/shenzhen`, `/cn/shenzhen/gov`
4. 对有响应的路由用 feedparser 验证

**输出**: `{found: bool, routes: [{route, title, item_count}]}`

### 5.5 analyze_site

**输入**: `url: str`
**逻辑**:
1. SSRF 校验
2. GET 请求目标 URL
3. 提取 HTML 结构（清理 script/style，保留列表区域）
4. 用 LLM（Agent 自身）分析 DOM 结构，生成 CSS selectors：
   - `item`: 列表项容器
   - `title`: 标题元素
   - `link`: 链接元素
   - `snippet`: 摘要元素（可选）
   - `time`: 时间元素（可选）
5. 返回生成的 SITE 类型配置

**输出**: `{list_url, selectors: {item, title, link, snippet?, time?}}`

**注意**: 这个工具可靠性最低，Agent 应在其他策略都失败时才使用。

### 5.6 validate_source

**输入**: `source_type: str, config: dict`
**逻辑**:
1. 调用 `FetcherFactory.create(source_type, config)`
2. 调用 `fetcher.validate_config()` 验证配置格式
3. 调用 `fetcher.fetch()` 实际抓取
4. 检查 FetchResult：status 为 SUCCESS/PARTIAL 且 items 非空

**输出**: `{valid: bool, status, items_count, sample_titles: [str], error?: str}`

### 5.7 add_source

**输入**: `name: str, source_type: str, config: dict`
**逻辑**:
1. **前置检查**：当前 session 状态必须为 `waiting_user` 且用户最近消息是确认
2. 检查源名称/URL 是否已存在（避免重复）
3. 调用 `SourceService.create_source()` 创建源
4. 调用 `SourceService.subscribe()` 为用户创建订阅
5. 更新 CandidateSource 状态为 `accepted`，记录 `source_id`

**输出**: `{success: bool, source_id, error?: str}`

---

## 6. SSE 流式协议

### 6.1 事件类型

```
event: agent_message
data: {"content": "让我帮你搜索一下深圳房产相关的信息源..."}

event: tool_call
data: {"tool": "search_catalog", "args": {"keywords": ["深圳", "房产"]}}

event: tool_result
data: {"tool": "search_catalog", "summary": "在内置目录中未找到直接匹配"}

event: agent_message
data: {"content": "内置目录没有直接匹配，让我搜索一下相关平台..."}

event: candidates_found
data: {"candidates": [{"name": "深圳住建局", "type": "RSS", "url": "...", "items_count": 15}]}

event: confirm_required
data: {"message": "找到以上候选源，要添加到你的信息源吗？", "candidates": [...]}

event: session_completed
data: {"added_sources": [{"name": "...", "source_id": "..."}]}

event: error
data: {"message": "搜索过程中出现错误", "recoverable": true}
```

### 6.2 用户消息格式

```json
POST /api/discovery/sessions/{id}/messages
{
    "content": "好的，加上第一个",
    "type": "text"
}
```

### 6.3 断线恢复

1. 前端断线后重新连接 SSE
2. 服务端检查 session 状态：
   - `active`：恢复 Agent 运行（从上次中断点继续不现实，重新运行最后一步）
   - `waiting_user`：重新发送 `confirm_required` 事件
   - `completed/failed`：发送最终状态

---

## 7. DDD 层次分配

| 变更 | 层 | 说明 |
|------|----|------|
| DiscoverySession, CandidateSource | domain | 纯数据实体，无外部依赖 |
| DiscoverySessionService | application | 会话生命周期、Agent 启动编排 |
| DiscoveryAgent + Tools | application | 业务逻辑编排，通过 deps 注入基础设施 |
| DiscoverySessionModel, DiscoverySessionRepository | infrastructure | DB 持久化 |
| discovery_router | interfaces | HTTP/SSE 端点，参数校验，DI 注入 |

跨模块依赖方向：
```
agent.interfaces → agent.application → agent.domain
                         ↓ (DI 注入)
                   sources.application (SourceService, CatalogProvider, FetcherFactory)
```

---

## 8. 配置项

新增到 `core/config.py`：

```python
# Discovery Agent
DISCOVERY_SESSION_TTL_SEC: int = 3600          # 会话过期时间 1 小时
DISCOVERY_AGENT_MODEL: str = "openai:gpt-4o-mini"
DISCOVERY_AGENT_MAX_TOOL_CALLS: int = 30       # 单次会话最大工具调用
DISCOVERY_WEB_SEARCH_PROVIDER: str = "tavily"  # 搜索引擎提供商
DISCOVERY_WEB_SEARCH_API_KEY: str = ""
DISCOVERY_RSSHUB_BASE_URL: str = "https://rsshub.app"
DISCOVERY_PROBE_TIMEOUT_SEC: float = 10.0      # RSS/SITE 探测超时
```

---

## 9. 错误处理与降级

| 场景 | 处理 |
|------|------|
| 搜索引擎 API 不可用 | 跳过 web_search，仅用 catalog + 用户提供的 URL |
| RSSHub 实例不可达 | 跳过 rsshub 策略，继续 probe_rss / analyze_site |
| 单个候选源验证超时 | 标记 INVALID，继续验证其他候选 |
| LLM 调用失败 | 重试 1 次，仍失败则会话标记 FAILED |
| 会话过期 | 标记 EXPIRED，前端提示重新开始 |
| 工具调用超过上限 | 终止 Agent，返回当前已发现的结果 |

---

## 10. 安全考虑

1. **SSRF 防护**：所有 URL 探测复用现有 `_is_allowed_url()` 校验（禁止 localhost、私有 IP、link-local）
2. **用户确认**：add_source 工具强制要求 session 处于 `waiting_user` 状态
3. **速率限制**：每用户同时只能有 1 个活跃 discovery session
4. **预算控制**：单次会话 LLM 调用上限 30 次
5. **HTML 清理**：analyze_site 抓取的 HTML 在传给 LLM 前先清理 script/style
