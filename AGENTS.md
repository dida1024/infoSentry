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
