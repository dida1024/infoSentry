# Runbook: Prompt Regressions

## Symptom: Agent decisions drifting (wrong labels, missing fields)

### Inspect

```bash
# Run prompt regression tests
cd infoSentry-backend
uv run pytest tests/ -k "prompt_regression" -v

# Check recent agent decisions for anomalies
docker exec -it infosentry-postgres psql -U infosentry -d infosentry -c \
  "SELECT id, status, fallback_reason FROM agent_runs WHERE created_at > NOW() - INTERVAL '24 hours' ORDER BY created_at DESC LIMIT 20;"
```

### Likely causes

1. **Prompt template changed without eval update** — rendering differs from expected
2. **Model provider updated model weights** — same prompt, different output
3. **Variable injection broken** — template vars not substituted

### Fix

**If prompt template changed:**
```bash
# Compare prompt versions
ls infoSentry-backend/prompts/agent/boundary_judge/
ls infoSentry-backend/prompts/agent/push_worthiness/

# Run full eval suite
cd infoSentry-backend
uv run pytest tests/ -k "prompt" -v
```

**If model drift:**
```bash
# Check which model is in use
grep JUDGE_MODEL infoSentry-backend/.env

# If needed, pin to specific model version in .env
# OPENAI_JUDGE_MODEL_SMALL=gpt-4o-mini-2024-07-18
```

**If variable injection broken:**
```bash
# Check prompt rendering logs
docker-compose -f docker-compose.prod.yml logs --tail=100 worker_agent | grep "render\|template\|prompt"
```

### Verify

```bash
cd infoSentry-backend
uv run pytest tests/ -k "prompt_regression" -v
# All cases must pass
```

## Change rules

- Prompt change → must update corresponding eval case in `infoSentry-backend/evals/prompt_regression/`
- Prompt version bump → must add new eval case file
- Every prompt in `infoSentry-backend/prompts/` must have a matching eval

## Prompt-to-eval mapping

| Prompt | Eval |
|--------|------|
| `agent/boundary_judge/v1` | `evals/prompt_regression/agent.boundary_judge.v1.json` |
| `agent/push_worthiness/v1` | `evals/prompt_regression/agent.push_worthiness.v1.json` |
| `goals/goal_draft/v1` | `evals/prompt_regression/goals.goal_draft.v1.json` |
| `goals/keyword_suggestion/v1` | `evals/prompt_regression/goals.keyword_suggestion.v1.json` |

## Related

- Eval cases: `infoSentry-backend/evals/prompt_regression/`
- Prompt templates: `infoSentry-backend/prompts/`
- Agent runtime runbook: [agent-runtime.md](agent-runtime.md)
