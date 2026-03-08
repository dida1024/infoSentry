# Backend Conventions Summary (infoSentry)

## DDD and layering
- Follow DDD layering and dependency direction: interfaces -> application -> domain.
- Infrastructure implements domain interfaces.
- Do not place business logic in routers/controllers.

## Types and async
- Use async/await throughout.
- Use full type annotations; prefer modern Python 3.10+ syntax.

## Errors and logging
- Domain raises exceptions; application handles/translates; interfaces return HTTP errors.
- Never swallow exceptions silently.
- Use structlog for business event logging.

## Repositories and transactions
- Access DB via repository pattern; avoid direct session calls outside repositories.
- Manage transactions in application services (Unit of Work).

## API design
- RESTful paths (list/detail/create/update/delete).
- Response format shown in conventions may differ from API spec; if conflict, follow API spec and note it.
