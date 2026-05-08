#!/usr/bin/env bash
# StopFailure hook: Log failed turns to scratchpad for resume detection.
# When a turn ends due to API error, record what was happening so the
# next session can pick up where things left off.

LATEST_PLAN_DIR=$(ls -td .claude/plans/*/ 2>/dev/null | head -1)
SCRATCHPAD="${LATEST_PLAN_DIR}scratchpad.md"

if [ -n "$LATEST_PLAN_DIR" ] && [ -d "$LATEST_PLAN_DIR" ]; then
  {
    echo ""
    echo "## API Failure — $(date '+%Y-%m-%d %H:%M')"
    echo ""
    echo "Turn ended due to API error. Check progress.md for last completed task."
    echo "Resume with: /phx:work --continue"
  } >> "$SCRATCHPAD"
fi

# Also warn on stderr so next session's resume detection catches it
echo "StopFailure: Turn ended due to API error. Progress saved to scratchpad." >&2
exit 2
