# infoSentry API Contracts v0

## Purpose

infoSentry 是一个信息追踪 Agent 系统。本规格定义其 REST API 契约，覆盖认证、Goal 管理、信息源管理、通知投递、反馈回路、Agent 可观测性及管理接口。所有端点均服务于核心流程：抓取多信息源 -> 语义匹配 Goal -> 三层推送决策（Immediate/Batch/Digest）-> 邮件推送。

---

## Response Envelope

### REQ-ENV-1: 统一成功响应信封

所有成功响应 MUST 包裹在统一的信封结构中，包含 `code`、`message`、`data`、`meta` 四个顶层字段。

#### Scenario: 成功响应信封格式

```
Given 任意 API 端点返回 2xx 成功响应
When 客户端解析响应体
Then 响应体 MUST 符合以下结构：
```

```json
{
  "code": 200,
  "message": "Operation successful",
  "data": { "..." },
  "meta": { "..." }
}
```

### REQ-ENV-2: 信封豁免

重定向响应（如 `GET /r/{item_id}`）与 `204 No Content` 响应 SHALL NOT 使用信封包裹。

> **注**：本文档后续成功响应示例默认展示 `data` 字段内容，除非特别说明。

---

## Auth

### REQ-AUTH-1: 请求 Magic Link 登录

系统 MUST 提供 `POST /api/auth/request_link` 端点，接受用户邮箱并发送 Magic Link 登录链接。

#### Scenario: 请求发送 Magic Link

```
Given 用户提供有效邮箱
When 发送 POST /api/auth/request_link 请求：
```

```json
{
  "email": "user@example.com"
}
```

```
Then 系统 MUST 返回发送确认：
```

```json
{
  "ok": true,
  "message": "登录链接已发送到邮箱"
}
```

---

### REQ-AUTH-2: 消费 Magic Link Token

系统 MUST 提供 `GET /api/auth/consume?token=...` 端点，验证 Magic Link Token 并返回会话信息。

#### Scenario: 使用有效 Token 登录

```
Given 用户收到有效的 Magic Link
When 发送 GET /api/auth/consume?token=<valid_token> 请求
Then 系统 MUST 返回会话信息，包含 user_id、email、access_token 和过期时间：
```

```json
{
  "ok": true,
  "session": {
    "user_id": "uuid",
    "email": "user@example.com",
    "access_token": "jwt...",
    "expires_at": "2025-01-28T00:00:00Z"
  }
}
```

---

### REQ-AUTH-3: 刷新会话 Token

系统 MUST 提供 `POST /api/auth/refresh` 端点，通过 httpOnly refresh cookie 刷新访问令牌。

#### Scenario: 成功刷新 Token

```
Given 用户持有有效的 httpOnly refresh cookie
When 发送 POST /api/auth/refresh 请求
Then 系统 MUST 返回新的 access_token 和过期时间：
```

```json
{
  "ok": true,
  "access_token": "jwt...",
  "expires_at": "2025-01-28T00:00:00Z"
}
```

#### Scenario: 刷新失败

```
Given 用户的 refresh cookie 无效或已过期
When 发送 POST /api/auth/refresh 请求
Then 系统 MUST 返回以下错误码之一：
  - REFRESH_TOKEN_MISSING — cookie 中无 refresh token
  - DEVICE_SESSION_NOT_FOUND — 设备会话不存在
  - DEVICE_SESSION_EXPIRED — 设备会话已过期
  - DEVICE_SESSION_REVOKED — 设备会话已被撤销
  - DEVICE_SESSION_RISK — 设备会话存在风险
```

---

### REQ-AUTH-4: 退出登录

系统 MUST 提供 `POST /api/auth/logout` 端点，撤销 refresh 会话并清除 cookie。

#### Scenario: 成功退出登录

```
Given 用户已登录
When 发送 POST /api/auth/logout 请求
Then 系统 MUST 撤销 refresh 会话并清除 cookie
And 返回退出确认：
```

```json
{
  "ok": true,
  "message": "已退出登录"
}
```

---

## Goals

