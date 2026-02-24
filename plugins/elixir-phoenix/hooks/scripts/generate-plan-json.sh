#!/usr/bin/env bash
# Generate plan.json sidecar from plan.md.
# Called by PostToolUse when a new plan.md is created (Write tool).
# Parses checkbox tasks and creates JSON representation.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# Only trigger for plan.md files on Write (new creation)
echo "$FILE_PATH" | grep -qE '\.claude/plans/[^/]+/plan\.md$' || exit 0
CONTENT=$(echo "$INPUT" | jq -r '.tool_input.content // empty')
if [[ -z "$CONTENT" ]]; then
  exit 0
fi

PLAN_DIR=$(dirname "$FILE_PATH")
JSON_FILE="${PLAN_DIR}/plan.json"

# Parse tasks from plan.md
# Format: - [ ] [Pn-Tm][agent] Description
# or:     - [x] [Pn-Tm][agent] Description
TASKS=$(echo "$CONTENT" | grep -oP '- \[[ x]\] \[P\d+-T\d+\]\[[^\]]+\] .+' || true)

if [ -z "$TASKS" ]; then
  exit 0
fi

# Build JSON
echo "{" > "$JSON_FILE"
echo '  "version": "1.0.0",' >> "$JSON_FILE"
echo "  \"source\": \"$(basename "$FILE_PATH")\"," >> "$JSON_FILE"
echo "  \"generated\": \"$(date -Iseconds)\"," >> "$JSON_FILE"
echo '  "tasks": [' >> "$JSON_FILE"

FIRST=true
echo "$TASKS" | while IFS= read -r line; do
  STATUS="pending"
  echo "$line" | grep -q '\[x\]' && STATUS="completed"

  TASK_ID=$(echo "$line" | grep -oP '\[P\d+-T\d+\]' | tr -d '[]')
  AGENT=$(echo "$line" | grep -oP '\]\[\K[^\]]+' | tail -1)
  DESC=$(echo "$line" | sed 's/^.*\] //')

  if [ "$FIRST" = true ]; then
    FIRST=false
  else
    echo ',' >> "$JSON_FILE"
  fi

  printf '    {"task_id": "%s", "agent": "%s", "status": "%s", "description": "%s"}' \
    "$TASK_ID" "$AGENT" "$STATUS" "$DESC" >> "$JSON_FILE"
done

echo '' >> "$JSON_FILE"
echo '  ]' >> "$JSON_FILE"
echo '}' >> "$JSON_FILE"
