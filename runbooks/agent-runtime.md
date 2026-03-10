# Runbook: Agent Runtime

## Symptom: agent_runs showing FALLBACK status

### Inspect

```bash
# Check recent agent runs
docker exec -it infosentry-postgres psql -U infosentry -d infosentry -c \
  "SELECT id, status, fallback_reason, created_at FROM agent_runs ORDER BY created_at DESC LIMIT 10;"

# Check worker_agent logs
docker-compose -f docker-compose.prod.yml logs --tail=100 worker_agent | grep -i "error\|fallback\|timeout"
```

### Likely causes

1. **LLM API unreachable** — network issue or API key invalid
2. **LLM rate-limited (429)** — exceeded provider quota
3. **Budget fuse tripped** — daily judge budget exhausted
4. **Response schema invalid** — LLM returned non-JSON or wrong shape

### Fix

**If LLM API unreachable:**
```bash
# Verify connectivity
curl -s https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY" | head -5

# If API key issue, update .env and restart
docker-compose -f docker-compose.prod.yml restart worker_agent
```

**If budget fuse tripped:**
```bash
# Check current budget
curl http://localhost:8000/api/v1/admin/budget -H "Authorization: Bearer $TOKEN"

# System auto-recovers next day. To override now:
curl -X POST http://localhost:8000/api/v1/admin/config \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"JUDGE_PER_DAY": 300}'
```

**If schema violation:**
```bash
# Check the failing prompt output in logs
docker-compose -f docker-compose.prod.yml logs --tail=200 worker_agent | grep "schema\|parse\|json"

# Fallback is automatic (degrades to BATCH). Fix prompt if recurring.
```

### Verify

```bash
# Confirm new runs succeed
docker exec -it infosentry-postgres psql -U infosentry -d infosentry -c \
  "SELECT status, count(*) FROM agent_runs WHERE created_at > NOW() - INTERVAL '1 hour' GROUP BY status;"
```

---

## Symptom: No agent_runs being created

### Inspect

```bash
# Check if match pipeline is feeding agent queue
docker exec infosentry-redis redis-cli LLEN q_agent

# Check worker is alive
docker-compose -f docker-compose.prod.yml ps | grep worker_agent
```

### Likely causes

1. **worker_agent crashed** — check logs
2. **Upstream queue stalled** — q_embed or q_match backlogged
3. **No matches above threshold** — normal if sources are quiet

### Fix

```bash
# Restart worker if crashed
docker-compose -f docker-compose.prod.yml restart worker_agent

# Check upstream queues
docker exec infosentry-redis redis-cli LLEN q_embed
docker exec infosentry-redis redis-cli LLEN q_match
```

### Verify

```bash
celery -A src.core.infrastructure.celery.app inspect ping
```

## Related

- Agent runtime spec: `agents/`
- Budget runbook: [budget-and-feature-flags.md](budget-and-feature-flags.md)
- Prompt regression runbook: [prompt-regressions.md](prompt-regressions.md)
