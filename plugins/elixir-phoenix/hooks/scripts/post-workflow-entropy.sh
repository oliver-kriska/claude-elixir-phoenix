#!/usr/bin/env bash
# Stop hook: After workflow completion, suggest entropy check.
# Detects if a workflow was running by checking for progress files
# with recent timestamps.

[ -f "mix.exs" ] || exit 0

# Check for recently modified progress files (within last hour)
RECENT_PROGRESS=$(find .claude/plans/ -name "progress.md" -newer /tmp/.claude_session_start 2>/dev/null | head -1)

if [ -n "$RECENT_PROGRESS" ]; then
  SLUG=$(basename "$(dirname "$RECENT_PROGRESS")")

  # Check if workflow completed (has COMPLETED state)
  if grep -q "COMPLETED\|COMPOUNDING" "$RECENT_PROGRESS" 2>/dev/null; then
    # Check if baseline exists
    if [ -f ".claude/metrics/baseline.json" ]; then
      echo ""
      echo "Workflow completed for '${SLUG}'. Consider running /phx:entropy to check for quality drift."
    fi
  fi
fi
