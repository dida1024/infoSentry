---
name: backend_fetcher_security
description: Secure URL fetching and content parsing in infoSentry sources module. Use for SSRF/XSS hardening and fetcher behavior changes.
---

# Fetcher Security (infoSentry)

Follow hard rules in `AGENTS.md`.

## Scope
- `src/modules/sources/**`
- Any URL fetching or HTML parsing logic.

## Must do
- Validate URLs against SSRF: block private, loopback, link-local, reserved, multicast.
- Only allow `http`/`https` schemes; reject `file://` and custom protocols.
- Clean titles/snippets to remove HTML tags.
- Add or update tests in `tests/unit/test_ingest.py` for validation cases.

## Must not do
- Do not follow redirects to disallowed hosts.
- Do not accept URLs without hostname.

## Required checks
- `uv run pytest`
- `uv run mypy src`