# Test strategy

- Prefer unit tests for domain/application logic.
- Add integration tests for key endpoints and flows.
- Use pytest + pytest-anyio for async tests.
- Keep tests isolated; avoid shared mutable state.
