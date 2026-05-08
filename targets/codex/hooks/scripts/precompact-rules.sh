#!/usr/bin/env bash
# PreCompact hook: Re-inject critical SKILL-SPECIFIC rules before compaction.
# Iron Laws from CLAUDE.md survive compaction (system prompt), so we only
# re-inject rules from loaded skills that live in conversation context.
#
# PreCompact hookSpecificOutput only supports top-level fields.
# Use "systemMessage" to inject context that survives compaction.

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
  PLAN_INTENT="$(head -5 "${dir}plan.md" | grep '^#' | head -1 | sed 's/^#* *//')"
  break
done

# Build context message based on active phase
CONTEXT=""

if [ "$ACTIVE_PLAN" = true ] && [ "$FULL_MODE" = false ]; then
  CONTEXT="PRESERVE ACROSS COMPACTION — active /phx:plan session:"
  CONTEXT+="\n"
  if [ -n "$PLAN_SLUG" ]; then
    CONTEXT+="\n- Active plan: ${PLAN_SLUG} — ${PLAN_INTENT}"
    CONTEXT+="\n- Plan file: .claude/plans/${PLAN_SLUG}/plan.md"
    CONTEXT+="\n"
  fi
  CONTEXT+="\nCRITICAL: After writing plan.md, you MUST STOP."
  CONTEXT+="\nDo NOT proceed to implementation or /phx:work."
  CONTEXT+="\nPresent the plan summary and use AskUserQuestion with options:"
  CONTEXT+="\n  - Start in fresh session (recommended)"
  CONTEXT+="\n  - Get a briefing (/phx:brief)"
  CONTEXT+="\n  - Start here"
  CONTEXT+="\n  - Review the plan"
  CONTEXT+="\n  - Adjust the plan"
  CONTEXT+="\nWait for user response. This is Iron Law #1 of /phx:plan."
fi

if [ "$ACTIVE_WORK" = true ] && [ "$FULL_MODE" = false ]; then
  CONTEXT="PRESERVE ACROSS COMPACTION — active /phx:work session:"
  CONTEXT+="\n"
  if [ -n "$PLAN_SLUG" ]; then
    CONTEXT+="\n- Active plan: ${PLAN_SLUG} — ${PLAN_INTENT}"
    CONTEXT+="\n- Plan file: .claude/plans/${PLAN_SLUG}/plan.md"
    CONTEXT+="\n"
  fi
  CONTEXT+="\n- Verify after EVERY task (mix compile --warnings-as-errors)"
  CONTEXT+="\n- Max 3 retries per task, then mark BLOCKER"
  CONTEXT+="\n- Auto-continue between phases, but STOP when ALL phases done"
  CONTEXT+="\n- NEVER auto-start /phx:review — ask user what to do next"
  CONTEXT+="\n- Re-read plan.md for current state (checkboxes are the source of truth)"
fi

if [ "$FULL_MODE" = true ]; then
  CONTEXT="PRESERVE ACROSS COMPACTION — /phx:full autonomous mode:"
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
    DEAD_ENDS=$(sed -n '/^## Dead Ends/,/^## /p' "$SCRATCHPAD" | head -20)
    if [ -n "$DEAD_ENDS" ] && ! echo "$DEAD_ENDS" | grep -q "(none yet)"; then
      CONTEXT+="\n\nSCRATCHPAD Dead Ends (DO NOT RETRY these approaches):"
      CONTEXT+="\n${DEAD_ENDS}"
    fi
  fi
fi

# Output as JSON with systemMessage (hookSpecificOutput doesn't support PreCompact hookEventName)
if [ -n "$CONTEXT" ]; then
  printf '%b' "$CONTEXT" | jq -Rs '{systemMessage: .}'
fi
