---
name: backend_agent_runtime_change
description: Update agent runtime, tools, and action ledger behavior in infoSentry while keeping auditability and deterministic replay.
---

# Agent Runtime Change (infoSentry)

Follow hard rules in `AGENTS.md` and `docs/agents/AGENT_RUNTIME_SPEC.md`.

## Scope
- `src/modules/agent/**`
- `docs/agents/**`

## Must do
- Keep side effects behind tools; no direct writes from LLM-facing logic.
- Record tool calls and action ledger entries for every run.
- Update `docs/agents/AGENT_RUNTIME_SPEC.md` when state/tools change.

## Must not do
- Do not bypass tool-call logging.
- Do not introduce non-idempotent side effects without dedupe keys.

## Required checks
- `uv run pytest`
- `uv run mypy src`