# Runbooks

Operational failure response procedures for infoSentry. Each runbook follows the same structure:

**Symptom → Inspect → Likely cause → Fix → Verify**

## Index

| Runbook | Covers |
|---------|--------|
| [agent-runtime.md](agent-runtime.md) | Agent decision failures, LLM errors, fallback triggers |
| [celery-queues-and-workers.md](celery-queues-and-workers.md) | Queue backlog, worker crash, beat scheduling |
| [prompt-regressions.md](prompt-regressions.md) | Prompt output drift, schema violations, eval failures |
| [email-delivery.md](email-delivery.md) | SMTP failures, duplicate sends, delivery guardrails |
| [budget-and-feature-flags.md](budget-and-feature-flags.md) | Budget fuse trips, feature flag toggling, degraded mode |

## When to use these vs `docs/ops/`

- **Runbooks** (`runbooks/`): Something is broken right now. Follow the steps.
- **Ops guides** (`docs/ops/`): How to deploy, configure, or maintain the system.

## Related

- Deployment guide: `docs/ops/DEPLOYMENT.md`
- VM topology: `docs/ops/RUNBOOK_VM.md`
- Agent runtime spec: `agents/`
- Eval cases: `infoSentry-backend/evals/`
