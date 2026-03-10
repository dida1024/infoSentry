# AI-Friendly Architecture Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate infoSentry's AI-facing repository architecture into a single source of truth for skills, specs, prompts, evaluations, traces, and runbooks without disrupting the existing backend/frontend code layout.

**Architecture:** Keep `infoSentry-backend/` and `infosentry-web/` in place, then add a thin AI-governance layer around them: one repository-local skill source, one agent/policy source, one spec source, one evaluation source, one trace source, and one runbook source. Do this in phases so the repository gets more AI-friendly immediately while avoiding a risky top-level code migration.

**Tech Stack:** Markdown docs, repository layout conventions, existing FastAPI/Next.js/Celery monorepo, prompt assets, pytest/mypy, frontend lint/build.

---

## Scope

This plan covers repository information architecture and AI engineering governance, not product feature delivery. It includes:

- skill directory consolidation
- AI-facing documentation restructuring
- prompt/eval/trace/runbook governance
- replay/observability planning hooks
- rollout and validation rules

This plan explicitly does not include:

- moving backend code into a new `app/` directory
- replacing DDD module layout in `infoSentry-backend/src/modules/**`
- full LangGraph migration in this phase
- adding new dependencies

## Current-State Summary

Current repository strengths:

- Strong project rules already exist in [`AGENTS.md`](/Users/ray/Documents/code/infoSentry/AGENTS.md).
- Backend has an `agent` runtime, prompt store, replay-related code, and prompt regression coverage.
- There is already a monorepo split between [`infoSentry-backend/`](/Users/ray/Documents/code/infoSentry/infoSentry-backend) and [`infosentry-web/`](/Users/ray/Documents/code/infoSentry/infosentry-web).

Current repository problems:

- skills are split across `.codex/`, `.claude/`, and `.agents/`
- docs are spread across `docs/agents`, `docs/specs`, `docs/ops`, and tool-specific hidden folders
- prompt assets exist, but evals/traces/runbooks are not unified into one AI governance system
- runtime replay/observability is only partially exposed to operators
- repository context for AI assistants is fragmented rather than layered

## Target Repository Model

Target layout after this optimization:

```text
infoSentry/
  AGENTS.md
  skills/
  agents/
  specs/
  docs/architecture/
  memory-bank/
  evals/
  traces/
  runbooks/
  scripts/
  infoSentry-backend/
  infosentry-web/
```

### Directory Responsibilities

- `AGENTS.md`
  - Repository-wide hard rules
  - Tool-agnostic policy and delivery guardrails
  - No duplicated skill bodies
- `skills/`
  - The only repository-local source of truth for reusable skills
  - Backend/frontend/release/git/project workflow skills
- `agents/`
  - Agent role definitions, policies, runtime contracts, prompt governance, action-logging expectations
- `specs/`
  - Product specs, API specs, acceptance rules, migration specs, AI architecture plans
- `docs/architecture/`
  - Stable system architecture explanations and ADR-adjacent material
- `memory-bank/`
  - Working context for active initiatives, decisions, status, glossary, AI context pack
- `evals/`
  - Prompt regression, decision goldens, schema contract checks, replay comparison cases
- `traces/`
  - Curated runtime traces, run samples, failure exemplars, diff snapshots
- `runbooks/`
  - Failure response procedures for queues, workers, prompts, budgets, email, replay, and degraded AI modes
- `scripts/`
  - Validation and support scripts only, not policy documents

## Migration Strategy

Use a four-layer migration order:

1. Policy layer
2. Knowledge layer
3. Evaluation layer
4. Runtime/operations layer

Reasoning:

- Policy must stabilize first so future edits follow one standard.
- Knowledge needs a stable home before evaluation and runbooks can reference it.
- Evals and traces become useful only after source-of-truth paths are fixed.
- Runtime/ops improvements should consume the new documentation and trace conventions rather than invent their own.

## Phase Plan

### Phase 0: Freeze the Rules and Name the Sources of Truth

**Objective:** Stop further drift while the repository is being cleaned up.

**Deliverables:**

