#!/usr/bin/env bash
# PostToolUse hook: When a plan.md file is CREATED (Write, not Edit),
# remind Claude to STOP and present the plan to the user.
# Skips in /phx:full autonomous mode (detected by progress.md with State).

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# Only trigger for plan.md files
echo "$FILE_PATH" | grep -qE '\.claude/plans/[^/]+/plan\.md$' || exit 0

# Only trigger on Write (new plan creation), not Edit (checkbox updates).
# Write tool has .tool_input.content; Edit tool has .tool_input.old_string.
CONTENT=$(echo "$INPUT" | jq -r '.tool_input.content // empty')
if [[ -z "$CONTENT" ]]; then
  exit 0
fi

# Skip in /phx:full autonomous mode — workflow-orchestrator creates
# progress.md with **State**: field during INITIALIZING.
PLAN_DIR=$(dirname "$FILE_PATH")
if [ -f "${PLAN_DIR}/progress.md" ] && grep -q '\*\*State\*\*:' "${PLAN_DIR}/progress.md" 2>/dev/null; then
  exit 0
fi

# Skip for annotation cycles — plan is being refined, not newly created
if grep -q '\*\*Annotation Cycles\*\*:' "$FILE_PATH" 2>/dev/null; then
  exit 0
fi

echo ""
echo "=========================================="
echo "STOP: Plan file created."
echo "=========================================="
echo "Do NOT proceed to implementation."
echo "Present a brief summary of the plan to the user,"
echo "then use AskUserQuestion with options:"
echo "  - Start in fresh session (recommended)"
echo "  - Start here"
echo "  - Review the plan"
echo "  - Adjust the plan"
echo "=========================================="
