# Microservice Rewrite Baseline

Goal: capture the current backend baseline and define initial service ownership rules for a shared database.

## Current architecture snapshot

- Pattern: modular monolith with queue isolation
- API: FastAPI
- Tasks: Celery workers + Celery Beat
- Storage: PostgreSQL + pgvector
- Cache and broker: Redis
- AI: OpenAI API (embeddings + LLM judge)
- Auth: JWT + magic link
- Deployment: single machine, docker compose

## Core module boundaries (current)

- users: auth, sessions, user budget
- sources: ingest and subscriptions
- goals: goal CRUD, keywords, push config
- items: embeddings, match calculations, budget
- push: decision delivery and feedback
- agent: orchestration, rules, LLM decisioning

## Public API baseline (current)

Auth

- POST /api/v1/auth/request_link
- GET /api/v1/auth/consume

Users

- GET /api/v1/users/me
- PUT /api/v1/users/me

Sources

- GET /api/v1/sources
- POST /api/v1/sources
- PUT /api/v1/sources/{id}
- POST /api/v1/sources/{id}/enable
- POST /api/v1/sources/{id}/disable

Goals

- GET /api/v1/goals
- POST /api/v1/goals
- GET /api/v1/goals/{id}
- PUT /api/v1/goals/{id}
- POST /api/v1/goals/{id}/pause
- POST /api/v1/goals/{id}/resume

Notifications and feedback

- GET /api/v1/notifications
- POST /api/v1/items/{id}/feedback
- GET /api/v1/r/{item_id}

Agent observability

- GET /api/v1/agent/runs
- GET /api/v1/agent/runs/{id}
- GET /api/v1/admin/budget

## Task pipeline baseline (current)

1. ingest source -> create items
2. embed items -> write vector
3. match items -> create goal_item_matches
4. agent decision -> create push_decisions
5. send email -> update delivery status

Queues (current)

- q_ingest
- q_embed
- q_match
- q_agent
- q_email

## Data model baseline (core tables)

- users, auth_magic_links, sessions
- sources
- goals, goal_push_configs, goal_priority_terms
- items, goal_item_matches
- push_decisions, click_events, item_feedback, blocked_sources
- agent_runs, agent_tool_calls, agent_action_ledger, budget_daily

## Cross module coupling hotspots

- agent depends on goals, items, push, users
- goals depends on items, push, users, sources
- items depends on goals and push feedback
- push depends on goals, items, sources

## Shared database ownership rules (initial)

Principles

- Each table has a single owner service that writes data.
- Non owners can read through their own DB connections, but only read.
- Cross service writes must go through owner service API, or via event handling.
- Idempotency keys are mandatory for write APIs.

Ownership matrix (initial)

| Table group | Owner service | Notes |
| --- | --- | --- |
| users, auth_magic_links, sessions | api-service | auth and profile |
| sources | worker-service | ingest and scheduling |
| goals, goal_push_configs, goal_priority_terms | api-service | configuration |
| items, goal_item_matches | worker-service | ingest, embed, match |
| push_decisions, click_events, item_feedback, blocked_sources | worker-service | delivery and feedback |
| agent_runs, agent_tool_calls, agent_action_ledger, budget_daily | ai-service | decision runtime and budget |

## Known constraints

- Single machine deployment must remain the default.
- Shared database is mandatory for cost reasons.
- Any new dependency requires explicit approval.

## Baseline artifacts to keep stable

- Table schemas and indexes
- Prompt files and versioning
- Budget and rate limit logic
