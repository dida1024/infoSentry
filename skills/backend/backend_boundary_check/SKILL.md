---
name: backend_boundary_check
description: Review backend changes for DDD boundary violations and architectural risks.
---

# Backend Boundary Check

Follow hard rules in `AGENTS.md`.

## Read first (only what you need)
- `references/boundary_checks.md`
- `references/anti_patterns_summary.md`

## Scope
- Identify boundary violations and architectural risks.
- Report findings with file:line and a concrete fix.
- Confirm project invariants: no business logic in interfaces, domain free of infra, async-only I/O, full typing (no `# type: ignore`), no hardcoded config (use settings), structlog for business events, UUID string IDs, UTC timestamps, `is_deleted` present, idempotency keys kept intact.
