# API contract summary (infoSentry)

- Prefer RESTful paths: list/create/update/detail.
- Error format uses `{ "error": { "code", "message", "details" } }`.
- Use cursor pagination for large lists (cursor/next_cursor/has_more).