### REQ-GOAL-1: 获取用户所有 Goals

系统 MUST 提供 `GET /api/goals` 端点，返回当前用户的全部 Goal 列表。

#### Scenario: 获取 Goal 列表

```
Given 用户已认证
When 发送 GET /api/goals 请求
Then 系统 MUST 返回该用户的所有 Goal，每个 Goal 包含 id、name、description、priority_mode、status、created_at：
```

```json
{
  "goals": [
    {
      "id": "uuid",
      "name": "AI 行业动态",
      "description": "追踪 AI 领域重要新闻",
      "priority_mode": "STRICT",
      "status": "ACTIVE",
      "created_at": "2025-12-28T00:00:00Z"
    }
  ]
}
```

---

### REQ-GOAL-2: 创建新 Goal

系统 MUST 提供 `POST /api/goals` 端点，创建新的 Goal。请求 MUST 包含 name；description、priority_mode、priority_terms、negative_terms、batch_windows、digest_send_time 为可选字段。

#### Scenario: 成功创建 Goal

```
Given 用户已认证
When 发送 POST /api/goals 请求：
```

```json
{
  "name": "AI 行业动态",
  "description": "追踪 AI 领域的重要新闻和技术突破",
  "priority_mode": "STRICT",
  "priority_terms": ["GPT", "Claude", "LLM", "大模型"],
  "negative_terms": ["广告", "招聘"],
  "batch_windows": ["12:30", "18:30"],
  "digest_send_time": "09:00"
}
```

```
Then 系统 MUST 创建 Goal 并返回 id、name、created_at：
```

```json
{
  "id": "uuid",
  "name": "AI 行业动态",
  "created_at": "2025-12-28T00:00:00Z"
}
```

---

### REQ-GOAL-3: 获取单个 Goal 详情

系统 MUST 提供 `GET /api/goals/{id}` 端点，返回指定 Goal 的完整详情，包括统计摘要。

#### Scenario: 获取 Goal 详情

```
Given 用户已认证
And 存在 id 为 {id} 的 Goal 属于该用户
When 发送 GET /api/goals/{id} 请求
Then 系统 MUST 返回 Goal 的完整信息，包含配置字段和匹配统计：
```

```json
{
  "id": "uuid",
  "name": "AI 行业动态",
  "description": "追踪 AI 领域的重要新闻和技术突破",
  "priority_mode": "STRICT",
  "priority_terms": ["GPT", "Claude", "LLM", "大模型"],
  "negative_terms": ["广告", "招聘"],
  "batch_windows": ["12:30", "18:30"],
  "digest_send_time": "09:00",
  "status": "ACTIVE",
  "stats": {
    "total_matches": 156,
    "immediate_count": 12,
    "batch_count": 89,
    "digest_count": 55
  },
  "created_at": "2025-12-28T00:00:00Z",
  "updated_at": "2025-12-28T00:00:00Z"
}
```

---

### REQ-GOAL-4: 更新 Goal

系统 MUST 提供 `PUT /api/goals/{id}` 端点，支持部分更新 Goal 的可变字段。

#### Scenario: 更新 Goal 字段

```
Given 用户已认证
And 存在 id 为 {id} 的 Goal 属于该用户
When 发送 PUT /api/goals/{id} 请求，仅包含需要更新的字段：
```

```json
{
  "name": "AI 行业动态（更新）",
  "priority_terms": ["GPT", "Claude", "LLM", "大模型", "Gemini"]
}
```

```
Then 系统 MUST 仅更新请求中提供的字段，保留其他字段不变
```

---

### REQ-GOAL-5: 暂停 Goal

系统 MUST 提供 `POST /api/goals/{id}/pause` 端点，将 Goal 状态切换为 PAUSED。

#### Scenario: 暂停活跃的 Goal

```
Given 用户已认证
And 存在 id 为 {id} 的 Goal，状态为 ACTIVE
When 发送 POST /api/goals/{id}/pause 请求
Then 系统 MUST 将 Goal 状态更新为 PAUSED 并返回确认：
```

