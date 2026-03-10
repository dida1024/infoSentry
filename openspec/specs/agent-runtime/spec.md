# Agent Runtime Spec v0（infoSentry）

## Purpose

Push Orchestrator Agent 的运行时规格。该 Agent 接收候选信息条目（含匹配分数与特征），结合目标配置、历史行为与预算状态，输出结构化的推送决策（IMMEDIATE / BATCH / DIGEST / IGNORE）。核心设计原则：stateful + tool use + action ledger + replay + policy guardrails。

---

## Agent Identity & Constraints

### REQ-AGENT-001: Agent 角色定义

Agent MUST 作为 Push Orchestrator Agent（决策型），接收候选 items 并输出 Action Proposals。

- 输入：候选 items（match_score / features）+ goal 配置 + 历史行为 + 预算状态
- 输出：Action Proposals（结构化）
  - EMIT_DECISION（IMMEDIATE / BATCH / DIGEST / IGNORE）
  - ENQUEUE_EMAIL（可选，或由非 LLM 层执行）
  - SUGGEST_TUNING（v1+，仅建议）

#### Scenario: Agent 接收候选条目并输出决策

```
Given 一条新的候选 item 通过 MatchComputed 触发进入 Agent
  And 该 item 具有 match_score、cosine、term_hits 等特征
  And 对应 goal 的配置、历史行为、预算状态已可查询
When Agent 执行决策流水线
Then Agent MUST 输出至少一条 ActionProposal
  And 每条 ActionProposal MUST 包含结构化的 decision 类型与 reason_json
```

### REQ-AGENT-002: LLM 副作用隔离

LLM MUST NOT 直接执行副作用。所有写操作 MUST 通过 Tool Registry 中的写工具完成。

#### Scenario: LLM 生成决策但不直接写库

```
Given Agent 流水线进入 BoundaryJudgeNode
When LLM 返回判定结果（label + confidence + reason）
Then 判定结果 MUST 仅写入 AgentState.draft
  And 实际的数据库写入 MUST 由后续 EmitActionsNode 通过 emit_decision 工具完成
```

### REQ-AGENT-003: 输出可解释性

Agent 输出 MUST 包含解释与证据引用。每条决策 MUST 附带 reason 和 evidence 字段。

#### Scenario: 决策包含可追溯的证据

```
Given Agent 对一条 item 做出 IMMEDIATE 决策
When 决策写入 push_decisions 表
Then reason_json MUST 包含人类可读的 reason 文本
  And evidence 数组 MUST 引用具体的 item 字段（title / source / published_at）
```

### REQ-AGENT-004: 失败降级策略

Agent MUST 支持失败/超时降级。当 LLM 调用失败时，MUST 降级为保守决策。

#### Scenario: LLM 超时触发降级

```
Given Agent 调用 LLM 进行 BoundaryJudge 判定
When LLM 响应超时或返回 HTTP 429
Then Agent MUST 将 agent_runs.status 设为 FALLBACK
  And 决策 MUST 统一降级为 BATCH（保守策略）
```

---

## State Management

### REQ-STATE-001: AgentState Schema 定义

Agent MUST 使用以下 Pydantic Schema 管理运行时状态。所有 Node MUST 接收 AgentState 作为输入并返回 AgentState 作为输出。

```python
class AgentState(BaseModel):
    run_id: str
    trigger: Literal["MatchComputed", "BatchWindowTick", "DigestTick"]

    goal: GoalContext
    # goal_id, description, priority_mode, must_terms[], negative_terms[]
    # blocked_sources[]

    item: ItemContext
    # item_id, title, url, source_id, source_name, published_at, snippet

    match: MatchContext
    # score
    # features {cosine, term_hits, recency, source_trust}

    history: HistoryContext
    # recent_decisions[]
    # recent_clicks[]
    # feedback_stats {like, dislike}

    budget: BudgetContext
    # embedding_disabled, judge_disabled, usd_est_today

    draft: DraftContext
    # preliminary_bucket (optional)
    # llm_proposal (optional)
    # push_worthiness (optional) 推送价值判定结果 {label, confidence, uncertain, reason, evidence}
    # adjusted_score (optional) LLM 二判后的分数（可能被降到 DIGEST_MIN_SCORE 以下）
    # record_ignore (bool) 是否记录 IGNORE 决策
    # fallback_reason (optional) LLM 判定的回退原因

    actions: List[ActionProposal]
    # final_actions[]   # list of ActionProposal
```