- Updated `AGENTS.md` naming the canonical locations for skills, agent docs, specs, evals, traces, and runbooks
- Decision note explaining why `.claude/.codex/.agents` are being consolidated
- Temporary migration note for contributors

**Files:**

- Modify: `/Users/ray/Documents/code/infoSentry/AGENTS.md`
- Create: `/Users/ray/Documents/code/infoSentry/docs/architecture/ai-repository-governance.md`
- Create: `/Users/ray/Documents/code/infoSentry/memory-bank/README.md`

**Step 1: Write the failing documentation assertions**

Create a checklist in the governance doc asserting:

- repository-local skills must live in exactly one place
- project-level rules must not be duplicated in tool-specific hidden directories
- AI docs must reference canonical paths only

**Step 2: Validate the current duplication state**

Run:

```bash
find .claude .codex .agents -maxdepth 4 -type f | sort
rg -n --hidden -S "SKILL.md|skills/|claude.md|AGENTS.md" . --glob '!**/.git/**'
```

Expected:

- multiple skill-bearing directories are listed
- at least one overlap or split responsibility is visible

**Step 3: Define the canonical map**

Write into the governance doc:

- `skills/` is canonical for repository-local skill bodies
- `AGENTS.md` is canonical for repository-wide rules
- `agents/` is canonical for agent runtime policy and prompt governance
- `specs/` is canonical for product/API/acceptance specs
- `runbooks/` is canonical for operational response

**Step 4: Update `AGENTS.md` minimally**

Add a short section naming the canonical locations and stating that tool-specific folders may only contain adapter metadata.

**Step 5: Commit**

```bash
git add AGENTS.md docs/architecture/ai-repository-governance.md memory-bank/README.md
git commit -m "docs: define canonical AI repository governance"
```

### Phase 1: Consolidate Skills into a Single Repository Source

**Objective:** Eliminate duplicated skill bodies across `.claude`, `.codex`, and `.agents`.

**Deliverables:**

- New top-level `skills/`
- Migrated repository-local skills from `.codex/skills/**`
- Explicit handling decision for `.claude/skills/**` and `.agents/skills/**`
- Thin tool adapters only in hidden tool directories

**Files:**

- Create: `/Users/ray/Documents/code/infoSentry/skills/`
- Move: `/Users/ray/Documents/code/infoSentry/.codex/skills/**` -> `/Users/ray/Documents/code/infoSentry/skills/**`
- Review and merge or delete: `/Users/ray/Documents/code/infoSentry/.claude/skills/**`
- Review and merge or delete: `/Users/ray/Documents/code/infoSentry/.agents/skills/**`
- Modify: `/Users/ray/Documents/code/infoSentry/.claude/claude.md`
- Modify: `/Users/ray/Documents/code/infoSentry/.gitignore`

**Step 1: Inventory all skills and classify them**

Create a migration table with these columns:

- current path
- skill name
- project-local or personal/global
- duplicate of another skill or not
- target action: move, merge, or remove

Run:

```bash
find .codex/skills .claude/skills .agents/skills -type f | sort
```

**Step 2: Create the new canonical `skills/` root**

Create subdirectories preserving logical groups, for example:

```text
skills/backend/
skills/frontend/
skills/release/
skills/git/
skills/process/
```

**Step 3: Move the current canonical skill bodies**

Treat `.codex/skills/**` as the starting canonical source unless a `.claude/skills/**` version is newer and demonstrably better.

**Step 4: Replace duplicated tool-specific skill bodies with references**

Keep `.claude/` for adapter material only. If a tool requires a local reference file, make it a pointer doc rather than a second full skill body.

**Step 5: Verify repository references**

Run:

```bash
rg -n --hidden -S "\.codex/skills|\.claude/skills|\.agents/skills|skills/" . --glob '!**/.git/**'
```

Expected:

- repository docs reference `skills/` as canonical
- hidden tool directories do not remain the authoritative skill store

**Step 6: Commit**

```bash
git add skills .claude .agents .codex .gitignore
git commit -m "refactor: consolidate repository-local skills"
```

