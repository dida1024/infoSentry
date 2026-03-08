# Migration rules

- Keep models and migrations consistent.
- Include indexes and constraints where needed.
- Provide safe downgrade when possible.
- Apply project defaults: string UUID primary keys; `DateTime(timezone=True)` stored in UTC; `is_deleted` soft-delete flag; maintain dedupe unique constraints per ADRs (items.url_hash, goal_item_matches(goal_id,item_id), push_decisions.dedupe_key, budget_daily.date).
