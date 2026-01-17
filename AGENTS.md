# AGENTS - infoSentry

## Hard rules (project-specific)
- Follow DDD layering and dependency direction:
  - interfaces -> application -> domain
  - infrastructure implements domain interfaces
  - domain must not depend on infrastructure
- Do not put business logic in routers/controllers.
- Prefer async/await across the backend.
- Use full type annotations (mypy strict).
- No silent exception swallowing; handle errors explicitly.
- No `# type: ignore` to bypass type checks.
- No hardcoded configuration values.
- Log key business events (structlog).

## Module layout (backend)
- `src/modules/<module>/domain`: entities, value objects, repository interfaces, domain services
- `src/modules/<module>/application`: commands/queries/services (use-case orchestration)
- `src/modules/<module>/infrastructure`: models, repository impl, mappers
- `src/modules/<module>/interfaces`: routers, schemas

## Testing and migrations
- Tests use pytest + pytest-anyio for async.
- Migrations use Alembic; keep models and migrations consistent.

## AI development constraints
- Do not add new dependencies without explicit approval.
- No hardcoded secrets or default credentials in code or examples.
- Config changes must update `.env.example` and relevant docs.
- No business logic in routers/controllers; use application or domain services.
- Preserve DDD dependency direction and keep infra behind ports.
- Use structlog for business events; avoid loguru for domain events.
- Do not broaden exception handling; handle errors explicitly.
- For frontend UI changes, follow `docs/dev/FRONTEND_CONVENTIONS.md`.

## Required checks (when applicable)
- Backend: `uv run pytest` and `uv run mypy src`.
- Frontend: `npm run lint` and `npm run build`.
- If checks fail due to pre-existing issues, report them and proceed only if unrelated.

## AI skill triggers
- `skill-backend-ddd-change`: any change under `src/modules/**` or `src/core/**`.
- `skill-fetcher-security`: any change under `src/modules/sources/**` or URL fetching.
- `skill-agent-runtime-change`: any change under `src/modules/agent/**` or `docs/agents/**`.
- `skill-config-and-secrets`: any change to config, env, or auth settings.
- `skill-migrations`: any DB schema or model change.
- `skill-frontend-ui`: any CSS/layout/visual change in `infosentry-web`.
- `skill-frontend-data`: any API client or data-shaping change in `infosentry-web/src/lib`.