### Phase 2: Split AI Knowledge into Stable Layers

**Objective:** Separate architecture, specs, agent policy, and working memory so AI assistants can load only the necessary context.

**Deliverables:**

- top-level `agents/`
- top-level `specs/`
- `docs/architecture/`
- `memory-bank/`
- path migration map from old docs to new canonical docs

**Files:**

- Create: `/Users/ray/Documents/code/infoSentry/agents/README.md`
- Create: `/Users/ray/Documents/code/infoSentry/specs/README.md`
- Create: `/Users/ray/Documents/code/infoSentry/docs/architecture/README.md`
- Create: `/Users/ray/Documents/code/infoSentry/memory-bank/ai-context-pack.md`
- Move or copy canonical content from:
  - `/Users/ray/Documents/code/infoSentry/docs/agents/AGENT_RUNTIME_SPEC.md`
  - `/Users/ray/Documents/code/infoSentry/docs/agents/AI_SKILLS.md`
  - `/Users/ray/Documents/code/infoSentry/docs/specs/API_SPEC_v0.md`
  - `/Users/ray/Documents/code/infoSentry/docs/specs/TECH_SPEC_v0.md`
  - `/Users/ray/Documents/code/infoSentry/docs/specs/ai_langgraph_design.md`
  - `/Users/ray/Documents/code/infoSentry/docs/ops/RUNBOOK_VM.md`

**Step 1: Define canonical file placement rules**

Use this mapping:

- runtime contracts and agent policies -> `agents/`
- product/API/acceptance specs -> `specs/`
- stable architecture descriptions -> `docs/architecture/`
- fast-changing operational context and initiative notes -> `memory-bank/`

**Step 2: Create an `ai-context-pack.md`**

This file must include:

- repository map
- system topology
- queue topology
- prompt inventory
- source-of-truth map
- required checks
- active known gaps

**Step 3: Add migration stubs in old locations**

For any moved document, leave a short note in the old file or an index file pointing to the canonical new path until the team fully switches.

**Step 4: Update cross-links**

Run:

```bash
rg -n "docs/agents|docs/specs|docs/ops|docs/architecture|specs/|agents/|memory-bank/" AGENTS.md docs skills .claude .codex .agents --glob '!**/.git/**'
```

Expected:

- new canonical paths appear in repository-level guidance
- old paths are either redirected or clearly marked transitional

**Step 5: Commit**

```bash
git add agents specs docs/architecture memory-bank docs
git commit -m "docs: layer AI-facing repository knowledge"
```

### Phase 3: Establish AI Evaluation Governance

**Objective:** Make prompts and agent decisions testable and reviewable as first-class repository assets.

**Deliverables:**

- top-level `evals/`
- prompt regression structure
- agent decision golden cases
- replay comparison case format
- evaluation index and ownership rules

**Files:**

- Create: `/Users/ray/Documents/code/infoSentry/evals/README.md`
- Create: `/Users/ray/Documents/code/infoSentry/evals/prompt-regression/README.md`
- Create: `/Users/ray/Documents/code/infoSentry/evals/agent-decisions/README.md`
- Create: `/Users/ray/Documents/code/infoSentry/evals/replay-diffs/README.md`
- Move or mirror from: `/Users/ray/Documents/code/infoSentry/infoSentry-backend/evals/prompt_regression/**`
- Review prompt coverage for:
  - `agent.boundary_judge`
  - `agent.push_worthiness`
  - `goals.goal_draft`
  - `goals.keyword_suggestion`

**Step 1: Define the eval taxonomy**

- prompt regression: rendering and guardrails
- schema contract: output structure guarantees
- decision goldens: expected label/reason/fallback behaviors
- replay diffs: compare current runtime behavior against saved snapshots

**Step 2: Fill coverage gaps**

Current prompt eval coverage is incomplete. Ensure every prompt file has at least one matching eval case.

**Step 3: Define required metadata for each eval case**

Each eval file should include:

- owner
- purpose
- prompt or runtime target
- input fixture
- expected invariants
- change sensitivity notes

