# Boundary checks

## 禁止项
- 接口层直接 import infrastructure 仓储/依赖（例如 `...infrastructure.repositories`、`...infrastructure.dependencies`）。
- 接口层直接 import 基础设施认证依赖（如 `core.infrastructure.security.jwt.get_current_user_id`）。
- 接口层拼装复杂业务响应（通知列表、证据链、动作列表、分页游标等）。
- 接口层执行业务流程（反馈更新、点击跟踪、配置/健康检查聚合）。
- 应用层直接 import infrastructure（Redis/JWT/fetchers/models/queues 等）。
- 应用层直接依赖 infra 常量（如队列枚举在 infrastructure）。

## 推荐项
- 路由只负责：参数校验、调用 application service/use-case、返回 response schema。
- 认证依赖来自 application 层（例如 `core.application.security.get_current_user_id`），由入口进行 override 绑定到 infra 实现。
- 业务逻辑（通知拼装、反馈、点击、监控/配置聚合）下沉到 application services。
- 应用层通过 ports/Protocol 注入依赖（KVClient、TokenService、FetcherFactory）。
- 跨层共享常量放 domain（如队列枚举），infra 仅引用。
- 入口 `main.py` 必须集中配置 `dependency_overrides`，把 application dependencies 映射到 infrastructure implementations。

## 检查命令
- 查接口层违规引用：
  - `rg -n "infrastructure" infoSentry-backend/src/modules/*/interfaces`
- 查应用层违规引用：
  - `rg -n "infrastructure" infoSentry-backend/src/modules/*/application`
- 查认证依赖是否在 app 层：
  - `rg -n "get_current_user_id" infoSentry-backend/src/modules/*/interfaces`
- 查入口是否配置 DI overrides：
  - `rg -n "dependency_overrides" infoSentry-backend/main.py`
