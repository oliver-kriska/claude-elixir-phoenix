#!/usr/bin/env bash
# Stop hook: warn about pending plan tasks and running background work.
# Non-blocking — stdout only (visible in terminal). Guard against loops.
INPUT=$(cat)
if [ "$(echo "$INPUT" | jq -r '.stop_hook_active' 2>/dev/null)" = "true" ]; then
  exit 0
fi

PENDING=$(grep -rl '\[ \]' .claude/plans/*/plan.md 2>/dev/null | wc -l | tr -d ' ')
if [[ "$PENDING" -gt 0 ]]; then
  echo "⚠ $PENDING plan(s) have uncompleted tasks"
fi

# CC 2.1.145+: Stop hook input includes background_tasks[] and session_crons[].
# Surface running background work (mix phx.server, iex, mix watch, scheduled jobs).
BG_COUNT=$(echo "$INPUT" | jq -r '(.background_tasks // []) | length' 2>/dev/null)
if [[ "$BG_COUNT" =~ ^[0-9]+$ ]] && (( BG_COUNT > 0 )); then
  echo "⚠ $BG_COUNT background task(s) still running — stop them or detach explicitly"
fi
CRON_COUNT=$(echo "$INPUT" | jq -r '(.session_crons // []) | length' 2>/dev/null)
if [[ "$CRON_COUNT" =~ ^[0-9]+$ ]] && (( CRON_COUNT > 0 )); then
  echo "⚠ $CRON_COUNT session cron(s) scheduled — see /schedule list"
fi
