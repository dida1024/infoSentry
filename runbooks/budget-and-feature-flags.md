# Runbook: Budget and Feature Flags

## Symptom: Budget fuse tripped — agent decisions degraded

### Inspect

```bash
# Check budget status via API
curl http://localhost:8000/api/v1/admin/budget -H "Authorization: Bearer $TOKEN"

# Check logs for budget warnings
docker-compose -f docker-compose.prod.yml logs --tail=100 worker_agent | grep -i "budget\|fuse\|limit"

# Check agent_runs fallback rate
docker exec -it infosentry-postgres psql -U infosentry -d infosentry -c \
  "SELECT status, count(*) FROM agent_runs
   WHERE created_at > NOW() - INTERVAL '24 hours' GROUP BY status;"
```

### Likely causes

1. **Normal exhaustion** — high-volume day exceeded JUDGE_PER_DAY (200) or DAILY_USD_BUDGET ($0.33)
2. **Runaway loop** — bug caused repeated LLM calls for same items
3. **Model cost spike** — provider changed pricing

### Fix

**Normal exhaustion (wait for reset):**
- Budget resets daily. System auto-degrades: boundary samples fall back to BATCH.
- No action needed unless urgent items are being missed.

**Override budget temporarily:**
```bash
curl -X POST http://localhost:8000/api/v1/admin/config \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"JUDGE_PER_DAY": 300, "DAILY_USD_BUDGET": 0.50}'
```

**If runaway loop:**
```bash
# Check for repeated calls on same items
docker exec -it infosentry-postgres psql -U infosentry -d infosentry -c \
  "SELECT item_id, count(*) FROM agent_runs
   WHERE created_at > NOW() - INTERVAL '6 hours'
   GROUP BY item_id HAVING count(*) > 2 ORDER BY count(*) DESC LIMIT 10;"

# If duplicates found, investigate dedup logic
docker-compose -f docker-compose.prod.yml logs --tail=500 worker_agent | grep "duplicate\|already_processed"
```

### Verify

```bash
curl http://localhost:8000/api/v1/admin/budget -H "Authorization: Bearer $TOKEN"
# remaining_judge > 0 or next reset time visible
```

---

## Symptom: Need to toggle feature flags for degraded operation

### Feature flag reference

| Flag | Default | Effect when `false` |
|------|---------|---------------------|
| `LLM_ENABLED` | true | Boundary samples skip judge, all degrade to BATCH |
| `EMBEDDING_ENABLED` | true | Skip embedding computation |
| `IMMEDIATE_ENABLED` | true | No immediate pushes, only Batch/Digest |
| `EMAIL_ENABLED` | true | No email, only in-app notifications |

### Toggle via API (no restart)

```bash
# Read current flags
curl http://localhost:8000/api/v1/admin/config -H "Authorization: Bearer $TOKEN"

# Toggle one flag
curl -X POST http://localhost:8000/api/v1/admin/config \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"LLM_ENABLED": false}'

# Emergency: disable all advanced features
curl -X POST http://localhost:8000/api/v1/admin/config \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"LLM_ENABLED": false, "IMMEDIATE_ENABLED": false, "EMAIL_ENABLED": false}'
```

### Toggle via .env (requires restart)

```bash
# If API is down, edit .env directly
vim infoSentry-backend/.env
# Change: LLM_ENABLED=false

docker-compose -f docker-compose.prod.yml restart api worker_agent
```

### Verify

```bash
curl http://localhost:8000/api/v1/admin/config -H "Authorization: Bearer $TOKEN"
# Confirm flag values match intent
```

## Related

- Agent runtime runbook: [agent-runtime.md](agent-runtime.md)
- Deployment guide: `docs/ops/DEPLOYMENT.md` (section 5: degradation switches)
