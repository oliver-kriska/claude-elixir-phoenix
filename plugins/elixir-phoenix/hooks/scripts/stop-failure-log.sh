#!/usr/bin/env bash
# StopFailure hook: Log failed turns to scratchpad for resume detection.
# Uses structured scratchpad format (Dead Ends, Decisions, Handoff).

LATEST_PLAN_DIR=$(ls -td .claude/plans/*/ 2>/dev/null | head -1)
SCRATCHPAD="${LATEST_PLAN_DIR}scratchpad.md"

if [ -n "$LATEST_PLAN_DIR" ] && [ -d "$LATEST_PLAN_DIR" ]; then
  SLUG=$(basename "$LATEST_PLAN_DIR")
  BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")

  # Initialize scratchpad with template if empty or missing
  if [ ! -s "$SCRATCHPAD" ]; then
    cat > "$SCRATCHPAD" << TEMPLATE
# Scratchpad — ${SLUG}

## Dead Ends (DO NOT RETRY)

## Decisions

## Hypotheses

## Open Questions

## Handoff

TEMPLATE
  fi

  # Append to Handoff section
  {
    echo ""
    echo "### API Failure — $(date '+%Y-%m-%d %H:%M')"
    echo ""
    echo "- Branch: ${BRANCH}"
    echo "- Plan: .claude/plans/${SLUG}/plan.md"
    echo "- Last task: Check progress.md for last completed task"
    echo "- Next: Resume with \`/phx:work --continue\`"
    echo "- Reason: Turn ended due to API error"
  } >> "$SCRATCHPAD"
fi

echo "StopFailure: Turn ended due to API error. Progress saved to scratchpad." >&2
exit 2
