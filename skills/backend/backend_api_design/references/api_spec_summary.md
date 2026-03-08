# API Spec Summary (infoSentry v0)

Source of truth: `specs/API_SPEC_v0.md`.

## Base
- All API endpoints are under `/api` except redirect tracking under `/r/{item_id}`.
- Error response format:
  - `{ "error": { "code": "...", "message": "...", "details": {...} } }`
  - Common codes: `VALIDATION_ERROR`, `NOT_FOUND`, `UNAUTHORIZED`, `FORBIDDEN`, `RATE_LIMITED`, `INTERNAL_ERROR`.

## Existing endpoints (overview)

### Auth
- `POST /api/auth/request_link`: request magic link.
- `GET /api/auth/consume?token=...`: consume magic link.

### Goals
- `GET /api/goals`: list goals.
- `POST /api/goals`: create goal.
- `GET /api/goals/{id}`: goal detail.
- `PUT /api/goals/{id}`: update goal.
- `POST /api/goals/{id}/pause`: pause goal.
- `POST /api/goals/{id}/resume`: resume goal.

### Sources
- `GET /api/sources?type=`: list sources by type.
- `POST /api/sources`: create source (NEWSNOW | RSS | SITE).
- `PUT /api/sources/{id}`: update source.
- `POST /api/sources/{id}/enable`: enable source.
- `POST /api/sources/{id}/disable`: disable source.

### Notifications
- `GET /api/notifications?goal_id=&cursor=&status=`: list notifications.

### Feedback & Click
- `POST /api/items/{item_id}/feedback`: submit feedback.
- `GET /r/{item_id}?goal_id=...&channel=...`: click tracking + 302 redirect.

### Agent Runs
- `GET /api/agent/runs?goal_id=&cursor=&status=`: list runs.
- `GET /api/agent/runs/{run_id}`: run detail.

### Admin (optional)
- `GET /api/admin/budget`: budget state.
- `POST /api/admin/config`: hot config update.

## Response patterns (examples)
- Lists typically use `next_cursor` and `has_more`.
- Notification response includes nested `item`, `reason`, `actions`.
