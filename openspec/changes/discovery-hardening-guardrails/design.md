# Discovery Hardening Guardrails — 技术设计

## 1. 设计原则

本次优化不是扩功能，而是把 discovery 从“可运行骨架”收敛到“可长期维护的交互式 agent 流程”。

核心原则：

1. 状态由显式事件驱动，不由模型文案推断
2. 用户可见数据必须可重连恢复
3. 外部 URL 安全校验覆盖完整请求路径，包括重定向
4. 对用户承诺“已添加成功”时，写入语义必须一致

## 2. 交互式 Discovery 会话模型

### 2.1 显式状态推进

`DiscoverySession.status` 只允许由以下显式事件驱动：

1. `turn_started`
2. `confirmation_requested`
3. `candidate_accepted`
4. `turn_failed`
5. `session_expired`

禁止通过扫描 agent 自然语言输出中的关键词来切换：

1. `WAITING_USER`
2. `COMPLETED`
3. `FAILED`

### 2.2 Candidate 持久化闭环

candidate 生命周期必须完整落库：

1. 发现候选时创建 `discovery_candidates`
2. 验证开始时更新为 `VALIDATING`
3. 验证完成后更新为 `VALID` 或 `INVALID`
4. 用户确认后更新为 `ACCEPTED` 并写入 `source_id`
5. 用户拒绝后更新为 `REJECTED`

`GET /discovery/sessions/{id}` 返回的数据必须足够让前端在断线后恢复：

1. 完整消息历史
2. 当前 session 状态
3. 当前候选源列表及其验证状态

## 3. URL 获取安全

### 3.1 请求约束

discovery 相关 URL 工具仅允许：

1. `http`
2. `https`

必须拒绝：

1. `file://`
2. 自定义协议
3. 指向 private / loopback / link-local / reserved / multicast 的目标

### 3.2 Redirect-safe 校验

若工具需要处理重定向，必须满足以下其一：

1. 禁止自动重定向
2. 逐跳校验 `Location` 的目标 host 后再继续请求

禁止“只校验初始 URL，再无条件 follow redirects”。

## 4. Source 添加一致性

`add_source` 的成功语义必须是：

1. source 创建成功
2. 当前用户订阅成功
3. candidate 状态和 `source_id` 已同步落库

若创建 source 成功但订阅失败，系统必须采用以下之一：

1. 同事务回滚整体操作
2. 明确补偿删除已创建 source
3. 返回失败并记录需要人工/系统修复的补偿状态

禁止对外返回“success=true”但用户实际上没有完成订阅。

## 5. 并发与过期

### 5.1 单用户 active session 约束

“每用户最多一个 active/waiting session” 不能只依赖应用层 `count_active_by_user()`。

必须增加至少一种强约束：

1. 数据库唯一约束或部分索引
2. 事务内锁定
3. 等价强一致机制

### 5.2 过期清理

过期清理必须覆盖全部符合条件记录，不能只扫描固定前 N 条。

可接受方案：

1. 分页扫全量
2. 条件批量更新

## 6. Canonical Specs 提升策略

本次 change 中以下内容应升级为仓库级规格：

1. 交互式 agent 的显式状态驱动约束
2. 外部 URL 获取的 redirect-safe SSRF 约束
3. discovery API 的持久化恢复契约

这些规则会同步写入：

1. `openspec/specs/agent-runtime/spec.md`
2. `openspec/specs/system-architecture/spec.md`
3. `openspec/specs/api-contracts/spec.md`

## 7. 本轮修复细化

### 7.1 Active Session 强约束

当前实现仍只有应用层并发检查。修复时必须增加一项强约束机制：

1. 数据库 partial unique index，限制同一用户同时最多一个 `active/waiting_user` session
2. 或等价的事务锁/串行化策略

仅保留 `count_active_by_user()` 作为友好报错前置检查，不可视为最终一致性保证。

### 7.2 Stream 状态推进信号

当前 stream 实现通过扫描 tool result 序列化文本中的 `"valid": true` / `"success": true` 来推进状态。这不是合格的显式业务事件。

修复方向应为：

1. tool 返回结构化的业务结果类型或显式标志
2. stream 层仅根据明确字段或命令结果推进 `WAITING_USER` / `COMPLETED`
3. 禁止继续用字符串包含判断作为状态驱动依据

### 7.3 Router 依赖注入

`discovery_router` 不得直接构造 `InfrastructureNewsNowCatalogProvider`。

修复方向：

1. 在 application/infrastructure dependencies 中提供 catalog provider getter
2. router 仅通过 Depends 注入抽象能力

### 7.4 add_source 完整成功语义

`success=true` 必须同时满足：

1. source 创建成功
2. subscribe 成功
3. candidate accept/source_id 更新成功

若第 3 步失败，必须：

1. 继续补偿回滚整体操作，或
2. 明确返回失败并留下可修复状态，不得对外宣称完成

### 7.5 全量过期清理

`expire_stale_sessions()` 必须覆盖全部符合条件记录。

可接受方案：

1. 分页循环直到无更多记录
2. 按条件批量更新

固定 `page=1, page_size=100` 的扫描不满足要求。

### 7.6 Web Search Provider 配置兑现

`DISCOVERY_WEB_SEARCH_PROVIDER` 已是公开配置项，修复时必须二选一：

1. 真正支持按配置选择 provider
2. 删除该配置并收敛为单 provider 语义

禁止保留“配置可选”但实现写死的状态。
