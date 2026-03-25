## MODIFIED Requirements

### Requirement: LLM 副作用隔离

交互式 Agent MUST NOT 通过自然语言输出隐式驱动业务状态。所有会话状态推进和持久化副作用 MUST 由显式工具结果或系统事件驱动。

#### Scenario: 交互式会话状态不得由文案关键词判断

```
Given 一个交互式 Agent 通过 SSE 向用户输出自然语言内容
When 系统判断本轮会话是否需要进入 waiting_user、completed 或 failed
Then 系统 MUST 基于显式工具结果、结构化事件或内部命令结果来推进状态
  And MUST NOT 仅因输出文本中包含“确认”“成功”等关键词而切换状态
```

## ADDED Requirements

### Requirement: 交互式 Agent 状态机显式化

任何支持多轮交互和断线恢复的 Agent MUST 将会话状态机显式建模，并将状态推进持久化。

#### Scenario: 多轮交互 Agent 使用显式状态推进

```
Given 一个支持“用户确认后继续执行”的 Agent 会话
When 本轮执行结束
Then 会话 MUST 被写入明确的 status
  And 下一轮执行 MUST 从持久化状态恢复，而不是依赖进程内临时上下文
```

### Requirement: 用户可见候选结果必须可恢复

对于会展示候选结果、校验结果或待确认动作的交互式 Agent，用户可见结果 MUST 持久化并可通过查询接口恢复。

#### Scenario: 断线后恢复候选与确认状态

```
Given Agent 已发现并验证多个候选结果，随后 SSE 连接断开
When 客户端重新请求会话详情
Then 系统 MUST 返回完整的历史消息、候选结果和当前确认状态
  And 用户 MUST 能在不依赖旧连接内存状态的情况下继续流程
```
