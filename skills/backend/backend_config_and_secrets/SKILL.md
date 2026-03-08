---
name: backend_config_and_secrets
description: Modify configuration, auth, CORS, and secrets in infoSentry safely and consistently.
---

# Config and Secrets (infoSentry)

Follow hard rules in `AGENTS.md`.

## Scope
- `src/core/config.py`
- `.env*`, auth settings, JWT, CORS

## Must do
- Update `.env.example` for any config change.
- Enforce safe production defaults (no wildcard CORS, strong SECRET_KEY).
- Keep JWT expiry and refresh behavior explicit.

## Must not do
- No hardcoded secrets or default credentials in code/examples.
- No broad CORS in production.

## Required checks
- `uv run pytest`
- `uv run mypy src`