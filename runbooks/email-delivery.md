# Runbook: Email Delivery

## Symptom: Emails not being sent

### Inspect

```bash
# Check email queue
docker exec infosentry-redis redis-cli LLEN q_email

# Check worker_email logs
docker-compose -f docker-compose.prod.yml logs --tail=100 worker_email | grep -i "error\|smtp\|fail\|refused"

# Check push_decisions status
docker exec -it infosentry-postgres psql -U infosentry -d infosentry -c \
  "SELECT status, count(*) FROM push_decisions WHERE created_at > NOW() - INTERVAL '24 hours' GROUP BY status;"
```

### Likely causes

1. **SMTP credentials invalid** — password changed or expired
2. **SMTP provider rate limit** — too many sends per minute
3. **EMAIL_ENABLED=false** — feature flag turned off
4. **worker_email crashed**

### Fix

**If SMTP credentials:**
```bash
# Test SMTP connection directly
docker-compose -f docker-compose.prod.yml exec api python -c "
import smtplib
s = smtplib.SMTP('$SMTP_HOST', $SMTP_PORT)
s.starttls()
s.login('$SMTP_USER', '$SMTP_PASS')
print('SMTP OK')
s.quit()
"

# Fix credentials in .env, then restart
docker-compose -f docker-compose.prod.yml restart worker_email
```

**If feature flag off:**
```bash
curl -X POST http://localhost:8000/api/v1/admin/config \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"EMAIL_ENABLED": true}'
```

**If worker crashed:**
```bash
docker-compose -f docker-compose.prod.yml restart worker_email
```

### Verify

```bash
# Queue should drain
watch -n 5 'docker exec infosentry-redis redis-cli LLEN q_email'

# Recent push_decisions should show SENT
docker exec -it infosentry-postgres psql -U infosentry -d infosentry -c \
  "SELECT id, status, created_at FROM push_decisions ORDER BY created_at DESC LIMIT 5;"
```

---

## Symptom: Duplicate emails being sent

### Inspect

```bash
# Check for duplicate push_decisions in same window
docker exec -it infosentry-postgres psql -U infosentry -d infosentry -c \
  "SELECT goal_id, channel, count(*) FROM push_decisions
   WHERE created_at > NOW() - INTERVAL '1 hour'
   GROUP BY goal_id, channel HAVING count(*) > 1;"
```

### Likely causes

1. **Coalesce pipeline broken** — Immediate decisions not being merged
2. **Worker retry caused re-send** — task acked but email already sent
3. **Beat fired duplicate schedule** — stale schedule file

### Fix

```bash
# Check coalesce logic in logs
docker-compose -f docker-compose.prod.yml logs --tail=200 worker_agent | grep -i "coalesce\|merge\|dedup"

# If beat issue, see celery-queues-and-workers.md
```

### Verify

```bash
# No duplicate sends in last hour
docker exec -it infosentry-postgres psql -U infosentry -d infosentry -c \
  "SELECT goal_id, channel, count(*) FROM push_decisions
   WHERE created_at > NOW() - INTERVAL '1 hour'
   GROUP BY goal_id, channel HAVING count(*) > 1;"
# Expected: 0 rows
```

## Related

- Delivery guardrails: `AGENTS.md` (delivery guardrails section)
- Queue runbook: [celery-queues-and-workers.md](celery-queues-and-workers.md)