```json
{
  "ok": true,
  "status": "PAUSED"
}
```

---

### REQ-GOAL-6: 恢复 Goal

系统 MUST 提供 `POST /api/goals/{id}/resume` 端点，将 Goal 状态从 PAUSED 恢复为 ACTIVE。

#### Scenario: 恢复已暂停的 Goal

```
Given 用户已认证
And 存在 id 为 {id} 的 Goal，状态为 PAUSED
When 发送 POST /api/goals/{id}/resume 请求
Then 系统 MUST 将 Goal 状态恢复为 ACTIVE 并返回确认：
```

```json
{
  "ok": true,
  "status": "ACTIVE"
}
```

---

## Sources

### REQ-SRC-1: 获取信息源列表

系统 MUST 提供 `GET /api/sources` 端点，返回信息源列表，支持按类型过滤。

NEWSNOW 默认公共源 SHALL 在服务启动后自动对齐上游目录（`shared/sources.json`），并出现在公共源列表中。

#### Scenario: 获取所有信息源

```
Given 用户已认证
When 发送 GET /api/sources 请求
Then 系统 MUST 返回该用户可见的全部信息源列表
```

#### Scenario: 按类型过滤信息源

```
Given 用户已认证
When 发送 GET /api/sources?type=NEWSNOW 请求
Then 系统 MUST 仅返回类型为 NEWSNOW 的信息源
```

`type` 查询参数 MAY 取值：`NEWSNOW` | `RSS` | `SITE`。

响应格式：

```json
{
  "sources": [
    {
      "id": "uuid",
      "type": "NEWSNOW",
      "name": "Reuters Tech",
      "enabled": true,
      "last_fetch_at": "2025-12-28T10:00:00Z",
      "error_streak": 0,
      "config": {
        "base_url": "https://newsnow.busiyi.world",
        "source_id": "reuters-tech"
      }
    }
  ]
}
```

---

### REQ-SRC-2: 创建信息源

系统 MUST 提供 `POST /api/sources` 端点，支持创建 NEWSNOW、RSS、SITE 三种类型的信息源。请求 MUST 包含 `type`、`name` 和对应类型的 `config`。

#### Scenario: 创建 NEWSNOW 类型信息源

```
Given 用户已认证
When 发送 POST /api/sources 请求，type 为 NEWSNOW：
```

```json
{
  "type": "NEWSNOW",
  "name": "NewsNow | Github",
  "config": {
    "base_url": "https://newsnow.busiyi.world",
    "api_path": "/api/s",
    "source_id": "github",
    "latest": false
  }
}
```

```
Then 系统 MUST 创建信息源并返回创建结果
```

#### Scenario: 创建 RSS 类型信息源

```
Given 用户已认证
When 发送 POST /api/sources 请求，type 为 RSS：
```

```json
{
  "type": "RSS",
  "name": "Hacker News",
  "config": {
    "feed_url": "https://news.ycombinator.com/rss"
  }
}
```

```
Then 系统 MUST 创建信息源并返回创建结果
```

#### Scenario: 创建 SITE 类型信息源（list-only）

```
Given 用户已认证
When 发送 POST /api/sources 请求，type 为 SITE：
```

```json
{
  "type": "SITE",
  "name": "TechCrunch",
  "config": {
    "list_url": "https://techcrunch.com",
    "selectors": {
      "item": "article.post-block",
      "title": "h2.post-block__title a",
      "link": "h2.post-block__title a",
      "snippet": "div.post-block__content"
    }
  }
}
```

```
Then 系统 MUST 创建信息源并返回创建结果
```

---

### REQ-SRC-3: 更新信息源

系统 MUST 提供 `PUT /api/sources/{id}` 端点，支持更新信息源配置。

#### Scenario: 更新信息源配置

```
Given 用户已认证
And 存在 id 为 {id} 的信息源属于该用户
When 发送 PUT /api/sources/{id} 请求，包含需要更新的字段
Then 系统 MUST 更新对应信息源的配置
```

---

### REQ-SRC-4: 启用信息源

系统 MUST 提供 `POST /api/sources/{id}/enable` 端点，启用指定信息源。

