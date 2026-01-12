# 后端任务文档（infoSentry）

## 范围
处理评审中发现的后端问题：DDD 分层、路由业务逻辑、基础设施耦合、类型、异常处理、配置、日志与测试。

## 原则
- interfaces -> application -> domain；infrastructure 实现 domain 接口。
- 路由/控制器不包含业务逻辑。
- 后端优先使用 async/await。
- mypy 严格模式，不使用 `# type: ignore`。
- 不允许静默吞异常。
- 不允许硬编码配置值。
- 关键业务事件使用 structlog 记录。

## 任务清单

### ✅ T1. 贯彻 DDD 依赖方向
- 目标：移除接口层与应用层直接使用 infrastructure。
- 影响范围：
  - infoSentry-backend/src/modules/users/interfaces/router.py
  - infoSentry-backend/src/modules/agent/interfaces/router.py
  - infoSentry-backend/src/modules/push/interfaces/router.py
  - infoSentry-backend/src/modules/goals/interfaces/router.py
  - infoSentry-backend/src/modules/sources/interfaces/router.py
  - infoSentry-backend/src/modules/items/application/budget_service.py
  - infoSentry-backend/src/modules/sources/application/ingest_service.py
  - infoSentry-backend/src/modules/agent/application/monitoring_service.py
  - infoSentry-backend/src/modules/users/application/handlers.py
- 工作内容：
  - 引入应用服务/用例，承载接口层需求。
  - 在 domain 或 application 定义接口（如 FeatureFlagStore、BudgetStore、FetcherPort、TokenService），由 infrastructure 实现。
  - 通过依赖注入提供实现。
- 验收标准：
  - interfaces 仅依赖 application/domain。
  - application 仅依赖 domain（通过 DI 接入接口/适配器）。

### ✅ T2. 将路由业务逻辑下沉到 application 层
- 目标：路由保持“薄”，只做校验和调用用例。
- 影响范围：
  - infoSentry-backend/src/modules/push/interfaces/router.py
  - infoSentry-backend/src/modules/agent/interfaces/router.py
- 工作内容：
  - 将通知列表拼装、反馈处理、点击追踪、配置/健康/监控流程抽到 application 服务。
- 验收标准：
  - 路由只负责请求映射与响应返回。

### ✅ T3. 去除 application -> infrastructure 的直接依赖
- 目标：应用层只依赖 domain 抽象。
- 影响范围：
  - infoSentry-backend/src/modules/items/application/budget_service.py
  - infoSentry-backend/src/modules/sources/application/ingest_service.py
  - infoSentry-backend/src/modules/agent/application/monitoring_service.py
  - infoSentry-backend/src/modules/users/application/handlers.py
- 工作内容：
  - 为 Redis、抓取器、JWT/Token 发行等引入 port/interface。
  - 在 infrastructure 提供实现并注入。
- 验收标准：
  - application 中不再 import src.core.infrastructure.* 或 modules/*/infrastructure/*。

### ✅ T4. 修复类型与严格模式
- 目标：满足 mypy strict。
- 影响范围：
  - infoSentry-backend/src/core/config.py
  - infoSentry-backend/src/modules/items/tasks.py
  - infoSentry-backend/src/modules/sources/interfaces/router.py
  - infoSentry-backend/src/modules/goals/interfaces/router.py
- 工作内容：
  - 移除 settings 初始化处的 `# type: ignore` 并修复根因。
  - 补齐缺失的返回类型与参数类型注解。
- 验收标准：
  - 无 `# type: ignore`。
  - 公共函数/方法具备完整注解。

### ✅ T5. 消除静默吞异常
- 目标：明确处理异常并记录日志/抛出。
- 影响范围：
  - infoSentry-backend/src/modules/agent/application/monitoring_service.py
  - infoSentry-backend/src/modules/sources/infrastructure/fetchers/newsnow.py
  - infoSentry-backend/src/modules/sources/infrastructure/fetchers/rss.py
- 工作内容：
  - 用明确处理与结构化日志替换 `except Exception: pass`。
  - 确保失败能被记录或冒泡。
- 验收标准：
  - 无异常处理中的静默 `pass`。

### T6. 配置化硬编码参数
- 目标：将常量迁移至配置（settings/env）。
- 影响范围：
  - infoSentry-backend/src/core/config.py
  - infoSentry-backend/src/modules/items/application/budget_service.py
  - infoSentry-backend/src/modules/agent/application/monitoring_service.py
  - infoSentry-backend/src/modules/sources/infrastructure/fetchers/rss.py
  - infoSentry-backend/src/modules/items/application/embedding_service.py
- 工作内容：
  - 为阈值、价格、超时、UA、文本长度等增加 settings 字段。
  - 代码中改用 settings。
- 验收标准：
  - 运行路径不新增硬编码业务/运维常量。

### T7. 日志标准化（structlog）
- 目标：关键业务事件使用 structlog。
- 影响范围：
  - infoSentry-backend/src/core/infrastructure/logging.py
  - 关键 domain/application 服务与任务（如 ingest/embed/match/push）
- 工作内容：
  - 引入 structlog 配置，替换关键事件日志。
  - 保持 debug 日志字段结构化一致。
- 验收标准：
  - 关键业务事件以 structlog 输出。

### T8. 测试与迁移对齐
- 目标：确保重构后行为一致。
- 影响范围：
  - infoSentry-backend/tests/*
- 工作内容：
  - 为新 application 服务与薄路由调整/补充测试。
  - 若引入模型变更，检查迁移一致性。
- 验收标准：
  - 测试覆盖重构用例；无遗漏迁移。

## 里程碑
- M1：接口层不再依赖 infrastructure（T1, T2, T3）。
- M2：类型与异常处理干净（T4, T5）。
- M3：配置/日志/测试更新完成（T6, T7, T8）。
