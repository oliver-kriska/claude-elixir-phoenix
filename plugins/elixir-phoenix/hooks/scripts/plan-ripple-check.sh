#!/usr/bin/env bash
# PostToolUse hook: When a plan.md is EDITED (not created), remind about
# consistency with progress.md and scratchpad.md.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# Only trigger for plan.md files
echo "$FILE_PATH" | grep -qE '\.claude/plans/[^/]+/plan\.md$' || exit 0

# Only trigger on Edit (not Write — Write is new plan creation handled by plan-stop-reminder)
OLD_STRING=$(echo "$INPUT" | jq -r '.tool_input.old_string // empty')
if [[ -z "$OLD_STRING" ]]; then
  exit 0
fi

PLAN_DIR=$(dirname "$FILE_PATH")

# Check if sibling files exist and might need updating
NEEDS_UPDATE=""
if [ -f "${PLAN_DIR}/progress.md" ]; then
  NEEDS_UPDATE="${NEEDS_UPDATE}progress.md "
fi
if [ -f "${PLAN_DIR}/scratchpad.md" ]; then
  NEEDS_UPDATE="${NEEDS_UPDATE}scratchpad.md "
fi

if [ -n "$NEEDS_UPDATE" ]; then
  echo ""
  echo "RIPPLE CHECK: plan.md was edited."
  echo "Verify consistency with: ${NEEDS_UPDATE}"
fi