#### Scenario: 启用已禁用的信息源

```
Given 用户已认证
And 存在 id 为 {id} 的信息源，当前 enabled 为 false
When 发送 POST /api/sources/{id}/enable 请求
Then 系统 MUST 将该信息源的 enabled 设为 true
```

---

### REQ-SRC-5: 禁用信息源

系统 MUST 提供 `POST /api/sources/{id}/disable` 端点，禁用指定信息源。

#### Scenario: 禁用已启用的信息源

```
Given 用户已认证
And 存在 id 为 {id} 的信息源，当前 enabled 为 true
When 发送 POST /api/sources/{id}/disable 请求
Then 系统 MUST 将该信息源的 enabled 设为 false
```

---

## Notifications

### REQ-NOTIF-1: 获取通知列表

系统 MUST 提供 `GET /api/notifications` 端点，返回通知列表，支持游标分页和多条件过滤。

查询参数：
- `goal_id` — 过滤特定 Goal（MAY 省略）
- `cursor` — 分页游标（MAY 省略）
- `status` — 过滤状态，取值 `PENDING` | `SENT` | `READ`（MAY 省略）

#### Scenario: 获取通知列表（含游标分页）

```
Given 用户已认证
When 发送 GET /api/notifications 请求（可携带 goal_id、cursor、status 查询参数）
Then 系统 MUST 返回通知列表，每条通知 MUST 包含以下嵌套结构：
  - 通知元数据：id, goal_id, item_id, decision, status, channel, decided_at, sent_at
  - item 对象：title, url, source_name, published_at, snippet
  - reason 对象：summary, score, evidence 数组
  - actions 数组：每个 action 包含 type 及可选 url
And 响应 MUST 包含 next_cursor 和 has_more 分页字段
```

响应格式：

```json
{
  "notifications": [
    {
      "id": "uuid",
      "goal_id": "uuid",
      "item_id": "uuid",
      "decision": "IMMEDIATE",
      "status": "SENT",
      "channel": "EMAIL",
      "item": {
        "title": "OpenAI 发布 GPT-5",
        "url": "https://example.com/news/gpt5",
        "source_name": "Reuters",
        "published_at": "2025-12-28T08:00:00Z",
        "snippet": "OpenAI 今日正式发布了备受期待的 GPT-5..."
      },
      "reason": {
        "summary": "命中核心关键词「GPT」，来源可信度高",
        "score": 0.95,
        "evidence": [
          {
            "type": "TERM_HIT",
            "value": "GPT-5",
            "quote": "OpenAI 发布 GPT-5",
            "ref": {"field": "title"}
          },
          {
            "type": "SOURCE",
            "value": "Reuters",
            "ref": {"field": "source"}
          }
        ]
      },
      "actions": [
        {"type": "OPEN", "url": "/r/item-uuid?goal_id=...&channel=email"},
        {"type": "LIKE"},
        {"type": "DISLIKE"},
        {"type": "BLOCK_SOURCE"}
      ],
      "decided_at": "2025-12-28T08:05:00Z",
      "sent_at": "2025-12-28T08:06:00Z"
    }
  ],
  "next_cursor": "cursor_token",
  "has_more": true
}
```

---

## Feedback & Click Tracking

### REQ-FB-1: 提交反馈

系统 MUST 提供 `POST /api/items/{item_id}/feedback` 端点，接受用户对匹配结果的反馈。

`feedback` 字段 MUST 取值 `LIKE`（有价值）或 `DISLIKE`（不相关）。`block_source` MAY 设为 `true` 以屏蔽该信息源。

#### Scenario: 提交正向反馈

```
Given 用户已认证
And 存在 item_id 为 {item_id} 的匹配条目
When 发送 POST /api/items/{item_id}/feedback 请求：
```

```json
{
  "goal_id": "uuid",
  "feedback": "LIKE",
  "block_source": false
}
```

```
Then 系统 MUST 记录反馈并返回确认：
```

```json
{
  "ok": true,
  "feedback_id": "uuid"
}
```

