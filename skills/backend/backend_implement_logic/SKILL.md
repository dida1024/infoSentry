---
name: backend_implement_logic
description: Implement or review backend logic with DDD boundaries, async patterns, and repository abstractions.
---

# Backend Implement Logic (Includes Boundary Checks)

Follow hard rules in `AGENTS.md`.

## Read first (only what you need)
- `references/layering_summary.md`
- `references/error_logging_summary.md`
- `references/patterns_summary.md`
- `references/anti_patterns_summary.md`
- `references/boundary_checks.md`
- `docs/decisions/ARCHITECTURE_DECISIONS.md` (schema/queue defaults)
- `docs/decisions/DECISIONS.md` (product/flow defaults)

## Scope
- Implement domain/application/infrastructure logic with correct boundaries.
- Review changes for boundary violations and architectural risks.
- Keep domain pure; application orchestrates; infrastructure integrates.
- Add logging and explicit error handling where needed.

## Python conventions (project default)
- Use async/await by default.
- Full type annotations; prefer Python 3.10+ typing; keep mypy strict (no `# type: ignore` bypass).
- Code style and linting: Ruff (check + format).
- Data validation/models: Pydantic v2 at interfaces layer only; domain uses pure types/value objects.
- If a `while True` loop is unavoidable, add an explicit exit mechanism (cancellation, timeout, sentinel, or backoff with max retries) and document the stop condition.
- Proactively optimize hot paths (batching, pagination, timeouts, and resource limits) to avoid performance regressions.

## Best‑practice defaults (when no project preference)
- Ruff: run both `ruff check` and `ruff format`; avoid ignoring rules unless justified.
- Pydantic: keep it at the edges (interfaces/schemas); avoid Pydantic BaseModel in domain entities unless you need validation/serialization there.

## Project invariants (must preserve)
- IDs: string UUIDs for primary keys.
- Timestamps: `DateTime(timezone=True)` stored in UTC.
- Soft delete: `is_deleted` flag on tables and entities.
- Idempotency keys: dedupe for `push_decisions`, `items` (`url_hash`), `goal_item_matches` (goal+item), `budget_daily` (date).
- Config: never hardcode; read from settings/env and inject.
- Logging: structlog for key business events; include dedupe keys/goal_id/item_id when present.
- Queues: Celery queues `q_ingest`, `q_embed`, `q_match`, `q_agent`, `q_email`; keep related task names consistent.

## Implementation checklist
- Identify which layer owns the change (domain/application/infrastructure).
- Validate boundaries: interfaces -> application -> domain; infra implements ports.
- Domain: enforce business rules, no external deps, raise domain errors.
- Application: orchestrate use-case, manage transaction/UoW, call repositories.
- Infrastructure: implement repositories, DB models, external service adapters.
- Avoid direct DB/session use outside repository implementations.
- Add structlog events for key business actions and error paths.
- Confirm DI wiring exists (FastAPI `dependency_overrides` in entrypoint).
- Avoid `while True` loops without a clear and tested exit strategy.

## Output expectations
- Briefly describe which layer(s) changed and why.
- Call out any boundary risks or trade-offs.
