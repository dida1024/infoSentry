## ADDED Requirements

### Requirement: Discovery 会话详情必须支持断线恢复

系统 MUST 提供可恢复 discovery 会话的详情接口语义。会话详情必须包含足以恢复交互的持久化状态。

#### Scenario: 客户端在等待确认前断线

```
Given 用户已创建 discovery session
  And Agent 已输出候选结果并进入等待用户确认状态
When 客户端重新请求该 session 的详情
Then 响应 MUST 包含完整消息历史
  And MUST 包含候选结果及其验证状态
  And MUST 包含当前 session 状态，以便客户端决定下一步交互
```

### Requirement: Discovery 完成语义必须基于显式业务结果

Discovery API MUST 仅在显式业务动作完成后暴露 completed 语义。

#### Scenario: 候选验证成功但尚未真正添加 source

```
Given Agent 已验证候选 source 可用
  And 用户尚未确认添加，或 source/subscribe 写入尚未一致完成
When 客户端读取会话状态或流事件
Then 系统 MUST NOT 将该 session 标记为 completed
  And MUST 将其保留在可继续交互的状态
```