#### Scenario: 提交负向反馈并屏蔽来源

```
Given 用户已认证
And 存在 item_id 为 {item_id} 的匹配条目
When 发送 POST /api/items/{item_id}/feedback 请求，feedback 为 DISLIKE 且 block_source 为 true
Then 系统 MUST 记录反馈
And 系统 SHOULD 将该信息源标记为用户屏蔽
```

---

### REQ-FB-2: 点击跟踪与重定向

系统 MUST 提供 `GET /r/{item_id}` 端点，记录点击事件后重定向到原文 URL。

查询参数：
- `goal_id` — 关联的 Goal（SHOULD 提供）
- `channel` — 点击来源渠道，如 `email`（SHOULD 提供）

#### Scenario: 点击跟踪并重定向

```
Given 存在 item_id 为 {item_id} 的条目，其原文 URL 为 https://example.com/article
When 发送 GET /r/{item_id}?goal_id=...&channel=email 请求
Then 系统 MUST 记录 click_event
And 系统 MUST 返回 302 Redirect 到 item.url
```

---

## Replay & Observability

### REQ-REPLAY-1: 获取 Agent 运行记录列表

系统 MUST 提供 `GET /api/agent/runs` 端点，返回 Agent 运行记录列表，支持游标分页和多条件过滤。

查询参数：
- `goal_id` — 过滤特定 Goal（MAY 省略）
- `cursor` — 分页游标（MAY 省略）
- `status` — 过滤运行状态，取值 `SUCCESS` | `ERROR` | `FALLBACK`（MAY 省略）

#### Scenario: 获取运行记录列表

```
Given 用户已认证
When 发送 GET /api/agent/runs 请求（可携带 goal_id、cursor、status 查询参数）
Then 系统 MUST 返回运行记录列表，每条记录包含 id、trigger、goal_id、status、llm_used、model_name、latency_ms、created_at
And 响应 MUST 包含 next_cursor 分页字段
```

```json
{
  "runs": [
    {
      "id": "uuid",
      "trigger": "MatchComputed",
      "goal_id": "uuid",
      "status": "SUCCESS",
      "llm_used": true,
      "model_name": "gpt-4o-mini",
      "latency_ms": 1234,
      "created_at": "2025-12-28T08:05:00Z"
    }
  ],
  "next_cursor": "cursor_token"
}
```

---

### REQ-REPLAY-2: 获取 Agent 运行详情

系统 MUST 提供 `GET /api/agent/runs/{run_id}` 端点，返回单次 Agent 运行的完整详情，包含 tool_calls 和 action_ledger。

#### Scenario: 获取运行详情

```
Given 用户已认证
And 存在 run_id 为 {run_id} 的运行记录
When 发送 GET /api/agent/runs/{run_id} 请求
Then 系统 MUST 返回完整运行详情，包含以下部分：
  - 基础信息：id, trigger, goal_id, status, llm_used, model_name, latency_ms, created_at
  - input_snapshot：运行输入快照（goal, item, match, budget）
  - output_snapshot：运行输出快照（decision, reason）
  - final_actions：最终执行的动作列表
  - budget_snapshot：预算快照（usd_est_today, judge_calls_today）
  - tool_calls：工具调用链，每条包含 id, tool_name, input, output, status, latency_ms
  - action_ledger：动作账本，每条包含 id, action_type, payload, created_at
```