#### Scenario: MatchComputed 触发 Immediate 决策状态初始化

```
Given 系统检测到一条新的 MatchComputed 事件
When AgentState 被构建
Then trigger MUST 为 "MatchComputed"
  And goal / item / match / history / budget 字段 MUST 填充完整
  And draft MUST 初始化为空（无 preliminary_bucket、无 llm_proposal）
  And actions MUST 初始化为空列表
```

### REQ-STATE-002: Node 状态变更约束

每个 Node MUST 仅修改 AgentState 的 `draft` 和 `actions` 字段。其他字段（goal / item / match / history / budget）MUST 保持不可变。

#### Scenario: Node 不得修改只读上下文字段

```
Given AgentState 已通过 LoadContextNode 填充 goal 与 item 信息
When 后续任一 Node（BucketNode / BoundaryJudgeNode 等）处理该 state
Then goal / item / match / history / budget 字段 MUST 与输入时完全一致
  And 仅 draft 和 actions 字段 MAY 被修改
```

---

## Tool Registry

### REQ-TOOL-001: 只读工具集合

Agent MUST 注册以下只读工具（默认允许调用）：

| 工具名 | 签名 | 用途 |
|--------|------|------|
| `get_goal_context` | `(goal_id)` | 获取目标配置 |
| `get_item` | `(item_id)` | 获取条目详情 |
| `get_history` | `(goal_id, window)` | 获取历史决策与点击 |
| `check_budget` | `()` | 检查预算状态 |
| `search_candidates` | `(goal_id, criteria)` | 搜索候选条目（Batch/Digest 路径） |

#### Scenario: LoadContextNode 调用只读工具加载上下文

```
Given Agent 流水线启动，AgentState 仅含 trigger 与基础 ID
When LoadContextNode 执行
Then MUST 调用 get_goal_context 填充 goal 字段
  And MUST 调用 get_item 填充 item 字段
  And MUST 调用 check_budget 填充 budget 字段
  And MUST 调用 get_history 填充 history 字段
```

### REQ-TOOL-002: 写工具集合（严格控制）

Agent MUST 注册以下写工具。写工具 MUST 仅在 EmitActionsNode 或 CoalesceNode 中调用：

| 工具名 | 签名 | 用途 |
|--------|------|------|
| `emit_decision` | `(goal_id, item_id, decision, reason_json, dedupe_key)` | 写入推送决策 |
| `enqueue_email` | `(decision_ids, channel)` | 加入邮件发送队列 |
| `record_tool_call` | `(run_id, ...)` | 记录工具调用日志 |
| `record_action_ledger` | `(run_id, ...)` | 写入不可变行动账本 |

#### Scenario: 写工具仅在 EmitActions 阶段调用

```
Given Agent 流水线已通过 BucketNode 和 BoundaryJudgeNode 完成决策判定
When EmitActionsNode 执行
Then MUST 调用 emit_decision 写入最终决策
  And MUST 调用 record_action_ledger 写入行动账本
  And MUST 调用 record_tool_call 记录本次所有工具调用
```

### REQ-TOOL-003: 工具调用审计记录

每次工具调用 MUST 写入 `agent_tool_calls` 表，记录以下字段：

- `tool_name`：工具名称
- `input_json`：输入参数（脱敏）
- `output_json`：输出结果（脱敏）
- `latency`：调用耗时
- `status`：调用状态

#### Scenario: 工具调用被完整记录

```
Given Agent 在 LoadContextNode 中调用 get_goal_context
When 工具调用完成
Then agent_tool_calls 表 MUST 新增一条记录
  And 记录 MUST 包含 tool_name = "get_goal_context"
  And input_json MUST 已脱敏（不含用户 PII）
  And latency MUST 为实际调用耗时（毫秒）
```

---

## Decision Pipeline — Immediate Path

### REQ-PIPE-001: Immediate Path 节点流程

Immediate Path（由 MatchComputed 触发）MUST 按以下顺序执行节点：

