.PHONY: format format-check lint test

format:
	cd infoSentry-backend && uv run ruff format .

format-check:
	cd infoSentry-backend && uv run ruff format --check .
	cd infoSentry-backend && uv run ruff check .
	cd infosentry-web && npm run lint

lint:
	cd infoSentry-backend && uv run ruff check .
	cd infoSentry-backend && uv run mypy .
	cd infosentry-web && npm run lint

test:
	cd infoSentry-backend && uv run pytest

