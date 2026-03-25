# Source Discovery Agent — 实施任务

## PR-1: 基础设施（DB + 会话管理 + SSE 端点骨架 + sources 查重扩展）

### Task 1.1: 领域实体定义
- [x] 创建 `src/modules/agent/domain/discovery_entities.py`
  - `SessionStatus`, `MessageRole`, `CandidateStatus` 枚举
  - `DiscoverySession`, `SessionMessage`, `CandidateSource` 数据类
- **检查**: `uv run mypy src/modules/agent/domain/discovery_entities.py`

### Task 1.2: 数据库模型与迁移
- [x] 创建 `src/modules/agent/infrastructure/discovery/models.py`
  - `DiscoverySessionModel` (discovery_sessions 表)
  - `DiscoveryCandidateModel` (discovery_candidates 表)
- [x] 创建 Alembic 迁移: `uv run alembic revision --autogenerate -m "add_discovery_session_tables"`
- [x] 运行迁移: `uv run alembic upgrade head`
- **检查**: `uv run mypy src && uv run alembic upgrade head`

### Task 1.3: Repository 实现
- [x] 创建 `src/modules/agent/infrastructure/discovery/repositories.py`
  - `DiscoverySessionRepository`
    - `create(session) → session`
    - `get_by_id(session_id) → session | None`
    - `update(session) → session`
    - `list_by_user(user_id, page, page_size) → list[session]`
    - `count_active_by_user(user_id) → int` （并发限制用）
  - `DiscoveryCandidateRepository`
    - `create(candidate) → candidate`
    - `update(candidate) → candidate`
    - `list_by_session(session_id) → list[candidate]`
- [x] Domain ↔ Model mapper 函数
- **检查**: `uv run mypy src`

### Task 1.4: Sources 模块查重扩展
- [x] `src/modules/sources/domain/repository.py` — `SourceRepository` 新增抽象方法:
  - `exists_by_config_url(source_type: SourceType, url: str) -> bool`
- [x] `src/modules/sources/infrastructure/repositories.py` — PostgreSQL 实现:
  - RSS: `SELECT 1 FROM sources WHERE type='RSS' AND config->>'feed_url' = :url`
  - SITE: `SELECT 1 FROM sources WHERE type='SITE' AND config->>'list_url' = :url`
  - NEWSNOW: `SELECT 1 FROM sources WHERE type='NEWSNOW' AND config->>'source_id' = :url`
- [x] 单元测试
- **检查**: `uv run mypy src && uv run pytest tests/modules/sources/`

### Task 1.5: 会话管理服务
- [x] 创建 `src/modules/agent/application/discovery/session_service.py`
  - `DiscoverySessionService`
    - `create_session(user_id, query) → session`
      - 检查 `count_active_by_user()` ≤ 1（仅作为应用层前置检查）
    - `get_session(session_id, user_id) → session`
    - `add_user_message(session_id, content) → message`
      - 保存消息到 DB `messages_json`
      - 状态 waiting_user → active
    - `update_status(session_id, status)`
    - `list_sessions(user_id, page, page_size) → list[session]`
    - `expire_stale_sessions()` — 过期清理
- **检查**: `uv run mypy src`

### Task 1.6: Discovery 模块 DI 定义
- [x] 创建 `src/modules/agent/application/discovery/dependencies.py`
  - 声明抽象 repository getter（与项目 DI 模式一致）
- [x] 创建 `src/modules/agent/infrastructure/discovery/dependencies.py`
  - 具体 PostgreSQL 实现
- **检查**: `uv run mypy src`

### Task 1.7: SSE 端点骨架
- [x] 创建 `src/modules/agent/interfaces/discovery_router.py`
  - `POST /discovery/sessions` — 创建会话
  - `GET /discovery/sessions/{id}/stream` — SSE 流（先返回占位事件）
  - `POST /discovery/sessions/{id}/messages` — 用户消息
  - `GET /discovery/sessions/{id}` — 会话详情（含完整 messages_json 用于断线恢复）
  - `GET /discovery/sessions` — 会话列表
- [x] 路由 prefix = `/discovery`，最终挂在 `settings.API_V1_STR` 下 = `/api/v1/discovery/...`
- [x] 请求/响应 Pydantic 模型 (interfaces 层)
- **检查**: `uv run mypy src && uv run pytest`

### Task 1.8: main.py DI 注册
- [x] 在 `main.py` 中新增 discovery 模块的 dependency overrides:
  - `discovery_deps.get_discovery_session_repository` → infra 实现
  - `discovery_deps.get_discovery_candidate_repository` → infra 实现
- [x] 注册 discovery_router 到 api_router
- **检查**: `uv run mypy src && uv run pytest`

