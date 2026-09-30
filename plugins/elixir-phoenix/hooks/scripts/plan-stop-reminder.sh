#!/usr/bin/env bash
# PostToolUse hook: When a plan.md file is CREATED (Write, not Edit),
# remind Claude to STOP and present the plan to the user.
# Skips in /phx:full autonomous mode (detected by progress.md with State).

# Skip in non-Elixir projects (cross-project bleed guard — issue #55)
proj="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -f "$proj/mix.exs" ] || exit 0

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
printf '%s\n' \
  "" \
  "==========================================" \
  "STOP: Plan file created." \
  "==========================================" \
  "Don’t start implementing — the user reviews the plan first." \
  "Present a brief summary of the plan to the user," \
  "then use AskUserQuestion with options:" \
  "  - Start in fresh session (recommended)" \
  "  - Get a briefing (/phx:brief)" \
  "  - Start here" \
  "  - Review or adjust the plan" \
  "==========================================" >&2
exit 2
