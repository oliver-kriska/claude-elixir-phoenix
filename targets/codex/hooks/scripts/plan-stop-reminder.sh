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

# PostToolUse: exit 2 + stderr feeds message to Claude (stdout is verbose-mode only)
cat >&2 <<'MSG'

==========================================
STOP: Plan file created.
==========================================
Do NOT proceed to implementation.
Present a brief summary of the plan to the user,
then use AskUserQuestion with options:
  - Start in fresh session (recommended)
  - Start here
  - Review the plan
  - Adjust the plan
==========================================
MSG
exit 2
