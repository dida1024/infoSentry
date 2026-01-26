# infoSentry API Spec v0（摘要）

> v0 以"够用"为主，后续可补 OpenAPI 文档页面

---

## 0. Success Response Envelope

实际实现中，成功响应统一包裹为：

```json
{
  "code": 200,
  "message": "Operation successful",
  "data": { ... },
  "meta": { ... }
}
```

为便于阅读，本文档中的成功响应示例默认展示 `data` 内容（除非特别说明）。
重定向（如 `/r/{item_id}`）与 `204 No Content` 响应不适用。

## 1. Auth

### POST /api/auth/request_link
请求 Magic Link 登录

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "ok": true,
  "message": "登录链接已发送到邮箱"
}
```

---

### GET /api/auth/consume?token=...
消费 Magic Link Token

**Response:**
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

### POST /api/auth/refresh
刷新登录会话（使用 httpOnly refresh cookie）

**Response:**
```json
{
  "ok": true,
  "access_token": "jwt...",
  "expires_at": "2025-01-28T00:00:00Z"
}
```

**Error codes:**
- `REFRESH_TOKEN_MISSING`
- `DEVICE_SESSION_NOT_FOUND`
- `DEVICE_SESSION_EXPIRED`
- `DEVICE_SESSION_REVOKED`
- `DEVICE_SESSION_RISK`

---

### POST /api/auth/logout
退出登录（撤销 refresh 会话并清除 cookie）

**Response:**
```json
{
  "ok": true,
  "message": "已退出登录"
}
```

---

## 2. Goals

### GET /api/goals
获取用户所有 Goals

**Response:**
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

### POST /api/goals
创建新 Goal

**Request:**
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

**Response:**
```json
{
  "id": "uuid",
  "name": "AI 行业动态",
  "created_at": "2025-12-28T00:00:00Z"
}
```

---

### GET /api/goals/{id}
获取单个 Goal 详情

**Response:**
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

### PUT /api/goals/{id}
更新 Goal

**Request:**
```json
{
  "name": "AI 行业动态（更新）",
  "priority_terms": ["GPT", "Claude", "LLM", "大模型", "Gemini"]
}
```

---

### POST /api/goals/{id}/pause
暂停 Goal

**Response:**
```json
{
  "ok": true,
  "status": "PAUSED"
}
```

---

### POST /api/goals/{id}/resume
恢复 Goal

**Response:**
```json
{
  "ok": true,
  "status": "ACTIVE"
}
```

---

## 3. Sources

### GET /api/sources?type=
获取信息源列表

**Query Params:**
- `type`: NEWSNOW | RSS | SITE（可选）

**Response:**
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

### POST /api/sources
创建信息源

**Request (NEWSNOW):**
```json
{
  "type": "NEWSNOW",
  "name": "Reuters Tech",
  "config": {
    "base_url": "https://newsnow.busiyi.world",
    "source_id": "reuters-tech"
  }
}
```

**Request (RSS):**
```json
{
  "type": "RSS",
  "name": "Hacker News",
  "config": {
    "feed_url": "https://news.ycombinator.com/rss"
  }
}
```

**Request (SITE, list-only):**
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

---

### PUT /api/sources/{id}
更新信息源

---

### POST /api/sources/{id}/enable
启用信息源

---

### POST /api/sources/{id}/disable
禁用信息源

---

## 4. Inbox / Notifications

### GET /api/notifications?goal_id=&cursor=
获取通知列表

**Query Params:**
- `goal_id`: 过滤特定 Goal（可选）
- `cursor`: 分页游标（可选）
- `status`: PENDING | SENT | READ（可选）

**Response:**
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

## 5. Feedback & Click

### POST /api/items/{item_id}/feedback
提交反馈

**Request:**
```json
{
  "goal_id": "uuid",
  "feedback": "LIKE",
  "block_source": false
}
```

**feedback 取值:**
- `LIKE`: 有价值
- `DISLIKE`: 不相关

**Response:**
```json
{
  "ok": true,
  "feedback_id": "uuid"
}
```

---

### GET /r/{item_id}?goal_id=...&channel=email
点击跟踪 & 重定向

记录 click_events 后 302 跳转到原文 URL

**Response:**
- 302 Redirect to `item.url`

---

## 6. Replay / Observability

### GET /api/agent/runs?goal_id=&cursor=
获取 Agent 运行记录

**Query Params:**
- `goal_id`: 过滤特定 Goal（可选）
- `cursor`: 分页游标
- `status`: SUCCESS | ERROR | FALLBACK（可选）

**Response:**
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

### GET /api/agent/runs/{run_id}
获取 Agent 运行详情

**Response:**
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

## 7. Admin（可选）

### GET /api/admin/budget
获取预算状态

**Response:**
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

### POST /api/admin/config
热更新配置

**Request:**
```json
{
  "LLM_ENABLED": false
}
```

---

## 8. Error Response Format

所有 API 错误返回统一格式：

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

**常见错误码:**
- `VALIDATION_ERROR`: 请求参数验证失败
- `NOT_FOUND`: 资源不存在
- `UNAUTHORIZED`: 未认证
- `FORBIDDEN`: 无权限
- `RATE_LIMITED`: 请求过于频繁
- `INTERNAL_ERROR`: 服务器内部错误