### Task 1.9: 配置项
- [x] 在 `src/core/config.py` 新增 Discovery 相关配置
  - `DISCOVERY_SESSION_TTL_SEC: int = 3600`
  - `DISCOVERY_AGENT_MODEL: str = "openai:gpt-4o-mini"`
  - `DISCOVERY_AGENT_MAX_TOOL_CALLS: int = 30`
  - `DISCOVERY_WEB_SEARCH_API_KEY: str = ""`
  - `DISCOVERY_RSSHUB_BASE_URL: str = "https://rsshub.app"`
  - `DISCOVERY_PROBE_TIMEOUT_SEC: float = 10.0`
- [x] 同步更新 `infoSentry-backend/.env.example`
- **检查**: `uv run mypy src`

### Task 1.10: PR-1 单元测试
- [x] 测试 domain 实体的状态转换逻辑
- [x] 测试 repository CRUD 操作
- [x] 测试 session_service 基本流程（含并发限制）
- [x] 测试 SSE 端点返回正确状态码
- [x] 测试 sources `exists_by_config_url()` 查重
- **检查**: `uv run pytest tests/modules/agent/discovery/ && uv run pytest tests/modules/sources/`

---

## PR-2: Agent 核心（Pydantic AI Agent + 7 个工具 + SSE 集成）

> **前提**: `pydantic-ai` 和搜索 SDK 依赖审批通过

### Task 2.1: 添加依赖（需审批）
- [x] `uv add pydantic-ai`
- [x] 搜索 SDK（如 `tavily-python`，视审批决定）
- [x] 确认与现有依赖无冲突
- **检查**: `uv run python -c "import pydantic_ai; print(pydantic_ai.__version__)"`

### Task 2.2: Agent 骨架
- [x] 创建 `src/modules/agent/application/discovery/agent.py`
  - `DiscoveryAgent` 类
  - `DiscoveryDeps` 依赖注入数据类（包含 sources 模块的 handlers + query service + repository）
  - System prompt 定义
  - `run_stream(message_history) → async generator` — 接受对话历史，返回 SSE 事件流
- [x] 创建 `src/modules/agent/application/discovery/tools/__init__.py`
- **检查**: `uv run mypy src/modules/agent/application/discovery/`

### Task 2.3: Tool — search_catalog
- [x] 创建 `src/modules/agent/application/discovery/tools/catalog_search.py`
  - 从 `NewsNowCatalogProvider` 加载目录
  - 关键词模糊匹配 name/title
  - 通过 `SourceQueryService` 检查已有源标记重复
  - 返回最多 10 条匹配
- [x] 单元测试 (mock catalog data)
- **检查**: `uv run mypy src && uv run pytest tests/modules/agent/discovery/test_catalog_search.py`

### Task 2.4: Tool — web_search
- [x] 创建 `src/modules/agent/application/discovery/tools/web_search.py`
  - 搜索引擎 API 调用封装
  - 支持可配置的提供商，而不是写死单一实现
  - 返回最多 5 条结果
- [x] 搜索服务不可用时的降级处理（返回空结果 + 日志）
- [x] 单元测试 (mock API response)
- **检查**: `uv run mypy src && uv run pytest tests/modules/agent/discovery/test_web_search.py`

### Task 2.5: Tool — probe_rss
- [x] 创建 `src/modules/agent/application/discovery/tools/rss_probe.py`
  - 初始 URL SSRF 校验
  - redirect-safe 校验：禁止未校验的重定向目标
  - HTML `<link rel="alternate">` 检测
  - 常见路径探测: `/rss`, `/feed`, `/atom.xml`, `/rss.xml`, `/feed.xml`
  - feedparser 验证
- [x] 单元测试补充 redirect 到私网/保留地址的回归用例
- **检查**: `uv run mypy src && uv run pytest tests/modules/agent/discovery/test_rss_probe.py`

### Task 2.6: Tool — search_rsshub
- [x] 创建 `src/modules/agent/application/discovery/tools/rsshub_lookup.py`
  - 根据关键词 + 域名构造候选路由
  - 请求 RSSHub 实例验证，并校验所有重定向目标
  - feedparser 解析验证
- [x] 单元测试补充 redirect-safe 回归用例
- **检查**: `uv run mypy src && uv run pytest tests/modules/agent/discovery/test_rsshub_lookup.py`

### Task 2.7: Tool — fetch_site_html
- [x] 创建 `src/modules/agent/application/discovery/tools/site_html_fetcher.py`
  - 初始 URL SSRF 校验
  - redirect-safe 校验：禁止未校验的重定向目标
  - 获取 HTML，清理 script/style/nav/footer
  - 截取关键 DOM 结构（控制在 ~2000 token）
  - **只返回简化 HTML**，不做分析（Agent 的 LLM 能力负责从 HTML 推断 CSS selectors）
- [x] 单元测试补充 redirect 到私网/保留地址的回归用例
- **检查**: `uv run mypy src && uv run pytest tests/modules/agent/discovery/test_site_html_fetcher.py`

