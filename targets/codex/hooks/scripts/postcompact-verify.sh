#!/usr/bin/env bash
# PostCompact hook: Verify critical state survived compaction.
# Checks for active plan state and warns if plan context may have been lost.
# Uses stderr + exit 2 to feed messages back to Claude.

ACTIVE_PLAN=""
for dir in .claude/plans/*/; do
  [ -d "$dir" ] || continue
  if [ -f "${dir}plan.md" ]; then
    if grep -q '^\- \[ \]' "${dir}plan.md" 2>/dev/null; then
      ACTIVE_PLAN="$(basename "$dir")"
      break
    fi
  fi
done

if [ -n "$ACTIVE_PLAN" ]; then
  echo "POST-COMPACTION: Active plan '${ACTIVE_PLAN}' detected. Re-read .claude/plans/${ACTIVE_PLAN}/plan.md and .claude/plans/${ACTIVE_PLAN}/scratchpad.md to restore context." >&2
  exit 2
fi