**Step 4: Add repository-level rules**

Document these rules:

- prompt change requires eval review
- prompt version bump requires eval update
- runtime decision policy change requires a trace or replay diff sample

**Step 5: Verification**

Run:

```bash
find evals -maxdepth 3 -type f | sort
find infoSentry-backend/prompts -type f | sort
```

Expected:

- eval inventory is visible at top level
- every prompt has a corresponding eval location

**Step 6: Commit**

```bash
git add evals infoSentry-backend/evals infoSentry-backend/prompts AGENTS.md
git commit -m "docs: establish AI evaluation governance"
```

### Phase 4: Establish Trace and Replay Governance

**Objective:** Turn replay, run inspection, and failure analysis into stable repository assets instead of ad hoc debugging.

**Deliverables:**

- top-level `traces/`
- trace schema/template
- replay sample format
- failure-case catalog
- operator-facing trace selection guidance

**Files:**

- Create: `/Users/ray/Documents/code/infoSentry/traces/README.md`
- Create: `/Users/ray/Documents/code/infoSentry/traces/templates/trace-template.md`
- Create: `/Users/ray/Documents/code/infoSentry/traces/templates/replay-diff-template.md`
- Create: `/Users/ray/Documents/code/infoSentry/traces/examples/`
- Reference code and runtime behavior in:
  - `/Users/ray/Documents/code/infoSentry/infoSentry-backend/src/modules/agent/application/orchestrator.py`
  - `/Users/ray/Documents/code/infoSentry/infoSentry-backend/src/modules/agent/application/services.py`
  - `/Users/ray/Documents/code/infoSentry/infoSentry-backend/src/modules/agent/interfaces/router.py`

**Step 1: Define the trace schema**

Each trace should capture:

- run id or synthetic case id
- trigger
- inputs
- prompt/model version if applicable
- key tool calls
- final decision/actions
- fallback reason
- operator notes

**Step 2: Define replay diff artifacts**

Each replay diff should capture:

- original snapshot
- replayed result
- differences
- classification: expected drift or regression
- follow-up action

**Step 3: Link traces to evals and runbooks**

A trace should point to:

- related eval case
- related runbook
- related prompt or policy file

**Step 4: Commit**

```bash
git add traces
git commit -m "docs: define AI trace and replay governance"
```

### Phase 5: Establish Runbook Governance for AI Operations

**Objective:** Make failure handling for AI subsystems explicit, repeatable, and discoverable.

**Deliverables:**

- top-level `runbooks/`
- AI operations index
- queue/worker/replay/prompt/budget/email runbooks
- cross-links from runbooks to traces and specs

**Files:**

- Create: `/Users/ray/Documents/code/infoSentry/runbooks/README.md`
- Create: `/Users/ray/Documents/code/infoSentry/runbooks/agent-runtime.md`
- Create: `/Users/ray/Documents/code/infoSentry/runbooks/prompt-regressions.md`
- Create: `/Users/ray/Documents/code/infoSentry/runbooks/celery-queues-and-workers.md`
- Create: `/Users/ray/Documents/code/infoSentry/runbooks/email-delivery.md`
- Create: `/Users/ray/Documents/code/infoSentry/runbooks/budget-and-feature-flags.md`
- Review source material from:
  - `/Users/ray/Documents/code/infoSentry/docs/ops/RUNBOOK_VM.md`
  - `/Users/ray/Documents/code/infoSentry/docker-compose.yml`
  - `/Users/ray/Documents/code/infoSentry/infoSentry-backend/src/modules/agent/tasks.py`

**Step 1: Define runbook template**

Each runbook should include:

- symptom
- scope
- prerequisites
- commands to inspect
- expected healthy signals
- likely causes
- recovery actions
- evidence to collect
- related traces/evals/specs

**Step 2: Prioritize the AI-critical runbooks**

Order:

1. agent runtime
2. celery queues and worker heartbeat
3. prompt regressions
4. email delivery and delivery guardrails
5. budget and feature flags

**Step 3: Add operational evidence rules**

