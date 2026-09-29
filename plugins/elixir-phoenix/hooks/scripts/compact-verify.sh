#!/usr/bin/env bash
# SessionStart (matcher: compact) hook: point Claude back at the active plan
# after compaction. stdout is added to Claude's context on SessionStart.

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
  echo "POST-COMPACTION: Active plan '${ACTIVE_PLAN}' detected. Re-read .claude/plans/${ACTIVE_PLAN}/plan.md and .claude/plans/${ACTIVE_PLAN}/scratchpad.md to restore context."
fi
