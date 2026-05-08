#!/usr/bin/env bash
# Stop hook: Warn about plans with uncompleted tasks
# Guard against infinite loops per Claude Code docs
INPUT=$(cat)
if [ "$(echo "$INPUT" | jq -r '.stop_hook_active' 2>/dev/null)" = "true" ]; then
  exit 0
fi
PENDING=$(grep -rl '\[ \]' .claude/plans/*/plan.md 2>/dev/null | wc -l | tr -d ' ')
if [[ "$PENDING" -gt 0 ]]; then
  echo "⚠ $PENDING plan(s) have uncompleted tasks"
fi