```json
{
  "id": "uuid",
  "trigger": "MatchComputed",
  "goal_id": "uuid",
  "status": "SUCCESS",
  "input_snapshot": {
    "goal": {"id": "...", "name": "..."},
    "item": {"id": "...", "title": "..."},
    "match": {"score": 0.91},
    "budget": {"judge_disabled": false}
  },
  "output_snapshot": {
    "decision": "IMMEDIATE",
    "reason": "..."
  },
  "final_actions": [
    {
      "type": "EMIT_DECISION",
      "payload": {"decision": "IMMEDIATE", "goal_id": "...", "item_id": "..."}
    }
  ],
  "budget_snapshot": {
    "usd_est_today": 0.15,
    "judge_calls_today": 45
  },
  "llm_used": true,
  "model_name": "gpt-4o-mini",
  "latency_ms": 1234,
  "created_at": "2025-12-28T08:05:00Z",
  "tool_calls": [
    {
      "id": "uuid",
      "tool_name": "get_goal_context",
      "input": {"goal_id": "..."},
      "output": {"name": "...", "priority_terms": ["..."]},
      "status": "SUCCESS",
      "latency_ms": 12
    },
    {
      "id": "uuid",
      "tool_name": "emit_decision",
      "input": {"decision": "IMMEDIATE", "goal_id": "...", "item_id": "..."},
      "output": {"ok": true},
      "status": "SUCCESS",
      "latency_ms": 45
    }
  ],
  "action_ledger": [
    {
      "id": "uuid",
      "action_type": "EMIT_DECISION",
      "payload": {"decision": "IMMEDIATE", "goal_id": "...", "item_id": "..."},
      "created_at": "2025-12-28T08:05:01Z"
    }
  ]
}
```

---

## Admin

### REQ-ADMIN-1: 获取预算状态

系统 MAY 提供 `GET /api/admin/budget` 端点，返回当日 AI 用量预算状态。此端点为管理员功能。

#### Scenario: 查看当日预算状态

```
Given 管理员已认证
When 发送 GET /api/admin/budget 请求
Then 系统 MUST 返回当日预算状态，包含 token 用量估算、费用估算及各功能开关状态：
```

```json
{
  "date": "2025-12-28",
  "embedding_tokens_est": 150000,
  "judge_tokens_est": 25000,
  "usd_est": 0.18,
  "embedding_disabled": false,
  "judge_disabled": false,
  "daily_limit": 0.33
}
```

---

### REQ-ADMIN-2: 热更新配置

系统 MAY 提供 `POST /api/admin/config` 端点，支持运行时热更新系统配置。此端点为管理员功能。

#### Scenario: 热更新系统配置

```
Given 管理员已认证
When 发送 POST /api/admin/config 请求，包含需要更新的配置键值对：
```

```json
{
  "LLM_ENABLED": false
}
```

```
Then 系统 MUST 立即应用新配置，无需重启服务
```

---

## Error Handling

### REQ-ERR-1: 统一错误响应格式

所有 API 错误 MUST 返回统一的错误信封格式，包含 `error` 顶层字段，其内包含 `code`、`message` 和可选的 `details`。

#### Scenario: 错误响应结构

```
Given 任意 API 端点发生错误
When 系统返回错误响应
Then 响应体 MUST 符合以下结构：
```

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid email format",
    "details": {
      "field": "email",
      "value": "invalid"
    }
  }
}
```

### REQ-ERR-2: 标准错误码

系统 MUST 使用以下标准错误码：

| 错误码 | 含义 |
|--------|------|
| `VALIDATION_ERROR` | 请求参数验证失败 |
| `NOT_FOUND` | 资源不存在 |
| `UNAUTHORIZED` | 未认证 |
| `FORBIDDEN` | 无权限 |
| `RATE_LIMITED` | 请求过于频繁 |
| `INTERNAL_ERROR` | 服务器内部错误 |

#### Scenario: 验证错误

```
Given 客户端发送了包含无效参数的请求
When 服务端验证请求参数
Then 系统 MUST 返回 error.code 为 VALIDATION_ERROR
And error.details SHOULD 包含具体的 field 和 value 信息
```

#### Scenario: 资源不存在

```
Given 客户端请求了不存在的资源（如无效的 Goal ID）
When 服务端查找资源
Then 系统 MUST 返回 error.code 为 NOT_FOUND
```

#### Scenario: 未认证访问

```
Given 客户端未提供有效的认证凭证
When 访问需要认证的端点
Then 系统 MUST 返回 error.code 为 UNAUTHORIZED
```

#### Scenario: 请求限流

```
Given 客户端在短时间内发送了过多请求
When 系统检测到超过速率限制
Then 系统 MUST 返回 error.code 为 RATE_LIMITED
```
