---
name: backend_write_tests
description: Write backend tests (unit/integration/e2e) with pytest and async patterns.
---

# Backend Write Tests

Follow hard rules in `AGENTS.md`.

## Read first (only what you need)
- `references/test_strategy.md`
- `references/test_commands.md`
- `references/test_naming_structure.md`
- `references/test_anti_patterns.md`

## Scope
- Add or update tests for new behavior and regressions.
- Prefer unit tests; add integration/e2e for critical flows.
- Honor project invariants in fixtures/assertions: UUID string IDs, UTC-aware datetimes, soft-delete flags, dedupe uniqueness, async paths tested with pytest-anyio.
