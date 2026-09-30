#!/usr/bin/env bash
# SessionStart (matcher: compact) hook: re-inject SKILL-SPECIFIC workflow rules
# after compaction. Iron Laws from CLAUDE.md survive compaction (system prompt),
# so only rules from loaded skills, which live in conversation context, need it.
#
# SessionStart stdout is the channel that reaches Claude. PreCompact/PostCompact
# can't: their systemMessage and stderr are shown to the user only.

# Skip in non-Elixir projects (cross-project bleed guard — issue #55)
proj="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -f "$proj/mix.exs" ] || exit 0

# Print the "## Dead Ends" section, heading included, through the next "## "
# heading.
dead_ends_section() {
  local in_section=0 line
  while IFS= read -r line || [[ -n "$line" ]]; do
    if (( in_section )); then
      printf '%s\n' "$line"
      [[ $line == "## "* ]] && in_section=0
    elif [[ $line == "## Dead Ends"* ]]; then
      printf '%s\n' "$line"
      in_section=1
    fi
  done < "$1"
}

FULL_MODE=false
ACTIVE_PLAN=false
ACTIVE_WORK=false

for dir in .claude/plans/*/; do
  [ -d "$dir" ] || continue

  # Check for /phx:full autonomous mode
  if [ -f "${dir}progress.md" ] && grep -q '\*\*State\*\*:' "${dir}progress.md" 2>/dev/null; then
    FULL_MODE=true
    continue
  fi

  # Research exists but no plan yet = mid /phx:plan
  if [ -d "${dir}research" ] && [ ! -f "${dir}plan.md" ]; then
    ACTIVE_PLAN=true
  fi

  # Plan exists with PENDING status and unchecked tasks = planning or about to work
  if [ -f "${dir}plan.md" ]; then
    if grep -q 'Status.*PENDING' "${dir}plan.md" 2>/dev/null; then
      ACTIVE_PLAN=true
    elif grep -q '^\- \[ \]' "${dir}plan.md" 2>/dev/null; then
      ACTIVE_WORK=true
    fi
  fi
done

# Extract slug + intent from the active plan for context preservation
PLAN_SLUG=""
PLAN_INTENT=""
for dir in .claude/plans/*/; do
  [ -f "${dir}plan.md" ] || continue
  PLAN_SLUG="$(basename "$dir")"
  PLAN_INTENT="$(head -5 "${dir}plan.md" | grep '^#' | head -1)"
  PLAN_INTENT="${PLAN_INTENT#"${PLAN_INTENT%%[!#]*}"}"
  PLAN_INTENT="${PLAN_INTENT#"${PLAN_INTENT%%[! ]*}"}"
  break
done

# Build context message based on active phase
CONTEXT=""

if [ "$ACTIVE_PLAN" = true ] && [ "$FULL_MODE" = false ]; then
  CONTEXT="Workflow rules restored after compaction — active /phx:plan session:"
  CONTEXT+="\n"
  if [ -n "$PLAN_SLUG" ]; then
    CONTEXT+="\n- Active plan: ${PLAN_SLUG} — ${PLAN_INTENT}"
    CONTEXT+="\n- Plan file: .claude/plans/${PLAN_SLUG}/plan.md"
    CONTEXT+="\n"
  fi
  CONTEXT+="\nAfter writing plan.md, stop — the user reviews the plan before implementation or /phx:work starts."
  CONTEXT+="\nPresent the plan summary and use AskUserQuestion with options:"
  CONTEXT+="\n  - Start in fresh session (recommended)"
  CONTEXT+="\n  - Get a briefing (/phx:brief)"
  CONTEXT+="\n  - Start here"
  CONTEXT+="\n  - Review or adjust the plan"
  CONTEXT+="\nWait for the user's response (/phx:plan Iron Law #1)."
fi

if [ "$ACTIVE_WORK" = true ] && [ "$FULL_MODE" = false ]; then
  CONTEXT="Workflow rules restored after compaction — active /phx:work session:"
  CONTEXT+="\n"
  if [ -n "$PLAN_SLUG" ]; then
    CONTEXT+="\n- Active plan: ${PLAN_SLUG} — ${PLAN_INTENT}"
    CONTEXT+="\n- Plan file: .claude/plans/${PLAN_SLUG}/plan.md"
    CONTEXT+="\n"
  fi
  CONTEXT+="\n- Verify after each task (mix compile --warnings-as-errors)"
  CONTEXT+="\n- Max 3 retries per task, then mark BLOCKER"
  CONTEXT+="\n- Continue between phases automatically; stop when all phases are done"
  CONTEXT+="\n- Don't auto-start /phx:review — ask the user what to do next"
  CONTEXT+="\n- Re-read plan.md for current state (checkboxes are the source of truth)"
fi

if [ "$FULL_MODE" = true ]; then
  CONTEXT="Workflow rules restored after compaction — /phx:full autonomous mode:"
  CONTEXT+="\n"
  if [ -n "$PLAN_SLUG" ]; then
    CONTEXT+="\n- Active plan: ${PLAN_SLUG} — ${PLAN_INTENT}"
    CONTEXT+="\n- Plan file: .claude/plans/${PLAN_SLUG}/plan.md"
    CONTEXT+="\n"
  fi
  CONTEXT+="\n- Continue autonomous plan → work → review cycle"
  CONTEXT+="\n- Re-read progress.md for current state and cycle count"
  CONTEXT+="\n- Re-read plan.md for task checkboxes"
  CONTEXT+="\n- Max cycles, retries, and blocker limits still apply"
fi

# Append scratchpad Dead Ends to context (most valuable section for session continuity)
if [ -n "$PLAN_SLUG" ]; then
  SCRATCHPAD=".claude/plans/${PLAN_SLUG}/scratchpad.md"
  if [ -f "$SCRATCHPAD" ]; then
    DEAD_ENDS=$(dead_ends_section "$SCRATCHPAD" | head -20)
    if [ -n "$DEAD_ENDS" ] && ! echo "$DEAD_ENDS" | grep -q "(none yet)"; then
      CONTEXT+="\n\nScratchpad dead ends (approaches that already failed — don't retry them):"
      CONTEXT+="\n${DEAD_ENDS}"
    fi
  fi
fi

if [ -n "$CONTEXT" ]; then
  printf '%b\n' "$CONTEXT"
fi
