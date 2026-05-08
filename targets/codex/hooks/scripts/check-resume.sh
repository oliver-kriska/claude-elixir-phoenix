#!/usr/bin/env bash
# SessionStart hook: Detect plans with remaining tasks
FOUND_PLAN=false
for dir in .claude/plans/*/; do
  [ -f "${dir}plan.md" ] || continue
  UNCHECKED=$(grep -c '^\- \[ \]' "${dir}plan.md" 2>/dev/null || echo 0)
  CHECKED=$(grep -c '^\- \[x\]' "${dir}plan.md" 2>/dev/null || echo 0)
  if [ "$UNCHECKED" -gt 0 ]; then
    SLUG="$(basename "$dir")"
    echo "↻ Plan '${SLUG}' has ${UNCHECKED} remaining tasks (${CHECKED} done). Resume with: /phx:work .claude/plans/${SLUG}/plan.md"
    FOUND_PLAN=true
  fi
done

if [ "$FOUND_PLAN" = false ]; then
  echo "Elixir/Phoenix plugin loaded — describe your task and I'll suggest the right workflow"
fi