```
┌─────────────────┐
│ LoadContextNode │ tools.get_goal_context / get_item / check_budget / get_history
└────────┬────────┘
         │
         v
┌─────────────────┐
│  RuleGateNode   │ blocked_sources / negative_terms / STRICT must_terms 规则守门
└────────┬────────┘
         │
         v
┌─────────────────┐
│   BucketNode    │ score >= 0.93 => IMMEDIATE（初判）
│                 │ 0.88~0.93 => BOUNDARY（进入 LLM）
│                 │ 0.75~0.88 => BATCH
│                 │ <0.75 => IGNORE
└────────┬────────┘
         │
         v (仅 BOUNDARY 且 judge_disabled=false)
┌─────────────────────┐
│ BoundaryJudgeNode   │ 调 cheap model；若 uncertain/conf<阈值 => 升级大模型
│                     │ 输出结构化 proposal：label + reason + evidence + confidence + uncertain
└────────┬────────────┘
         │
         v
┌────────────────────┐
│ PushWorthinessNode │ LLM 二判：PUSH / SKIP；SKIP 会降分到 DIGEST_MIN_SCORE 以下并标记 IGNORE
└────────┬───────────┘
         │
         v
┌─────────────────┐
│ EmitActionsNode │ tools.emit_decision（幂等）
└────────┬────────┘
         │
         v (若 IMMEDIATE)
┌─────────────────┐
│  CoalesceNode   │ 5min 合并窗口，最多 3 条/封（写 decision_id 到 Redis buffer）
│                 │ 仅缓存非 deduplicated 决策
└─────────────────┘
```

### REQ-PIPE-002: RuleGateNode 规则守门

RuleGateNode MUST 在分数分桶之前执行硬规则过滤。

#### Scenario: 被封禁来源的 item 被直接拒绝

```
Given 一条 item 来自 source_id = "src-blocked-001"
  And 对应 goal 的 blocked_sources 列表包含 "src-blocked-001"
When RuleGateNode 执行
Then 该 item MUST 被标记为 IGNORE
  And 流水线 MUST 跳过后续 BucketNode / BoundaryJudgeNode
  And reason MUST 注明 "blocked_source"
```

#### Scenario: 包含否定关键词的 item 被拒绝

```
Given 一条 item 的 title 包含 goal 配置的 negative_terms 中的关键词
When RuleGateNode 执行
Then 该 item MUST 被标记为 IGNORE
  And reason MUST 注明匹配到的 negative_term
```

#### Scenario: STRICT 模式下缺少必须关键词被拒绝

```
Given goal 的 priority_mode = "STRICT"
  And must_terms = ["AI 芯片", "制裁"]
  And item 的 title + snippet 不包含任何 must_terms
When RuleGateNode 执行
Then 该 item MUST 被标记为 IGNORE
  And reason MUST 注明 "strict_must_terms_miss"
```

### REQ-PIPE-003: BucketNode 分数分桶

BucketNode MUST 根据 match_score 将 item 分入以下桶：

| 分数范围 | 分桶结果 | 后续路径 |
|----------|----------|----------|
| >= 0.93 | IMMEDIATE | 跳过 BoundaryJudge，直接 PushWorthiness |
| 0.88 ~ 0.93 | BOUNDARY | 进入 BoundaryJudgeNode（若 judge_disabled=false） |
| 0.75 ~ 0.88 | BATCH | 跳过 BoundaryJudge，直接 EmitActions |
| < 0.75 | IGNORE | 跳过后续所有节点 |

#### Scenario: 高分条目直接进入 IMMEDIATE

```
Given 一条 item 的 match_score = 0.95
When BucketNode 执行
Then draft.preliminary_bucket MUST 设为 "IMMEDIATE"
  And 流水线 MUST 跳过 BoundaryJudgeNode
```

#### Scenario: 边界分数进入 LLM 判定

```
Given 一条 item 的 match_score = 0.90
  And budget.judge_disabled = false
When BucketNode 执行
Then draft.preliminary_bucket MUST 设为 "BOUNDARY"
  And 流水线 MUST 进入 BoundaryJudgeNode
```

#### Scenario: 边界分数但 Judge 已禁用时降级

```
Given 一条 item 的 match_score = 0.90
  And budget.judge_disabled = true
When BucketNode 执行
Then draft.preliminary_bucket MUST 降级为 "BATCH"
  And 流水线 MUST 跳过 BoundaryJudgeNode
```

### REQ-PIPE-004: BoundaryJudgeNode LLM 判定

BoundaryJudgeNode MUST 调用 LLM 对 BOUNDARY 区间的 item 进行精细判定。

#### Scenario: Cheap model 判定高置信度

```
Given 一条 BOUNDARY item 进入 BoundaryJudgeNode
When cheap model 返回 confidence >= 阈值 且 uncertain = false
Then draft.llm_proposal MUST 设为返回的 label（IMMEDIATE 或 BATCH）
  And 流水线 MUST 继续到 PushWorthinessNode
```

