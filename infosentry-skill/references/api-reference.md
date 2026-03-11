# infoSentry API Reference

## Authentication

All API requests require an API Key passed via the `X-API-Key` header:

```
X-API-Key: isk_YOUR_KEY_HERE
```

## Base URL

```
{BASE_URL}/api/v1
```

## Response Format

All responses follow this structure:

```json
{
  "code": 200,
  "message": "Operation successful",
  "data": { ... },
  "meta": { "total": 100, "page": 1, "page_size": 20 }
}
```

---

## Goals

### List Goals

```
GET /goals?status={status}&page={page}&page_size={page_size}
```

**Scope**: `goals:read`

| Parameter | Type | Description |
|-----------|------|-------------|
| status | string | Filter: `active`, `paused`, `archived` |
| page | int | Page number (default: 1) |
| page_size | int | Items per page (default: 20) |

### Get Goal Detail

```
GET /goals/{goal_id}
```

**Scope**: `goals:read`

### Create Goal

```
POST /goals
```

**Scope**: `goals:write`

```json
{
  "name": "AI 行业动态",
  "description": "追踪 AI 领域的重要新闻",
  "priority_mode": "SOFT",
  "priority_terms": ["GPT", "Claude"],
  "negative_terms": ["广告"]
}
```

### Update Goal

```
PUT /goals/{goal_id}
```

**Scope**: `goals:write`

### Delete Goal

```
DELETE /goals/{goal_id}
```

**Scope**: `goals:write`

### Pause / Resume Goal

```
POST /goals/{goal_id}/pause
POST /goals/{goal_id}/resume
```

**Scope**: `goals:write`

### Get Goal Matches

```
GET /goals/{goal_id}/matches?min_score={score}&rank_mode={rank_mode}&page={page}&page_size={page_size}
```

**Scope**: `goals:read`

| Parameter | Type | Description |
|-----------|------|-------------|
| min_score | float | Minimum match score, 0.0–1.0 |
| rank_mode | string | Ranking mode (optional) |
| half_life_days | float | Half-life for time decay (optional) |
| page | int | Page number (default: 1) |
| page_size | int | Items per page (default: 20) |

### Suggest Keywords (AI)

```
POST /goals/suggest-keywords
```

**Scope**: `goals:write`

```json
{
  "description": "追踪 AI 领域的最新研究进展和产品发布",
  "max_keywords": 5
}
```

Response:

```json
{
  "code": 200,
  "data": {
    "keywords": ["AI", "LLM", "GPT", "机器学习", "深度学习"]
  }
}
```

### Generate Goal Draft (AI)

```
POST /goals/generate-draft
```

**Scope**: `goals:write`

```json
{
  "intent": "我想关注 AI 行业的最新动态",
  "max_keywords": 5
}
```

Response:

```json
{
  "code": 200,
  "data": {
    "name": "AI 行业动态",
    "description": "追踪 AI 领域的重要新闻和产品发布",
    "keywords": ["AI", "LLM", "GPT"]
  }
}
```

### Send Goal Email

```
POST /goals/{goal_id}/send-email
```

**Scope**: `goals:write`

```json
{
  "since": "2026-03-01T00:00:00Z",
  "min_score": 0.0,
  "limit": 20,
  "include_sent": false,
  "dry_run": false
}
```

Response:

```json
{
  "code": 200,
  "data": {
    "success": true,
    "email_sent": true,
    "items_count": 5,
    "decisions_updated": 5,
    "preview": {
      "subject": "infoSentry: AI 行业动态 — 5 条新匹配",
      "to_email": "user@example.com",
      "item_titles": ["..."]
    },
    "message": "Email sent successfully"
  }
}
```

> Set `dry_run: true` to preview without actually sending.

---

## Sources

### List Public Sources

```
GET /sources/public?page={page}&page_size={page_size}
```

**Scope**: `sources:read`

### List My Sources

```
GET /sources?page={page}&page_size={page_size}
```

**Scope**: `sources:read`

### Get Source Detail

```
GET /sources/{source_id}
```

**Scope**: `sources:read`

### Create Source

```
POST /sources
```

**Scope**: `sources:write`

```json
{
  "type": "RSS",
  "name": "Hacker News",
  "is_private": false,
  "config": {
    "url": "https://news.ycombinator.com/rss"
  },
  "fetch_interval_sec": 900
}
```

### Update Source

```
PUT /sources/{source_id}
```

**Scope**: `sources:write`

```json
{
  "name": "Updated Name",
  "config": { "url": "https://example.com/rss" },
  "fetch_interval_sec": 1800
}
```

> All fields are optional; only provided fields will be updated.

### Subscribe to Source

```
POST /sources/{source_id}/subscribe
```

**Scope**: `sources:write`

### Unsubscribe from Source

```
DELETE /sources/{source_id}
```

**Scope**: `sources:write`

### Enable / Disable Source

```
POST /sources/{source_id}/enable
POST /sources/{source_id}/disable
```

**Scope**: `sources:write`

---

## Notifications / Push

### List Notifications (Inbox)

```
GET /notifications?cursor={cursor}&goal_id={goal_id}&status={status}
```

**Scope**: `notifications:read`

### Mark as Read

```
POST /notifications/{notification_id}/read
```

**Scope**: `notifications:write`

### Submit Feedback

```
POST /items/{item_id}/feedback
```

**Scope**: `notifications:write`

```json
{
  "goal_id": "goal_456",
  "feedback": "LIKE",
  "block_source": false
}
```

### Track Click (Redirect)

```
GET /r/{item_id}?goal_id={goal_id}&channel={channel}
```

**Auth**: None (public endpoint)

Records a click event and returns an HTTP 302 redirect to the original item URL.

| Parameter | Type | Description |
|-----------|------|-------------|
| goal_id | string | Associated goal (optional) |
| channel | string | Click source channel (optional) |

---

## API Key Scopes

| Scope | Description |
|-------|-------------|
| `goals:read` | Read goals and matches |
| `goals:write` | Create, update, delete goals; AI suggestions; send email |
| `sources:read` | Read sources |
| `sources:write` | Create, update, subscribe/unsubscribe, enable/disable sources |
| `notifications:read` | Read notifications |
| `notifications:write` | Mark read, submit feedback |
| `agent:read` | Read agent run history |
| `admin:read` | Read admin data |
| `admin:write` | Write admin data |
