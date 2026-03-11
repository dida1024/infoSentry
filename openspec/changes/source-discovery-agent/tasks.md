# Source Discovery Agent — 实施任务

## PR-1: 基础设施（DB + 会话管理 + SSE 端点骨架）

### Task 1.1: 领域实体定义
- [ ] 创建 `src/modules/agent/domain/discovery_entities.py`
  - `SessionStatus`, `MessageRole`, `CandidateStatus` 枚举
  - `DiscoverySession`, `SessionMessage`, `CandidateSource` 数据类
- **检查**: `uv run mypy src/modules/agent/domain/discovery_entities.py`

### Task 1.2: 数据库模型与迁移
- [ ] 创建 `src/modules/agent/infrastructure/discovery/models.py`
  - `DiscoverySessionModel` (discovery_sessions 表)
  - `DiscoveryCandidateModel` (discovery_candidates 表)
- [ ] 创建 Alembic 迁移: `uv run alembic revision --autogenerate -m "add_discovery_session_tables"`
- [ ] 运行迁移: `uv run alembic upgrade head`
- **检查**: `uv run mypy src && uv run alembic upgrade head`

### Task 1.3: Repository 实现
- [ ] 创建 `src/modules/agent/infrastructure/discovery/repositories.py`
  - `DiscoverySessionRepository`
    - `create(session) → session`
    - `get_by_id(session_id) → session | None`
    - `update(session) → session`
    - `list_by_user(user_id, page, page_size) → list[session]`
  - `DiscoveryCandidateRepository`
    - `create(candidate) → candidate`
    - `update(candidate) → candidate`
    - `list_by_session(session_id) → list[candidate]`
- [ ] Domain ↔ Model mapper 函数
- **检查**: `uv run mypy src`

### Task 1.4: 会话管理服务
- [ ] 创建 `src/modules/agent/application/discovery/session_service.py`
  - `DiscoverySessionService`
    - `create_session(user_id, query) → session`
    - `get_session(session_id, user_id) → session`
    - `add_user_message(session_id, content) → message`
    - `update_status(session_id, status)`
    - `list_sessions(user_id, page, page_size) → list[session]`
    - `expire_stale_sessions()` — 过期清理
- **检查**: `uv run mypy src`

### Task 1.5: SSE 端点骨架
- [ ] 创建 `src/modules/agent/interfaces/discovery_router.py`
  - `POST /api/discovery/sessions` — 创建会话
  - `GET /api/discovery/sessions/{id}/stream` — SSE 流（先返回占位事件）
  - `POST /api/discovery/sessions/{id}/messages` — 用户消息
  - `GET /api/discovery/sessions/{id}` — 会话详情
  - `GET /api/discovery/sessions` — 会话列表
- [ ] 注册到主 app router
- [ ] 请求/响应 Pydantic 模型 (interfaces 层)
- **检查**: `uv run mypy src && uv run pytest`

### Task 1.6: 配置项
- [ ] 在 `src/core/config.py` 新增 Discovery 相关配置
  - `DISCOVERY_SESSION_TTL_SEC`
  - `DISCOVERY_AGENT_MODEL`
  - `DISCOVERY_AGENT_MAX_TOOL_CALLS`
  - `DISCOVERY_WEB_SEARCH_PROVIDER`
  - `DISCOVERY_WEB_SEARCH_API_KEY`
  - `DISCOVERY_RSSHUB_BASE_URL`
  - `DISCOVERY_PROBE_TIMEOUT_SEC`
- **检查**: `uv run mypy src`

### Task 1.7: PR-1 单元测试
- [ ] 测试 domain 实体的状态转换逻辑
- [ ] 测试 repository CRUD 操作
- [ ] 测试 session_service 基本流程
- [ ] 测试 SSE 端点返回正确状态码
- **检查**: `uv run pytest tests/modules/agent/discovery/`

---

## PR-2: Agent 核心（Pydantic AI Agent + 7 个工具）

### Task 2.1: 添加 pydantic-ai 依赖
- [ ] `uv add pydantic-ai`
- [ ] 确认与现有依赖无冲突
- **检查**: `uv run python -c "import pydantic_ai; print(pydantic_ai.__version__)"`

### Task 2.2: Agent 骨架
- [ ] 创建 `src/modules/agent/application/discovery/agent.py`
  - `DiscoveryAgent` 类
  - `DiscoveryDeps` 依赖注入数据类
  - System prompt 定义
  - `run_stream()` 方法 → 返回 async generator
- [ ] 创建 `src/modules/agent/application/discovery/tools/__init__.py`
- **检查**: `uv run mypy src/modules/agent/application/discovery/`

### Task 2.3: Tool — search_catalog
- [ ] 创建 `src/modules/agent/application/discovery/tools/catalog_search.py`
  - 从 `NewsNowCatalogProvider` 加载目录
  - 关键词模糊匹配 name/title
  - 检查已有 Source 列表标记重复
  - 返回最多 10 条匹配
- [ ] 单元测试 (mock catalog data)
- **检查**: `uv run mypy src && uv run pytest tests/modules/agent/discovery/test_catalog_search.py`