### Task 2.7a: Candidate 持久化生命周期
- [x] 在候选被发现时创建 `CandidateSource(status=DISCOVERED)`
- [x] 在验证开始时更新为 `VALIDATING`
- [x] 在验证结束时更新为 `VALID` / `INVALID` 并记录 `validation_result`
- [x] 在用户确认成功添加后更新为 `ACCEPTED` 并写入 `source_id`
- [x] 在用户明确拒绝时更新为 `REJECTED`
- [x] 补充单元测试与断线恢复测试，验证 `GET /sessions/{id}` 可返回完整 candidate 状态
- **检查**: `uv run mypy src && uv run pytest tests/unit/test_discovery_integration.py`

### Task 2.8: Tool — validate_source
- [x] 创建 `src/modules/agent/application/discovery/tools/source_validator.py`
  - 调用 `FetcherFactory.create()` + `validate_config()` + `fetch()`
  - 返回验证结果: valid, status, items_count, sample_titles
- [x] 单元测试 (mock fetcher)
- **检查**: `uv run mypy src && uv run pytest tests/modules/agent/discovery/test_source_validator.py`

### Task 2.9: Tool — add_source
- [x] 创建 `src/modules/agent/application/discovery/tools/source_adder.py`
  - 前置检查: session 状态 == waiting_user，且存在显式确认动作或明确的确认目标
  - 查重: `source_repository.exists_by_name()` + `source_repository.exists_by_config_url()`
  - 构造 `CreateSourceCommand`，调用 `create_source_handler.handle()`
  - 构造 `SubscribeSourceCommand`，调用 `subscribe_source_handler.handle()`
  - 更新 `CandidateSource.status → accepted`，记录 `source_id`
- [x] 定义并实现事务或补偿语义：source 创建成功但订阅失败时不得返回整体成功
- [x] 单元测试补充 partial failure / rollback / compensation 场景
- **检查**: `uv run mypy src && uv run pytest tests/modules/agent/discovery/test_source_adder.py`

### Task 2.10: SSE 流式集成
- [x] 将 `DiscoveryAgent.run_stream(message_history)` 输出接入 SSE 端点
  - agent_message 事件: Agent 文本输出
  - tool_call / tool_result 事件: 工具调用中间状态
  - confirm_required 事件: 由显式业务事件驱动 → session 状态 → waiting_user → SSE 关闭
  - session_completed 事件: 仅在显式业务动作完成后触发
  - error 事件: 错误
- [x] 用户消息路由: `POST /messages` → 保存到 DB → 状态 active → 客户端重连 SSE
- [x] 断线恢复: `GET /sessions/{id}` 返回完整对话历史和 candidate 状态，前端渲染后按 status 决定下一步
- [x] 每个 turn 结束时将对话历史写入 DB `messages_json`
- [x] 移除基于自然语言关键词推断 waiting_user/completed 的实现
- **检查**: `uv run mypy src && uv run pytest`

---

## PR-3: 集成验证与完善

### Task 3.1: 端到端集成测试
- [x] 测试完整流程: 创建会话 → SSE 接收 → 用户确认 → 源添加
- [x] 测试找不到源的场景: Agent 如实告知
- [x] 测试会话过期清理
- [x] 测试并发限制（每用户 1 个活跃会话）
- [x] 测试断线恢复: 关闭 SSE → `GET /sessions/{id}` → 重新 `GET /stream`
- [x] 测试已有源查重（名称 + URL 双重检查）
- [x] 测试 candidate 发现/验证/接受/拒绝的持久化恢复
- **检查**: `uv run pytest tests/unit/test_discovery_integration.py`

### Task 3.2: 错误处理完善
- [x] 外部服务不可用时的降级路径
- [x] LLM 调用失败重试（1 次）
- [x] 工具调用次数上限（DISCOVERY_AGENT_MAX_TOOL_CALLS）
- [x] SSE 连接异常断开时 asyncio.Task 清理
- **检查**: `uv run pytest`

### Task 3.3: 安全加固
- [x] redirect-safe SSRF 校验覆盖所有 URL 探测路径（probe_rss, search_rsshub, fetch_site_html）
- [x] 速率限制: 每用户同时 1 个活跃会话（增加数据库级或等价强约束，而不只是 session_service 检查）
- [x] HTML 清理: fetch_site_html 的 sanitization 验证
- [x] add_source 的用户确认状态强校验
- **检查**: `uv run pytest && uv run mypy src`

### Task 3.4: 日志与可观测性
- [x] structlog 结构化日志
  - 字段: session_id, user_id, tool_name, duration_ms
- [x] Agent 工具调用计数与耗时统计
- [ ] 发现成功率指标（找到 / 总会话）
- **检查**: `uv run mypy src`

### Task 3.5: 全量检查
- [x] `uv run pytest` — 全部测试通过 (354 passed)
- [x] `uv run mypy src` — 类型检查通过 (discovery module 0 errors)
- [x] `uv run ruff check src` — 代码风格通过
- [ ] 手动测试: 至少 3 个不同类型的发现场景
  - 内置目录命中（如 "GitHub 动态"）
  - RSS/RSSHub 命中（如 "某政府公告"）
  - 找不到的场景（如 "网易云评论区"）
