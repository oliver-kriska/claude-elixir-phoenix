#!/usr/bin/env bash
# SessionStart hook: Quick quality fingerprint (<15s, non-blocking).
# Checks for obvious entropy signals without running full analysis.

[ -f "mix.exs" ] || exit 0

# Quick compile check (5s timeout)
WARNINGS=$(timeout 5 mix compile 2>&1 | grep -c "warning:" 2>/dev/null || echo "unknown")

# Check for baseline
BASELINE_FILE=".claude/metrics/baseline.json"
if [ -f "$BASELINE_FILE" ]; then
  BASELINE_WARNINGS=$(jq -r '.scores.compile_warnings // 0' "$BASELINE_FILE" 2>/dev/null || echo "0")

  if [ "$WARNINGS" != "unknown" ] && [ "$WARNINGS" -gt "$BASELINE_WARNINGS" ] 2>/dev/null; then
    DELTA=$((WARNINGS - BASELINE_WARNINGS))
    echo "ENTROPY: +${DELTA} compile warnings since baseline. Run /phx:entropy for details."
  fi
else
  if [ "$WARNINGS" != "unknown" ] && [ "$WARNINGS" -gt 0 ] 2>/dev/null; then
    echo "NOTE: ${WARNINGS} compile warnings detected. Run /phx:entropy --save-baseline to track."
  fi
fi
