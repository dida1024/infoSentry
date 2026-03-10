# Runbook: Celery Queues and Workers

## Symptom: Queue backlog growing

### Inspect

```bash
# Check all queue lengths
for q in q_ingest q_embed q_match q_agent q_email; do
  echo "$q: $(docker exec infosentry-redis redis-cli LLEN $q)"
done

# Check worker status
docker-compose -f docker-compose.prod.yml ps | grep worker
```

### Likely causes

1. **Worker crashed or OOM-killed** — check `docker ps` and logs
2. **Upstream flood** — too many sources fetched at once
3. **LLM/SMTP downstream slow** — causes q_agent/q_email buildup
4. **Redis connection lost** — workers can't consume

### Fix

**If worker crashed:**
```bash
docker-compose -f docker-compose.prod.yml restart worker_ingest worker_embed_match worker_agent worker_email
```

**If downstream slow (LLM/SMTP):**
```bash
# Temporarily reduce concurrency or disable
curl -X POST http://localhost:8000/api/v1/admin/config \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"IMMEDIATE_ENABLED": false}'
```

**If Redis connection lost:**
```bash
docker exec infosentry-redis redis-cli ping
# If PONG -> Redis fine, check worker Redis URL config
# If no response -> restart Redis
docker-compose -f docker-compose.prod.yml restart redis
# Wait 10s, then restart workers
docker-compose -f docker-compose.prod.yml restart worker_ingest worker_embed_match worker_agent worker_email
```

### Verify

```bash
# Queue lengths should decrease
watch -n 5 'for q in q_ingest q_embed q_match q_agent q_email; do echo "$q: $(docker exec infosentry-redis redis-cli LLEN $q)"; done'

# Workers responding to ping
docker exec infosentry-worker-agent celery -A src.core.infrastructure.celery.app inspect ping
```

---

## Symptom: Celery Beat not scheduling tasks

### Inspect

```bash
docker-compose -f docker-compose.prod.yml logs --tail=50 beat
docker-compose -f docker-compose.prod.yml ps | grep beat
```

### Likely causes

1. **Beat process crashed**
2. **Stale PID/schedule file** — leftover from previous run
3. **Timezone misconfiguration** — tasks fire at wrong time

### Fix

```bash
# Restart beat
docker-compose -f docker-compose.prod.yml restart beat

# If stale schedule file, remove and restart
docker-compose -f docker-compose.prod.yml exec beat rm -f /app/celerybeat-schedule
docker-compose -f docker-compose.prod.yml restart beat
```

### Verify

```bash
# Beat should log scheduled task registrations
docker-compose -f docker-compose.prod.yml logs --tail=20 beat | grep -i "scheduler\|sending"
```

## Related

- VM topology: `docs/ops/RUNBOOK_VM.md` (concurrency table)
- Agent runtime runbook: [agent-runtime.md](agent-runtime.md)
