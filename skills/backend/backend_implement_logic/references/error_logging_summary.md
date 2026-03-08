# Error + logging summary

- Domain raises exceptions; application translates to use-case errors.
- No silent exception swallowing.
- Log key business events with structlog.
- Route-layer error handling should not mask domain validation errors; raise domain errors and let handlers map to HTTP.
