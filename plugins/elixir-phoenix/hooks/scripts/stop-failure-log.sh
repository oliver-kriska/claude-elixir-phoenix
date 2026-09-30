#!/usr/bin/env bash
# StopFailure hook: Log failed turns to scratchpad for resume detection.
# When a turn ends due to API error, record what was happening so the
# next session can pick up where things left off.
#
# NOTE (CC hooks ref): StopFailure cannot block, and CC ignores its exit code
# and output entirely. The scratchpad WRITE below is the whole job — there is no
# exit-2/stderr signal to emit (an earlier version did; it was a no-op). Next
# session’s check-resume.sh reads the scratchpad, which is how the signal
# actually propagates.

# ls -t is the portable mtime sort; plan slugs are kebab-case.
# shellcheck disable=SC2012
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

exit 0