Document that AI flow incidents cannot be declared fixed without:

- test evidence
- runtime evidence
- queue/worker evidence
- if applicable, DB transition evidence

**Step 4: Commit**

```bash
git add runbooks docs/ops
git commit -m "docs: add AI operations runbooks"
```

### Phase 6: Add Maintenance Rules and CI Entry Points

**Objective:** Prevent the repository from drifting back into the current fragmented state.

**Deliverables:**

- maintenance policy in `AGENTS.md`
- doc ownership notes
- optional validation script index in `scripts/`
- contributor checklist for AI-facing changes

**Files:**

- Modify: `/Users/ray/Documents/code/infoSentry/AGENTS.md`
- Create: `/Users/ray/Documents/code/infoSentry/scripts/ai_repo_checks.sh`
- Create: `/Users/ray/Documents/code/infoSentry/memory-bank/change-checklists.md`

**Step 1: Add change rules**

Rules to encode:

- skill changes must only happen under `skills/`
- prompt changes require eval review
- agent policy changes require trace or replay sample update
- operational procedure changes require runbook update
- config changes require spec and `.env.example` review

**Step 2: Add lightweight repository checks**

`ai_repo_checks.sh` should validate at minimum:

- no duplicate repository-local skill bodies under hidden tool directories
- required top-level AI governance directories exist
- prompt inventory and eval inventory can be listed cleanly

**Step 3: Document contributor workflow**

Add a concise checklist for:

- docs-only change
- prompt change
- runtime policy change
- operational incident fix

**Step 4: Verify**

Run:

```bash
bash scripts/ai_repo_checks.sh
```

Expected:

- clean pass on directory and governance assertions

**Step 5: Commit**

```bash
git add AGENTS.md scripts memory-bank
git commit -m "chore: add AI repository maintenance checks"
```

## Detailed Task Breakdown for Execution

### Task 1: Governance foundation

**Files:**

- Modify: `/Users/ray/Documents/code/infoSentry/AGENTS.md`
- Create: `/Users/ray/Documents/code/infoSentry/docs/architecture/ai-repository-governance.md`
- Create: `/Users/ray/Documents/code/infoSentry/memory-bank/README.md`

**Execution notes:**

- Keep `AGENTS.md` concise and tool-agnostic.
- Put migration rationale into `docs/architecture`, not into tool-specific hidden files.
- Treat this task as the prerequisite for every later task.

### Task 2: Skill source-of-truth migration

**Files:**

- Create: `/Users/ray/Documents/code/infoSentry/skills/`
- Modify: `/Users/ray/Documents/code/infoSentry/.claude/claude.md`
- Modify: `/Users/ray/Documents/code/infoSentry/.gitignore`
- Remove or de-authorize: repository-local skill bodies under hidden directories

**Execution notes:**

- Prefer move-plus-reference rather than copy-plus-fork.
- Preserve skill grouping names unless they are misleading.
- Keep tool adapters minimal.

### Task 3: Knowledge-layer split

**Files:**

- Create: `/Users/ray/Documents/code/infoSentry/agents/README.md`
- Create: `/Users/ray/Documents/code/infoSentry/specs/README.md`
- Create: `/Users/ray/Documents/code/infoSentry/docs/architecture/README.md`
- Create: `/Users/ray/Documents/code/infoSentry/memory-bank/ai-context-pack.md`

**Execution notes:**

- Do not duplicate long docs unnecessarily.
- If moving is risky, create canonical copies plus clear redirects, then clean later.

### Task 4: Eval baseline

**Files:**

- Create: `/Users/ray/Documents/code/infoSentry/evals/**`
- Review: `/Users/ray/Documents/code/infoSentry/infoSentry-backend/evals/**`
- Review: `/Users/ray/Documents/code/infoSentry/infoSentry-backend/prompts/**`

**Execution notes:**

- Coverage completeness matters more than sophistication in the first pass.
- Ensure the missing `agent.push_worthiness` case is added during execution.

### Task 5: Trace and replay baseline

**Files:**

