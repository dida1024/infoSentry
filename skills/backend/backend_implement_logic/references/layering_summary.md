# Layering summary (infoSentry)

- domain: pure business rules, no external dependencies.
- application: orchestration, transactions, calling repositories.
- infrastructure: DB/external integrations, repository implementations.
