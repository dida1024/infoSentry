# Migration steps

1. Update SQLAlchemy models.
2. Generate migration: `uv run alembic revision --autogenerate -m "desc"`.
3. Review migration for indexes/constraints.
4. Apply migration: `uv run alembic upgrade head`.
