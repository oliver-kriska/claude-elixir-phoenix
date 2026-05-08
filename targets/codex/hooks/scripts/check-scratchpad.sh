#!/usr/bin/env bash
# SessionStart hook: Detect scratchpad files and initialize structured template for new plans
COUNT=$(ls .claude/plans/*/scratchpad.md 2>/dev/null | wc -l | tr -d ' ')
if [[ "$COUNT" -gt 0 ]]; then
  LATEST=$(ls -t .claude/plans/*/scratchpad.md 2>/dev/null | head -1)
  # Check if scratchpad has Dead Ends (most valuable section for resume)
  DEAD_ENDS=$(grep -c "^- " "$LATEST" 2>/dev/null || echo 0)
  if [[ "$DEAD_ENDS" -gt 0 ]]; then
    echo "Scratchpad: $COUNT note(s) found — latest: $LATEST ($DEAD_ENDS dead-end entries — READ BEFORE RETRYING)"
  else
    echo "Scratchpad: $COUNT note(s) found — latest: $LATEST"
  fi
fi

# Initialize structured scratchpad template for new plans that don't have one
for dir in .claude/plans/*/; do
  [ -f "${dir}plan.md" ] || continue
  SCRATCHPAD="${dir}scratchpad.md"
  if [ ! -f "$SCRATCHPAD" ]; then
    SLUG=$(basename "$dir")
    BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
    cat > "$SCRATCHPAD" << TEMPLATE
# Scratchpad: ${SLUG}

## Dead Ends (DO NOT RETRY)

(none yet)

## Decisions

(none yet)

## Open Questions

(none yet)

## Handoff

- Branch: ${BRANCH}
- Plan: .claude/plans/${SLUG}/plan.md
- Next: (to be filled on session end)
TEMPLATE
  fi
done
