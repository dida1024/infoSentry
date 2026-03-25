# Discovery Hardening Guardrails — 实施任务

## 1. Spec 固化

- [ ] 将交互式 agent 的显式状态驱动约束写入 `openspec/specs/agent-runtime/spec.md`
- [ ] 将 redirect-safe URL 获取约束写入 `openspec/specs/system-architecture/spec.md`
- [ ] 将 discovery 会话恢复与完成语义写入 `openspec/specs/api-contracts/spec.md`

## 2. Discovery Correctness 修复

- [x] 修复 `search_catalog` 传入裸字符串 `source_type` 导致去重失效的问题
- [x] 将 session 状态切换从文案启发式改为显式事件驱动（_signal 字段）
- [x] 为 candidate 发现、验证、接受、拒绝补齐完整持久化路径
- [x] 确保 `GET /discovery/sessions/{id}` 可恢复完整候选和消息状态

## 3. 安全与一致性修复

- [x] 为 `probe_rss` 和 `fetch_site_html` 加入 redirect-safe SSRF 校验（http_safe.py safe_get）
- [x] 明确 `add_source` 的事务/补偿语义，消除部分成功返回
- [x] 为单用户 active session 限制增加数据库级或等价强约束（partial unique index）
- [x] 将过期清理改为全量覆盖策略，而不是固定扫描前 100 条

## 4. 测试与验证

- [x] 增加 SSRF redirect 回归测试（4 个 redirect-safe 测试）
- [x] 增加 candidate 持久化与断线恢复测试
- [x] 增加 source 创建成功但订阅失败的一致性测试
- [x] 增加并发创建 session 的竞态测试（API 层 409 + DB partial unique index）
- [x] 增加 SSE 事件流测试，覆盖 confirmation/completion/failure 语义
- [x] 运行项目要求的验证命令并记录结果：359 passed, 0 mypy errors, ruff clean

## 5. 文档与配置

- [x] 更新 `infoSentry-backend/.env.example` 中的 `DISCOVERY_*` 配置项
- [x] 更新 `source-discovery-agent` 相关 change 文档，使其与新的 guardrails 一致

## 6. 本轮复审补充修复项

- [x] 为 discovery session 增加数据库级或等价强约束（0010_active_session_unique.py partial unique index）
- [x] 重构 `run_discovery_stream()` 的状态推进，移除对 tool result 字符串内容的 `valid/success` 扫描（改用 `_signal` 字段）
- [x] 将 `InfrastructureNewsNowCatalogProvider` 从 router 直接实例化改为通过 DI 注入
- [x] 收紧 `add_source` 成功语义：candidate accept/source_id 更新失败时不得返回整体成功
- [x] 将 `expire_stale_sessions()` 改为全量覆盖策略（分页循环）
- [x] 兑现 `DISCOVERY_WEB_SEARCH_PROVIDER` 配置语义，或移除该配置（已移除，收敛为 Tavily-only）
- [x] 为以上 6 项分别补充回归测试或契约测试
