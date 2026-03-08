# Anti-patterns to avoid

- Domain depends on infrastructure (e.g., SQLAlchemy in domain).
- Business logic in routers/controllers.
- Interfaces import infrastructure repositories/dependencies directly.
- Routers assemble complex DTOs or pagination cursors.
- Routers perform workflow logic (feedback, click tracking, config/health aggregation).
- Application imports infrastructure clients (Redis/JWT/fetchers/models/queues).
- Entry-point missing dependency overrides for application dependencies.
- Silent exception swallowing; no `# type: ignore`.
- Sync I/O inside async functions.
- N+1 queries; prefer batch queries/joins.