#### Scenario: Cheap model 不确定时升级大模型

```
Given 一条 BOUNDARY item 进入 BoundaryJudgeNode
When cheap model 返回 uncertain = true 或 confidence < 阈值
Then Agent MUST 升级调用大模型进行二次判定
  And draft.llm_proposal MUST 使用大模型的返回结果
```

### REQ-PIPE-005: PushWorthinessNode 推送价值判定

PushWorthinessNode MUST 对 IMMEDIATE 和经 BoundaryJudge 判定为 IMMEDIATE 的 item 进行二次确认。

#### Scenario: 推送价值确认通过

```
Given 一条 item 经前序节点判定为 IMMEDIATE
When PushWorthinessNode 调用 LLM 二判返回 PUSH
Then draft.push_worthiness.label MUST 设为 "PUSH"
  And 流水线 MUST 继续到 EmitActionsNode，决策类型保持 IMMEDIATE
```

#### Scenario: 推送价值判定为 SKIP

```
Given 一条 item 经前序节点判定为 IMMEDIATE
When PushWorthinessNode 调用 LLM 二判返回 SKIP
Then draft.adjusted_score MUST 被降至 DIGEST_MIN_SCORE 以下
  And draft.record_ignore MUST 设为 true
  And 最终决策 MUST 变更为 IGNORE
```

### REQ-PIPE-006: EmitActionsNode 决策写入

EmitActionsNode MUST 调用 emit_decision 工具将最终决策写入数据库（幂等）。

#### Scenario: IMMEDIATE 决策被写入

```
Given Agent 流水线完成判定，最终决策为 IMMEDIATE
When EmitActionsNode 执行
Then MUST 调用 emit_decision(goal_id, item_id, "IMMEDIATE", reason_json, dedupe_key)
  And actions 列表 MUST 包含该 ActionProposal
```

### REQ-PIPE-007: CoalesceNode 合并窗口

CoalesceNode MUST 对 IMMEDIATE 决策执行 5 分钟合并窗口，每封邮件最多 3 条。

#### Scenario: 5 分钟内多条 IMMEDIATE 决策被合并

```
Given 同一 goal 在 5 分钟内产生 2 条 IMMEDIATE 决策
When CoalesceNode 执行
Then 两条决策的 decision_id MUST 写入同一个 Redis buffer
  And buffer 的 key MUST 为 goal_id + time_bucket
  And buffer 的 value MUST 是 push_decisions.id（decision_id），禁止写 item_id
```

#### Scenario: 合并窗口达到上限

```
Given 同一 goal 的合并窗口已有 3 条决策
When 第 4 条 IMMEDIATE 决策到达
Then 前 3 条 MUST 触发邮件发送
  And 第 4 条 MUST 进入新的合并窗口
```

#### Scenario: 已去重的决策不进入合并缓存

```
Given 一条决策的 dedupe_key 已存在于 push_decisions 表
When CoalesceNode 执行
Then 该决策 MUST NOT 写入 Redis buffer
```

---

## Decision Pipeline — Batch/Digest Path

### REQ-BATCH-001: Batch/Digest 路径流程

Batch（BatchWindowTick 触发）和 Digest（DigestTick 触发）路径 MUST 按以下步骤执行：

1. 调用 `search_candidates(goal_id, criteria)` 加载候选条目
2. 过滤 blocked_sources / negative_terms / 已推送重复项
3. 按 score + recency + term_hits 排序，选取 top N
4. 调用 LLM 进行推送价值二判（PUSH / SKIP）
5. 写入决策（BATCH / DIGEST / IGNORE）+ 加入邮件队列 + 记录 ledger 与 tool_calls

#### Scenario: Batch 窗口触发候选条目筛选与推送

```
Given BatchWindowTick 触发，goal_id = "goal-001"
When Agent 执行 Batch 路径
Then MUST 调用 search_candidates 获取候选列表
  And MUST 过滤 blocked_sources 和 negative_terms 匹配项
  And MUST 过滤已在 push_decisions 中存在的重复项
  And 剩余候选 MUST 按 score + recency + term_hits 排序取 top N
```

### REQ-BATCH-002: Batch 路径 SKIP 降分处理

Batch 路径中 LLM 二判返回 SKIP 的条目 MUST 降分并标记 IGNORE。

