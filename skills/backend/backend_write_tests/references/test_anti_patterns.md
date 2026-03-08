# Test anti-patterns

- Do not call real external services in unit tests; mock them.
- Avoid inter-test dependencies (test order should not matter).
