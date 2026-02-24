#!/usr/bin/env bash
# Validate plan.md structure and plan.json schema after edits.
# Runs on Edit of plan.md files. Checks checkbox format and
# optional JSON sidecar consistency.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# Only trigger for plan.md files
echo "$FILE_PATH" | grep -qE '\.claude/plans/[^/]+/plan\.md$' || exit 0

PLAN_DIR=$(dirname "$FILE_PATH")

# Validate task ID format
INVALID_TASKS=$(grep -nP '- \[[ x]\] \[(?!P\d+-T\d+\])' "$FILE_PATH" 2>/dev/null || true)
if [ -n "$INVALID_TASKS" ]; then
  echo ""
  echo "WARNING: Invalid task ID format detected:"
  echo "$INVALID_TASKS"
  echo "Expected: [Pn-Tm] (e.g., [P1-T1], [P2-T3])"
fi

# Check for duplicate task IDs
DUPES=$(grep -oP '\[P\d+-T\d+\]' "$FILE_PATH" 2>/dev/null | sort | uniq -d)
if [ -n "$DUPES" ]; then
  echo ""
  echo "WARNING: Duplicate task IDs found: $DUPES"
fi

# If plan.json exists, check for mismatch
JSON_FILE="${PLAN_DIR}/plan.json"
if [ -f "$JSON_FILE" ]; then
  MD_COMPLETED=$(grep -c '\[x\]' "$FILE_PATH" 2>/dev/null || echo 0)
  JSON_COMPLETED=$(grep -c '"completed"' "$JSON_FILE" 2>/dev/null || echo 0)

  if [ "$MD_COMPLETED" != "$JSON_COMPLETED" ]; then
    echo ""
    echo "INTEGRITY: plan.md ($MD_COMPLETED completed) vs plan.json ($JSON_COMPLETED completed) mismatch"
    echo "Plan.md is source of truth. Run sync to update plan.json."
  fi
fi
