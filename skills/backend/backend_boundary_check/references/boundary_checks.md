# Boundary checks

- domain must not depend on infrastructure.
- routers/controllers must not contain business logic.
- application should not bypass repositories to touch DB directly.
- no sync blocking calls without clear justification.
