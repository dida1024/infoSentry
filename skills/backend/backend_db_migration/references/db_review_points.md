# DB review points

- Watch for N+1 queries; prefer batch queries.
- Use parameterized queries; avoid SQL string concat.
- Ensure transaction boundaries for multi-step writes.
- Add indexes/constraints when adding new fields.
- Check project invariants: UTC timezone-aware timestamps, string UUID PKs, `is_deleted` soft delete, required unique keys for dedupe tables, foreign keys consistent with DDD module boundaries.