- Create: `/Users/ray/Documents/code/infoSentry/traces/**`
- Review: `/Users/ray/Documents/code/infoSentry/infoSentry-backend/src/modules/agent/application/orchestrator.py`
- Review: `/Users/ray/Documents/code/infoSentry/infoSentry-backend/src/modules/agent/application/services.py`

**Execution notes:**

- Separate curated repository traces from raw production data dumps.
- Store templates and sanitized examples only.

### Task 6: Runbook baseline

**Files:**

- Create: `/Users/ray/Documents/code/infoSentry/runbooks/**`
- Review: `/Users/ray/Documents/code/infoSentry/docs/ops/RUNBOOK_VM.md`
- Review: `/Users/ray/Documents/code/infoSentry/docker-compose.yml`

**Execution notes:**

- Focus on operator workflow, not architecture theory.
- Each runbook should end with evidence collection requirements.

### Task 7: Anti-drift guardrails

**Files:**

- Modify: `/Users/ray/Documents/code/infoSentry/AGENTS.md`
- Create: `/Users/ray/Documents/code/infoSentry/scripts/ai_repo_checks.sh`
- Create: `/Users/ray/Documents/code/infoSentry/memory-bank/change-checklists.md`

**Execution notes:**

- Keep checks lightweight enough to run frequently.
- Avoid adding external tooling in this phase.

## Risks and Mitigations

### Risk 1: Documentation churn without actual behavior change

Mitigation:

- Define this initiative as governance infrastructure, not runtime feature work.
- Pair Phase 3 and Phase 4 outputs with real prompt/eval/replay examples.

### Risk 2: Tool-specific adapters drift again

Mitigation:

- Keep hidden tool folders adapter-only.
- Encode this rule in `AGENTS.md` and `ai_repo_checks.sh`.

### Risk 3: Too many new top-level directories too quickly

Mitigation:

- Create directories only when their seed documents are written.
- Avoid empty placeholder trees.

### Risk 4: Team confusion during transition

Mitigation:

- Add temporary redirects and explicit migration notes.
- Record canonical paths in one short index doc.

### Risk 5: Reorg collides with active feature work

Mitigation:

- Execute in a dedicated branch or worktree.
- Land the plan in small commits.
- Freeze structural changes during release-critical work.

## Acceptance Criteria

This initiative is complete only when all of the following are true:

- repository-local skills have one canonical source
- `AGENTS.md` names the canonical locations for AI-facing repository artifacts
- `agents/`, `specs/`, `docs/architecture/`, `memory-bank/`, `evals/`, `traces/`, and `runbooks/` exist with real seed content
- prompt assets and eval assets have a documented mapping
- replay/trace artifacts have a documented schema and examples
- runbooks exist for agent runtime, queue/workers, prompt regression, delivery, and budget/feature flags
- hidden tool directories are no longer the authority for repository-local skill bodies
- lightweight anti-drift checks exist and pass

## Verification Commands

Use these commands during execution and before claiming completion:

```bash
find skills agents specs docs/architecture memory-bank evals traces runbooks -maxdepth 2 -type f | sort
rg -n --hidden -S "\.codex/skills|\.claude/skills|\.agents/skills|skills/" . --glob '!**/.git/**'
find infoSentry-backend/prompts -type f | sort
find evals -maxdepth 3 -type f | sort
bash scripts/ai_repo_checks.sh
uv run pytest
uv run mypy src
npm run lint
npm run build
```

Expected notes:

- backend and frontend commands are only mandatory when code or typed interfaces are touched
- if this initiative remains docs/scripts only, report non-run commands explicitly rather than pretending they were executed

## Recommended Execution Order

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3
5. Phase 4
6. Phase 5
7. Phase 6

## Recommendation on Delivery Mode

Use a dedicated worktree for execution. This initiative is large enough that it should not be mixed with product feature work.

Suggested branch names:

```bash
feat/ai-repo-governance
chore/ai-friendly-architecture
```

Plan complete and saved to `docs/plans/2026-03-08-ai-friendly-architecture-optimization-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
