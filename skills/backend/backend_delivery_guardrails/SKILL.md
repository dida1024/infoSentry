---
name: backend_delivery_guardrails
description: Use when debugging or changing async notification/email delivery flows to prevent inbox-email divergence with contract-first checks and runtime verification.
---

# Backend Delivery Guardrails (infoSentry)

Follow hard rules in `AGENTS.md`.

## Scope
- Any change or incident in:
  - `src/modules/agent/**`
  - `src/modules/push/**`
  - `src/modules/items/**`
  - `src/core/infrastructure/celery/**`

## Mandatory workflow
1. Root cause first.
  - Build a chain map: trigger -> decision record -> queue/buffer -> worker task -> email send -> decision status update.
  - Identify payload contract at each hop (ID type and key format must match).
2. TDD for regressions.
  - Write failing regression test(s) first.
  - Implement minimal fix.
  - Re-run regression tests and related suites.
3. Runtime verification.
  - Verify workers/beat are alive and consuming expected queues.
  - Verify queue/buffer behavior matches contract.
  - Verify DB status transitions for affected decisions (`PENDING -> SENT/FAILED/SKIPPED`).
4. Completion gate.
  - No "fixed" claim without fresh command evidence and observed status transition evidence.

## Minimum evidence to provide in task summary
- Exact commands run and pass/fail status.
- Why the root cause is proven (not guessed).
- Which contract mismatch was fixed (field/key/type).
- Before/after behavior for one real decision flow.

## Required checks
- `uv run pytest`
- `uv run mypy src`
- If related tests exist, include focused regression command(s) for push/agent/items flow.

## Must not do
- Do not patch symptoms without a failing regression test.
- Do not mark done with only unit tests when flow crosses queue/worker boundaries.
- Do not skip status transition verification for delivery incidents.
