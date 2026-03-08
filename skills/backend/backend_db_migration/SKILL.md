---
name: backend_db_migration
description: Create and manage database migrations using Alembic for the backend.
---

# Backend DB Migration

Follow hard rules in `AGENTS.md`.

## Read first (only what you need)
- `references/migration_steps.md`
- `references/migration_rules.md`
- `references/db_review_points.md`
- `docs/decisions/ARCHITECTURE_DECISIONS.md` (schema defaults: UUID strings, UTC, is_deleted, dedupe keys)

## Scope
- Update models, generate and review migrations, validate upgrade/downgrade paths.