#### Scenario: Batch 路径 LLM 判定 SKIP

```
Given Batch 路径中一条候选 item 进入 LLM 推送价值二判
When LLM 返回 SKIP
Then item 的 adjusted_score MUST 被降至 DIGEST_MIN_SCORE 以下
  And 该 item 的决策 MUST 标记为 IGNORE
```

### REQ-BATCH-003: Batch 路径处理量上限

Batch 路径 MUST 受 `BATCH_IGNORE_LIMIT`（默认值 = `BATCH_MAX_ITEMS`）控制总处理量，包括 IGNORE 决策在内。

#### Scenario: Batch 路径达到处理上限

```
Given BATCH_IGNORE_LIMIT = 10
  And search_candidates 返回 15 条候选
When Agent 处理 Batch 路径
Then 最多处理 10 条（含最终标记为 IGNORE 的条目）
  And 剩余 5 条 MUST 等待下一个 Batch 窗口
```

---

## LLM Integration & Fallback

### REQ-LLM-001: BoundaryJudgeOutput Schema

BoundaryJudgeNode 的 LLM 输出 MUST 严格遵循以下 JSON Schema：

```json
{
  "label": "IMMEDIATE | BATCH",
  "confidence": 0.85,
  "uncertain": false,
  "reason": "该新闻涉及用户关注的核心关键词「AI 芯片」，且来源可信度高",
  "evidence": [
    {
      "type": "TERM_HIT",
      "value": "AI 芯片",
      "ref": {"item_id": "abc-123", "field": "title"}
    },
    {
      "type": "SOURCE",
      "value": "Reuters",
      "ref": {"item_id": "abc-123", "field": "source"}
    },
    {
      "type": "TIME",
      "value": "2025-12-28T10:30:00Z",
      "ref": {"item_id": "abc-123", "field": "published_at"}
    }
  ]
}
```

- `label` MUST 为 `"IMMEDIATE"` 或 `"BATCH"`
- `confidence` MUST 为 0~1 浮点数
- `uncertain` MUST 为布尔值
- `reason` MUST 为人类可读的中文解释
- `evidence` MUST 为数组，每项 MUST 包含 `type`、`value`、`ref`

#### Scenario: LLM 返回符合 Schema 的判定

```
Given BoundaryJudgeNode 调用 LLM
When LLM 返回 JSON 通过 BoundaryJudgeOutput schema 校验
Then draft.llm_proposal MUST 使用该返回值
  And evidence 数组中每项 MUST 可追溯到 item 的具体字段
```

### REQ-LLM-002: LLM 失败统一降级

当 LLM 调用出现 schema 校验失败、超时或 HTTP 429 时，Agent MUST 统一降级为 BATCH。

#### Scenario: Schema 校验失败触发 FALLBACK

```
Given BoundaryJudgeNode 调用 LLM
When LLM 返回的 JSON 不符合 BoundaryJudgeOutput schema
Then agent_runs.status MUST 设为 "FALLBACK"
  And draft.fallback_reason MUST 记录 "schema_validation_failed"
  And 该 item 的决策 MUST 降级为 BATCH
```

#### Scenario: HTTP 429 触发 FALLBACK

```
Given BoundaryJudgeNode 调用 LLM
When LLM API 返回 HTTP 429 (Too Many Requests)
Then agent_runs.status MUST 设为 "FALLBACK"
  And draft.fallback_reason MUST 记录 "rate_limited"
  And 该 item 的决策 MUST 降级为 BATCH
```

---

## Idempotency & Consistency

### REQ-IDEM-001: emit_decision 幂等键

emit_decision MUST 使用 `dedupe_key` 保证幂等。相同 `dedupe_key` 的重复调用 MUST NOT 产生重复决策记录。

#### Scenario: 重复的 dedupe_key 被拒绝

```
Given emit_decision 已成功写入 dedupe_key = "goal-001_item-abc_20260309"
When 再次调用 emit_decision 使用相同的 dedupe_key
Then 第二次调用 MUST NOT 插入新记录
  And MUST 返回已存在的 decision_id
```

### REQ-IDEM-002: Coalesce Buffer Key 规范

Coalesce buffer MUST 使用 `goal_id + time_bucket` 作为 Redis key。

#### Scenario: 相同 goal 的决策落入同一时间桶

