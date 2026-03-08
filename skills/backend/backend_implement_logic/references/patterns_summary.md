# Patterns summary

- Repository pattern for data access (domain interface, infrastructure implementation).
- Mapper pattern to translate between ORM models and domain entities.
- Application services orchestrate use-cases and build response DTOs.
- Use ports/Protocol for external services (KV, Token, Fetcher).
- Use DI (FastAPI Depends) at app layer; map to infra via `dependency_overrides`.
- Keep auth dependencies in application layer; infra provides override.
