# Discovery Hardening Guardrails：交互式发现链路加固与长期约束固化

## 1. 背景

当前 `source-discovery-agent` 已经完成了第一阶段骨架，但审查显示 discovery 链路存在一组会反复出现的问题：

1. 交互式会话状态依赖文案启发式判断，缺少显式状态驱动
2. 候选源发现/验证/接受缺少完整持久化闭环
3. 外部 URL 获取虽有 SSRF 初始校验，但未约束重定向目标
4. 创建 source 与订阅不是统一成功语义，存在部分成功脏状态
5. 一些实现细节没有被提升为仓库级长期约束，后续类似需求容易重复犯错

这些问题既影响当前 discovery 功能，也暴露出交互式 agent 和外部抓取场景缺少明确规格约束。

## 2. 目标

本变更拆成一项独立优化行动，目标是：

1. 为 discovery 会话补齐正确性和一致性护栏
2. 将可复用的长期约束直接固化到 `openspec/specs/`
3. 让后续交互式 agent / URL 获取 / SSE 对话式功能在规格层面默认继承这些限制

## 3. 变更范围

本 change 关注以下内容：

1. discovery session 状态机显式化
2. candidate 生命周期持久化
3. URL 获取的 redirect-safe SSRF 约束
4. source 创建与订阅的一致性语义
5. discovery API 的重连恢复契约
6. 并发 active session 约束与过期清理策略

## 4. 非目标

本 change 不包含：

1. 改造其他非 discovery 业务模块
2. 引入新的 agent 编排框架
3. 扩展 discovery 的产品能力范围

## 5. 预期结果

完成后：

1. discovery 的状态推进、候选恢复、完成判定将具备可验证的数据语义
2. URL 抓取安全约束会成为仓库级规格，而不是某个工具里的局部实现
3. 后续类似需求在设计阶段就会受到这些规格约束，减少重复返工

## 6. 本轮复审新增确认的问题

在执行 `source-discovery-agent` 后再次复审，新增确认以下仍未闭合的问题需要纳入本 change：

1. active discovery session 约束仍仅依赖应用层 `count_active_by_user()`，缺少数据库级或等价强约束
2. stream 状态推进仍通过扫描 tool result 的字符串内容判断 `valid/success`，不是真正的显式业务事件
3. `discovery_router` 仍直接实例化 `InfrastructureNewsNowCatalogProvider`，违反 interfaces → application → domain 的边界方向
4. `add_source` 在 candidate 状态更新失败时仍可能返回整体成功，未满足完整一致性语义
5. `expire_stale_sessions()` 仍只处理前 100 条会话，无法覆盖全部过期记录
6. `DISCOVERY_WEB_SEARCH_PROVIDER` 已进入配置，但运行时实现仍写死 Tavily，配置语义未兑现
