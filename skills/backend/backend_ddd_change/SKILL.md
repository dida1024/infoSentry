---
name: backend_ddd_change
description: Implement backend changes in infoSentry while enforcing DDD layering, strict typing, and business-event logging.
---

# Backend DDD Change (infoSentry)

Follow hard rules in `AGENTS.md`.

## Scope
- Any change under `src/core/**` or `src/modules/**`.

## Must do
- Preserve dependency direction: interfaces → application → domain. Infrastructure only implements domain ports.
- Keep business logic out of routers/controllers.
- Prefer async/await for IO paths.
- Full type annotations; keep mypy strict happy.
- Log key business events via structlog.
- Update `.env.example` if config changes.
- If a `while True` loop is unavoidable, add an explicit exit mechanism (cancellation, timeout, sentinel, or backoff with max retries) and document the stop condition.
- Proactively optimize hot paths (batching, pagination, timeouts, and resource limits) to avoid performance regressions.

## Must not do
- Do not import infrastructure into domain/application layers.
- Do not add dependencies without explicit approval.
- No `# type: ignore` or broad exception handlers.
- Do not add `while True` loops without a clear and tested exit strategy.

## Required checks
- `uv run pytest`
- `uv run mypy src`

## When missing info
- Ask targeted questions about domain rules, side effects, and error handling.
