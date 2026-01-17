# AI Skills for infoSentry

This document defines project-specific skill profiles for AI-assisted development. Use the skill that matches the change scope to keep work consistent and safe.

## skill-backend-ddd-change
**Scope**: `src/core/**`, `src/modules/**` (backend domain/application/interfaces/infrastructure)

**Must do**
- Preserve dependency direction: interfaces → application → domain; infra implements ports.
- No business logic in routers/controllers.
- Use async/await where applicable.
- Full type annotations, mypy strict compliant.
- Use structlog for business events.

**Must not do**
- Do not import infrastructure from domain/application.
- Do not add dependencies without approval.

**Required checks**
- `uv run pytest`
- `uv run mypy src`

## skill-fetcher-security
**Scope**: `src/modules/sources/**`, URL fetchers, HTTP client usage

**Must do**
- Validate URLs against SSRF: block private, loopback, link-local, reserved, multicast.
- Only allow `http`/`https` schemes.
- Clean titles/snippets for HTML content.
- Add/adjust tests in `tests/unit/test_ingest.py` for validation.

**Must not do**
- Do not follow unvalidated redirects to non-public hosts.
- Do not accept `file://` or custom schemes.

**Required checks**
- `uv run pytest`
- `uv run mypy src`

## skill-agent-runtime-change
**Scope**: `src/modules/agent/**`, `docs/agents/**`

**Must do**
- Keep side effects behind tools.
- Update `docs/agents/AGENT_RUNTIME_SPEC.md` if state/tools change.
- Maintain action ledger consistency.

**Must not do**
- Do not bypass tool call logging.

**Required checks**
- `uv run pytest`
- `uv run mypy src`

## skill-config-and-secrets
**Scope**: `src/core/config.py`, `.env*`, auth settings, CORS/JWT

**Must do**
- Update `.env.example` for any config change.
- Enforce safe defaults for production.
- Reject wildcard CORS in production.

**Must not do**
- Do not add hardcoded secrets.

**Required checks**
- `uv run pytest`
- `uv run mypy src`

## skill-migrations
**Scope**: Alembic migrations, SQLModel model changes

**Must do**
- Create Alembic migration for every model/schema change.
- Keep migrations consistent with models.
- Add rollback notes for destructive changes.

**Required checks**
- `uv run pytest`
- `uv run mypy src`

## skill-frontend-ui
**Scope**: `infosentry-web/**` when changing styles/layout/visuals

**Must do**
- Follow `docs/dev/FRONTEND_CONVENTIONS.md`.
- Keep UI minimal and content-first.

**Required checks**
- `npm run lint`
- `npm run build`

## skill-frontend-data
**Scope**: `infosentry-web/src/lib/**`, API clients, data shaping

**Must do**
- Keep client types aligned with API spec.
- Validate response shapes when practical.

**Required checks**
- `npm run lint`
- `npm run build`

## Change checklist (all skills)
- Confirm scope and impacted modules.
- Update tests or note why not applicable.
- Run required checks or document pre-existing failures.
- Keep changes minimal and aligned to existing patterns.