```
Given goal_id = "goal-001"
  And 当前 time_bucket = "2026-03-09T10:00"
When 两条 IMMEDIATE 决策在该时间桶内产生
Then 两条决策 MUST 写入同一个 Redis key = "goal-001:2026-03-09T10:00"
```

### REQ-IDEM-003: Coalesce Buffer 必须使用 decision_id

Coalesce buffer 的 value MUST 是 `push_decisions.id`（decision_id）。MUST NOT 使用 item_id。

#### Scenario: Buffer 存储 decision_id 而非 item_id

```
Given 一条 IMMEDIATE 决策生成 decision_id = "dec-001"，对应 item_id = "item-abc"
When CoalesceNode 写入 Redis buffer
Then buffer value MUST 包含 "dec-001"
  And buffer value MUST NOT 包含 "item-abc"
```

### REQ-IDEM-004: Email 队列基于 decision_id

enqueue_email MUST 仅基于 `push_decisions.id` 入队，避免重复内容推送。

#### Scenario: 邮件入队使用 decision_id

```
Given 合并窗口到期，buffer 中有 decision_ids = ["dec-001", "dec-002"]
When enqueue_email 被调用
Then MUST 传入 decision_ids = ["dec-001", "dec-002"]
  And 邮件渲染 MUST 通过 decision_id 关联获取 item 内容
```

---

## Replay & Observability

### REQ-REPLAY-001: 回放流程

Agent MUST 支持基于 `run_id` 的完整回放。回放流程为：

1. 读取 `agent_runs.input_snapshot`（原始输入快照）
2. 读取 `agent_tool_calls`（工具调用记录）
3. 使用 input_snapshot 重放决策流水线
4. 对比重放结果与原始 Action Ledger（diff）

#### Scenario: 回放一次 Agent 运行

```
Given agent_runs 中存在 run_id = "run-20260309-001"
  And 该 run 的 input_snapshot 和 tool_calls 已完整记录
When 触发回放（GET /api/agent/runs/run-20260309-001/replay）
Then 系统 MUST 使用 input_snapshot 重新执行决策流水线
  And 返回 original_actions（原始决策）
  And 返回 replayed_actions（重放决策）
  And 返回 diff（两者差异）
```

### REQ-REPLAY-002: 回放 API

Agent MUST 提供以下回放 API 端点：

```
GET /api/agent/runs/{run_id}/replay
Response:
{
  "original_actions": [...],
  "replayed_actions": [...],
  "diff": [...]
}
```

#### Scenario: 回放用于定位误报

```
Given 用户反馈 item "xyz" 不应被推送为 IMMEDIATE
  And 该 item 的决策来自 run_id = "run-20260309-002"
When 运维人员调用回放 API
Then diff MUST 清晰展示哪个 Node 做出了 IMMEDIATE 判定
  And 可据此调整阈值或策略
```

### REQ-REPLAY-003: 回放目的

回放功能 MUST 支持以下运维场景：

- 定位误报 / 漏报
- 调整分数阈值
- 验证新策略的效果

---

## v1 Migration Readiness

### REQ-MIGRATE-001: v0 到 v1 框架映射

v0 的 Node 设计 MUST 保持与 LangGraph 等框架的兼容性。v0 组件与 v1 框架的映射关系：

| v0 组件 | v1 框架对应 |
|---------|-------------|
| AgentState | State schema |
| Node | Graph node |
| Tools | Tool binding |
| action_ledger | Checkpointer |
| run_id | Thread ID |

#### Scenario: v1 迁移不影响核心逻辑

```
Given v0 的 Node 实现遵循 AgentState 输入/输出约定
  And 所有副作用通过 Tool Registry 执行
When 迁移到 LangGraph 框架
Then 仅需替换编排层 wiring（Node 连接方式）
  And nodes / tools 代码 MUST 可直接复用
  And 添加 checkpointer 持久化替代 action_ledger
```

### REQ-MIGRATE-002: 迁移步骤

迁移到 v1 框架时 MUST 按以下步骤执行：

1. 替换编排层 wiring（Node 之间的调度与连接）
2. 复用 nodes / tools 代码（无需重写业务逻辑）
3. 添加 checkpointer 持久化（替代手动 action_ledger 管理）

#### Scenario: 迁移后回放功能保持可用

```
Given v0 的 replay 功能基于 input_snapshot + tool_calls 实现
When 迁移到 v1 框架并使用 checkpointer
Then 回放功能 MUST 继续可用
  And MAY 利用 checkpointer 的内置 replay 能力增强回放精度
```
