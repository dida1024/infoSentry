# Anti-patterns checklist

- Domain imports infrastructure/ORM.
- Routers contain business logic.
- Cross-module direct DB access.
- Silent exception handling.
- Hardcoded config values.
- Sync I/O in async functions.
- N+1 queries or SQL string concatenation.
- Inconsistent API response formats.
