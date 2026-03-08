#!/usr/bin/env bash
# ai_repo_checks.sh — Lightweight anti-drift checks for AI repository governance
# Run: bash scripts/ai_repo_checks.sh

set -uo pipefail

PASS=0
FAIL=0

check() {
  local desc="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "  PASS  $desc"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  $desc"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== AI Repository Governance Checks ==="
echo ""

# 1. Canonical directories exist with real content
echo "--- Canonical directories ---"
check "skills/ exists and has files" test -n "$(find skills -type f -name '*.md' 2>/dev/null | head -1)"
check "specs/ exists and has files" test -n "$(find specs -type f -name '*.md' 2>/dev/null | head -1)"
check "agents/ exists and has files" test -n "$(find agents -type f -name '*.md' 2>/dev/null | head -1)"
check "runbooks/ exists and has files" test -n "$(find runbooks -type f -name '*.md' 2>/dev/null | head -1)"

# 2. No authoritative skill bodies in hidden tool directories
echo ""
echo "--- No duplicate skill bodies in tool directories ---"
check "No SKILL.md under .claude/skills/" test -z "$(find .claude/skills -name 'SKILL.md' 2>/dev/null | head -1)"
check "No SKILL.md under .codex/skills/" test -z "$(find .codex/skills -name 'SKILL.md' 2>/dev/null | head -1)"
check "No SKILL.md under .agents/skills/" test -z "$(find .agents/skills -name 'SKILL.md' 2>/dev/null | head -1)"

# 3. Prompt-eval coverage
echo ""
echo "--- Prompt-eval coverage ---"
for prompt_dir in infoSentry-backend/prompts/*/*/; do
  if [ -d "$prompt_dir" ]; then
    # Extract prompt name: agent/boundary_judge -> agent.boundary_judge
    rel="${prompt_dir#infoSentry-backend/prompts/}"
    rel="${rel%/}"
    eval_name="$(echo "$rel" | sed 's|/|.|g')"
    check "Eval exists for $eval_name" test -n "$(find infoSentry-backend/evals/prompt_regression -name "${eval_name}*.json" 2>/dev/null | head -1)"
  fi
done

# 4. AGENTS.md references canonical locations
echo ""
echo "--- AGENTS.md governance section ---"
check "AGENTS.md has canonical locations section" grep -q "Canonical repository locations" AGENTS.md

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
