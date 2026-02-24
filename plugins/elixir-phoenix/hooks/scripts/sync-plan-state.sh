#!/usr/bin/env bash
# Sync plan.md checkbox state to plan.json after task completion.
# Runs async after Edit on plan.md files.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# Only trigger for plan.md files
echo "$FILE_PATH" | grep -qE '\.claude/plans/[^/]+/plan\.md$' || exit 0

# Only trigger on Edit (checkbox updates), not Write (new plan)
OLD_STRING=$(echo "$INPUT" | jq -r '.tool_input.old_string // empty')
if [[ -z "$OLD_STRING" ]]; then
  exit 0
fi

PLAN_DIR=$(dirname "$FILE_PATH")
JSON_FILE="${PLAN_DIR}/plan.json"

# Skip if no JSON sidecar exists
[ -f "$JSON_FILE" ] || exit 0

# Update completed status in JSON based on plan.md checkboxes
# Read all task IDs and their status from plan.md
grep -oP '- \[([ x])\] \[(P\d+-T\d+)\]' "$FILE_PATH" 2>/dev/null | while IFS= read -r match; do
  if echo "$match" | grep -q '\[x\]'; then
    TASK_ID=$(echo "$match" | grep -oP 'P\d+-T\d+')
    # Update JSON status to completed (in-place with sed)
    sed -i "s/\"task_id\": \"$TASK_ID\", \(.*\)\"status\": \"[^\"]*\"/\"task_id\": \"$TASK_ID\", \1\"status\": \"completed\"/" "$JSON_FILE" 2>/dev/null
  fi
done
