---
name: git_commit_split
description: Split changes into minimal, logical commits with clear intent and safe boundaries. Use when preparing commits or asked to organize changes before committing.
---

# Git Commit Split (infoSentry)

Use this skill to partition changes into coherent commits that reflect intent and reduce review risk.

## Goals
- Each commit represents a single logical change (feature, fix, refactor, docs, test).
- Avoid mixing unrelated concerns (e.g., formatting + behavior changes).
- Preserve bisectability (builds/tests should pass per commit when feasible).

## Workflow

### 1) Inventory changes
- Run `git status` and `git diff` to list all changes.
- Group files by purpose: 
  - feature implementation
  - bug fix
  - refactor
  - test changes
  - docs/config

### 2) Propose commit plan
- Produce a commit plan with 2–6 commits max.
- Each commit should include:
  - files included
  - intent in one sentence
  - required tests (if any)

### 3) Stage by intent
- Use `git add <files>` or `git add -p` (only if non-interactive not required) to stage groups.
- Do not stage unrelated files together.
- Avoid staging generated files unless required.

### 4) Validate per commit
- Run targeted tests if present (e.g., unit tests for touched module).
- If full suite is heavy, note it and request confirmation.

### 5) Write concise commit messages
- Format: `<type>: <intent>`
  - types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
- Focus on **why** not **what**.

## Must do
- Keep changes minimal and consistent with repo conventions.
- Ask user before committing if not explicitly requested.
- Never commit secrets or `.env` files.

## Must not do
- Do not run interactive commands that block the agent.
- Do not amend commits unless explicitly requested.
- Do not combine unrelated changes in one commit.

## Output format
Return:
1. Proposed commit list (ordered)
2. Files per commit
3. Suggested commit messages
4. Tests to run per commit
