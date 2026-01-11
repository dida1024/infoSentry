# Agent Runtime Spec v0（infoSentry）

目标：让系统"像 Agent"，而不是"调用 LLM 分析"  
关键：stateful + tool use + action ledger + replay + policy guardrails

---

## 1. Agent 定位（v0）
Push Orchestrator Agent（决策型 Agent）：
- 输入：候选 items（match_score/features）+ goal 配置 + 历史行为 + 预算状态
- 输出：Action Proposals（结构化）
  - EMIT_DECISION（IMMEDIATE/BATCH/DIGEST/IGNORE）
  - ENQUEUE_EMAIL（可选，或由非 LLM 层执行）
  - SUGGEST_TUNING（v1+，仅建议）
- 约束：
  - LLM 不直接执行副作用
  - 输出必须解释 + 引用证据
  - 失败/超时可降级

---

## 2. 核心概念
- Observation：本轮决策可用信息快照
- Tools：受控能力集合（读/写分权）
- Action Ledger：不可变行动账本（审计、回放）
- Policy：预算/安全/幂等护栏

---

## 3. AgentState（建议 Pydantic Schema）

### 3.1 Immediate 决策 State（MatchComputed 触发）

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
    
    actions: List[ActionProposal]
    # final_actions[]   # list of ActionProposal
```

---

## 4. Tool Registry（工具注册表）

### 4.1 工具分类
只读工具（默认允许）：
- get_goal_context(goal_id)
- get_item(item_id)
- get_history(goal_id, window)
- check_budget()
- search_candidates(goal_id, criteria)

写工具（严格控制）：
- emit_decision(goal_id, item_id, decision, reason_json, dedupe_key)
- enqueue_email(decision_ids, channel)
- record_tool_call(run_id, ...)
- record_action_ledger(run_id, ...)

### 4.2 工具调用记录（必须）
每次调用写 agent_tool_calls：
- tool_name
- input_json（脱敏）
- output_json（脱敏）
- latency/status

---

## 5. Node 设计（v0 不引框架，但按"可图化"拆分）

节点必须满足：
- 输入：AgentState
- 输出：AgentState（只改 draft/actions）
- 副作用只能通过 tools

### 5.1 Node 列表（Immediate Path）

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
         v (若 IMMEDIATE)
┌─────────────────┐
│  CoalesceNode   │ 5min 合并窗口，最多 3 条/封（写 Redis buffer）
└────────┬────────┘
         │
         v
┌─────────────────┐
│ EmitActionsNode │ tools.emit_decision（幂等）
│                 │ tools.enqueue_email（或写入 email queue）
└─────────────────┘
```

### 5.2 Batch/Digest Path
- Load candidates（search_candidates）
- Filter（blocked/negative/repeat）
- Select top N（score+recency+term）
- Emit decisions + enqueue email

---

## 6. LLM 输出 Schema（强制）

### 6.1 BoundaryJudgeOutput（JSON）

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

### 6.2 失败处理
- schema 校验失败 / 超时 / 429：
  - 记录 agent_runs.status=FALLBACK
  - 统一降级 BATCH（保守）

---

## 7. 幂等与一致性
- emit_decision 必须使用 dedupe_key unique
- coalesce buffer 的 key = goal_id + time_bucket
- email enqueue 只基于 push_decisions.id，避免重复内容

---

## 8. Replay（回放）

### 8.1 回放流程
1. 输入：run_id
2. 读取：agent_runs.input_snapshot + tool_calls
3. 输出：重放得到的 final_actions 与当时的 ledger 对比（diff）

### 8.2 回放目的
- 定位误报/漏报
- 调阈值
- 验证新策略

### 8.3 回放 API

```
GET /api/agent/runs/{run_id}/replay
Response:
{
  "original_actions": [...],
  "replayed_actions": [...],
  "diff": [...]
}
```

---

## 9. 迁移到 v1 框架（预留）

v0 的 Node 设计已经为迁移到 LangGraph 等框架做好准备：

| v0 组件 | v1 框架对应 |
|---------|-------------|
| AgentState | State schema |
| Node | Graph node |
| Tools | Tool binding |
| action_ledger | Checkpointer |
| run_id | Thread ID |

迁移时只需：
1. 替换编排层 wiring
2. nodes/tools 代码复用
3. 添加 checkpointer 持久化