### Task 2.4: Tool — web_search
- [ ] 创建 `src/modules/agent/application/discovery/tools/web_search.py`
  - 搜索引擎 API 调用封装
  - 支持 Tavily (默认) 提供商
  - 返回最多 5 条结果
- [ ] 搜索服务不可用时的降级处理
- [ ] 单元测试 (mock API response)
- **检查**: `uv run mypy src && uv run pytest tests/modules/agent/discovery/test_web_search.py`

### Task 2.5: Tool — probe_rss
- [ ] 创建 `src/modules/agent/application/discovery/tools/rss_probe.py`
  - SSRF 校验（复用 `_is_allowed_url`）
  - HTML `<link rel="alternate">` 检测
  - 常见路径探测: `/rss`, `/feed`, `/atom.xml`, `/rss.xml`, `/feed.xml`
  - feedparser 验证
- [ ] 单元测试 (mock HTTP responses)
- **检查**: `uv run mypy src && uv run pytest tests/modules/agent/discovery/test_rss_probe.py`

### Task 2.6: Tool — search_rsshub
- [ ] 创建 `src/modules/agent/application/discovery/tools/rsshub_lookup.py`
  - 根据关键词 + 域名构造候选路由
  - 请求 RSSHub 实例验证
  - feedparser 解析验证
- [ ] 单元测试 (mock RSSHub responses)
- **检查**: `uv run mypy src && uv run pytest tests/modules/agent/discovery/test_rsshub_lookup.py`

### Task 2.7: Tool — analyze_site
- [ ] 创建 `src/modules/agent/application/discovery/tools/site_analyzer.py`
  - SSRF 校验
  - 获取 HTML，清理 script/style
  - 截取关键 DOM 结构（控制 token 量）
  - 返回简化 HTML 供 Agent 自身分析（Agent 用 LLM 能力生成 selectors）
- [ ] 单元测试
- **检查**: `uv run mypy src && uv run pytest tests/modules/agent/discovery/test_site_analyzer.py`

### Task 2.8: Tool — validate_source
- [ ] 创建 `src/modules/agent/application/discovery/tools/source_validator.py`
  - 调用 `FetcherFactory.create()` + `validate_config()` + `fetch()`
  - 返回验证结果: valid, status, items_count, sample_titles
- [ ] 单元测试 (mock fetcher)
- **检查**: `uv run mypy src && uv run pytest tests/modules/agent/discovery/test_source_validator.py`

### Task 2.9: Tool — add_source
- [ ] 创建 `src/modules/agent/application/discovery/tools/source_adder.py`
  - 前置检查: session 状态 == waiting_user
  - 重复检查: 源名称/URL
  - 调用 `SourceService.create_source()`
  - 创建 `SourceSubscription`
  - 更新 `CandidateSource.status → accepted`
- [ ] 单元测试
- **检查**: `uv run mypy src && uv run pytest tests/modules/agent/discovery/test_source_adder.py`

### Task 2.10: SSE 流式集成
- [ ] 将 `DiscoveryAgent.run_stream()` 输出接入 SSE 端点
  - agent_message 事件: Agent 文本输出
  - tool_call / tool_result 事件: 工具调用中间状态
  - confirm_required 事件: 需要用户确认
  - session_completed 事件: 完成
  - error 事件: 错误
- [ ] 用户消息路由: `POST /messages` → 唤醒 Agent 继续
- [ ] 断线恢复逻辑
- **检查**: `uv run mypy src && uv run pytest`

---

## PR-3: 集成验证与完善

### Task 3.1: 端到端集成测试
- [ ] 测试完整流程: 创建会话 → SSE 接收 → 用户确认 → 源添加
- [ ] 测试找不到源的场景: Agent 如实告知
- [ ] 测试会话过期清理
- [ ] 测试并发限制（每用户 1 个活跃会话）
- **检查**: `uv run pytest tests/modules/agent/discovery/test_e2e.py`

### Task 3.2: 错误处理完善
- [ ] 外部服务不可用时的降级路径
- [ ] LLM 调用失败重试
- [ ] 工具调用次数上限
- [ ] 会话状态异常恢复
- **检查**: `uv run pytest`

### Task 3.3: 安全加固
- [ ] SSRF 校验覆盖所有 URL 探测路径
- [ ] 速率限制: 每用户同时 1 个活跃会话
- [ ] HTML 清理: analyze_site 传 LLM 前的 sanitization
- [ ] add_source 的用户确认状态强校验
- **检查**: `uv run pytest && uv run mypy src`

### Task 3.4: 日志与可观测性
- [ ] structlog 结构化日志
  - 字段: session_id, user_id, tool_name, duration_ms
- [ ] Agent 工具调用计数与耗时统计
- [ ] 发现成功率指标（找到 / 总会话）
- **检查**: `uv run mypy src`

### Task 3.5: 全量检查
- [ ] `uv run pytest` — 全部测试通过
- [ ] `uv run mypy src` — 类型检查通过
- [ ] `uv run ruff check src` — 代码风格通过
- [ ] 手动测试: 至少 3 个不同类型的发现场景
  - 内置目录命中（如 "GitHub 动态"）
  - RSS/RSSHub 命中（如 "某政府公告"）
  - 找不到的场景（如 "网易云评论区"）
