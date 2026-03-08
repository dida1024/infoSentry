---
name: backend_api_design
description: Design and add HTTP API endpoints for infoSentry backend (FastAPI + DDD). Use for API specs and implementing routes/schemas with proper layering.
---

# Backend API Design (infoSentry)

Follow hard rules in `AGENTS.md`.

## Read first (only what you need)
- `references/api_spec_summary.md`: source-of-truth summary of existing endpoints, response patterns, error format.
- `references/backend_conventions_summary.md`: DDD + Python/FastAPI conventions. If it conflicts with API_SPEC, follow API_SPEC and call out the conflict in Notes.
- `references/endpoint_placement.md`: where to place routers/schemas.
- `references/api_contract_summary.md`: shared contract rules for errors/pagination.
- `references/api_anti_patterns.md`: common API mistakes to avoid.
- `docs/decisions/DECISIONS.md` and `docs/decisions/ARCHITECTURE_DECISIONS.md` for defaults (timezones, idempotency, queues).

## Design rules
- Match existing URL patterns and resource naming (prefer RESTful paths; keep `/api` prefix, `/r` for redirect tracking).
- Keep business logic out of routers/controllers; design for DDD boundaries (interfaces -> application -> domain).
- Be explicit about auth, permissions, and idempotency.
- Use cursor pagination when listing potentially large sets (align with `cursor`, `next_cursor`, `has_more`).
- Use the project error format from `specs/API_SPEC_v0.md`.
- Default invariants: IDs are string UUIDs; timestamps UTC with timezone; soft delete via `is_deleted`; dedupe keys where specified in ADRs.
- No hardcoded config values; read from settings/env and inject via DI.
- Log key actions via structlog (include goal_id/item_id/dedupe_key where applicable).

## Output (concise, in order)
- Endpoint: `METHOD /path`
- Auth: required/optional + mechanism (token, session, etc.)
- Request schema: fields + validation rules (required/optional, constraints)
- Response schema: fields + example payload
- Errors: `code`, `message`, and when thrown (use project error codes)
- Pagination/filtering: query params + rules (cursor, filters, sorting)
- Side effects: events/tasks/logging
- Notes: migrations/indexing/cache/backward-compat + conflicts with conventions

## Implementation scope
- Add/modify FastAPI routes and schemas in the correct module.
- Route layer only handles validation, DI, and orchestration.
- Application/domain/infrastructure changes as needed for the endpoint.

## When missing info
- Ask 3–5 targeted questions (business goal, resource, auth, pagination, side effects).
