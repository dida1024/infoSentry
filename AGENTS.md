# AGENTS - infoSentry

## Workflow: OpenSpec (Spec-Driven Development)

This project uses [OpenSpec](https://github.com/Fission-AI/OpenSpec) for structured change management.

### Commands
- `/opsx:propose <description>` — Create a change with proposal, specs, design, and tasks in one step
- `/opsx:explore <topic>` — Investigate ideas and requirements before committing to a change
- `/opsx:apply <name>` — Implement tasks from an existing change
- `/opsx:archive <name>` — Finalize and archive a completed change

### Artifacts per change
```
openspec/changes/<name>/
├── proposal.md    ← why and what
├── design.md      ← technical approach
├── tasks.md       ← implementation checklist
└── specs/         ← delta specs (ADDED/MODIFIED/REMOVED)
```

### Before any code change
Follow all hard rules below. The OpenSpec workflow structures planning; these rules govern implementation.

---

## Hard rules (project-specific)

- Follow DDD layering and dependency direction:
  - interfaces → application → domain
  - infrastructure implements domain interfaces (ports)
  - domain must not depend on infrastructure
- For async notification/email pipeline changes, enforce end-to-end delivery guardrails (contract mapping, TDD regression, runtime verification evidence).
- Do not put business logic in routers/controllers.
- Prefer async/await across the backend.
- Use full type annotations (mypy strict).
- No silent exception swallowing; handle errors explicitly.
- No `# type: ignore` to bypass type checks.
- No hardcoded configuration values; read from settings/env and inject via DI.
- Log key business events (structlog) with context (goal_id, item_id, dedupe_key).
- Proactively optimize hot paths: batching, pagination, timeouts, resource limits.
- While-True loops must have explicit exit mechanism (timeout, sentinel, backoff with max retries).

## Module layout (backend)

- `src/modules/<module>/domain`: entities, value objects, repository interfaces, domain services
- `src/modules/<module>/application`: commands/queries/services (use-case orchestration)
- `src/modules/<module>/infrastructure`: models, repository impl, mappers
- `src/modules/<module>/interfaces`: routers, schemas

## Project invariants

- IDs: string UUIDs for primary keys
- Timestamps: `DateTime(timezone=True)` stored in UTC
- Soft delete: `is_deleted` flag on all soft-deleted tables
- Idempotency keys: `push_decisions.dedupe_key`, `items.url_hash`, `goal_item_matches(goal_id, item_id)`, `budget_daily.date`
- Queues: `q_ingest`, `q_embed`, `q_match`, `q_agent`, `q_email`

## API design

- RESTful paths with `/api` prefix; `/r/{item_id}` for redirect tracking
- Error format: `{ "error": { "code": "...", "message": "...", "details": {...} } }`
- Cursor pagination: `cursor`, `next_cursor`, `has_more`
- Routers in `src/modules/<module>/interfaces/routers.py`; schemas in `schemas.py`
- Route layer: validate input, wire DI dependencies, call application services only

## Testing and migrations

- Tests use pytest + pytest-anyio for async.
- Test naming: `test_<method>_<scenario>_<expected>`
- File layout: `tests/unit/`, `tests/integration/`, `tests/e2e/`
- Prefer unit tests; integration for key flows.
- No real external services in unit tests; use mocks.
- Migrations use Alembic; keep models and migrations consistent.
- Apply project defaults in migrations: UUID string keys, UTC timestamps, `is_deleted`, dedupe constraints.

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

## Delivery guardrails (mandatory for async notification/email flows)

- Scope: any change or incident under `src/modules/agent/**`, `src/modules/push/**`, `src/modules/items/**`, `src/core/infrastructure/celery/**`.
- Must produce a chain map before fix: trigger → decision record → queue/buffer → worker task → sender → status update.
- Must add failing regression test(s) first, then implement minimal fix, then re-run tests.
- Must provide runtime evidence (not only unit tests): worker/beat alive, queue state, and DB status transition evidence.
- Do not claim "fixed" without command outputs for required checks and runtime verification.

## Security (URL fetching)

- Validate URLs against SSRF: block private, loopback, link-local, reserved, multicast IP ranges.
- Only allow `http`/`https` schemes; reject `file://` and custom protocols.
- Clean titles/snippets to remove HTML tags.
- Do not follow redirects to disallowed hosts.

## Agent runtime

- Keep side effects behind tools; no direct writes from LLM-facing logic.
- Record tool calls and action ledger entries for every run.
- Update `openspec/specs/agent-runtime/spec.md` when state/tools change.
- No non-idempotent side effects without dedupe keys.

## Configuration and secrets

- Update `.env.example` for any config change.
- Enforce safe production defaults: no wildcard CORS, strong SECRET_KEY.
- Keep JWT expiry and refresh behavior explicit.
- Never commit `.env` files with real values.

## Boundary violations (forbidden)

- Domain imports infrastructure (SQLAlchemy, Redis, etc.)
- Routers import directly from `infrastructure.repositories` or `infrastructure.dependencies`
- Application imports infrastructure clients (Redis, JWT, fetchers, models, queues)
- Routers execute business workflows (feedback, click tracking, monitoring aggregation)
- Entry-point missing `dependency_overrides` mappings

## Git conventions

- Each commit: single logical change; format `<type>: <intent>` (feat, fix, refactor, test, docs, chore)
- 2–6 commits per PR max
- Never commit secrets or `.env` files
- Focus on WHY, not WHAT, in commit messages

## Canonical repository locations

- `openspec/specs/` — system behavior specifications (domain-organized)
- `openspec/changes/` — active change proposals
- `docs/product/` — PRD, roadmap, acceptance checklist
- `docs/decisions/` — architecture decisions and ADRs
- `docs/dev/` — coding conventions (frontend)
- `runbooks/` — operational failure response procedures
- `infoSentry-backend/evals/` — prompt regression and decision eval cases
- `infoSentry-backend/prompts/` — prompt templates
