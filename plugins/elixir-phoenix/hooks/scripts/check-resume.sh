#!/usr/bin/env bash
# SessionStart hook: Detect plans with remaining tasks
# Gated on mix.exs OR existing plans so non-Elixir projects don’t get the
# banner (issue #55 class), while projects already using the plan workflow
# (e.g. this plugin repo itself) keep their resume hints.
proj="${CLAUDE_PROJECT_DIR:-$PWD}"
is_elixir=0
[ -f "$proj/mix.exs" ] && is_elixir=1
has_plans=0
compgen -G "$proj/.claude/plans/*/plan.md" > /dev/null 2>&1 && has_plans=1
[ "$is_elixir" = 1 ] || [ "$has_plans" = 1 ] || exit 0

FOUND_PLAN=false
for dir in "$proj"/.claude/plans/*/; do
  [ -f "${dir}plan.md" ] || continue
  # grep -c prints the count even on zero matches (exiting 1), so no fallback
  # echo — `|| echo 0` would append a second line and garble the banner.
  UNCHECKED=$(grep -c '^\- \[ \]' "${dir}plan.md" 2>/dev/null)
  UNCHECKED=${UNCHECKED:-0}
  CHECKED=$(grep -c '^\- \[x\]' "${dir}plan.md" 2>/dev/null)
  CHECKED=${CHECKED:-0}
  if [ "$UNCHECKED" -gt 0 ]; then
    SLUG="$(basename "$dir")"
    echo "↻ Plan ‘${SLUG}’ has ${UNCHECKED} remaining tasks (${CHECKED} done). Resume with: /phx:work .claude/plans/${SLUG}/plan.md"
    FOUND_PLAN=true
  fi
done

# No-plan banner only in Elixir projects — sole owner of this banner (the
# former duplicate `echo` hook entry in hooks.json was removed).
if [ "$FOUND_PLAN" = false ] && [ "$is_elixir" = 1 ]; then
  echo "Elixir/Phoenix plugin loaded — describe your task and I’ll suggest the right workflow"
fi
