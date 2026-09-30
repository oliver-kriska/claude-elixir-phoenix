#!/usr/bin/env bash
# SessionStart hook: Detect scratchpad files and initialize structured template for new plans
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

shopt -s nullglob
PADS=(.claude/plans/*/scratchpad.md)
shopt -u nullglob
COUNT=${#PADS[@]}
if [[ "$COUNT" -gt 0 ]]; then
  # ls -t is the portable mtime sort; plan slugs are kebab-case.
  # shellcheck disable=SC2012
  LATEST=$(ls -t "${PADS[@]}" | head -1)
  # Count bullets in the Dead Ends section only — the template's Handoff
  # section always has bullets. grep -c prints 0 on no match (exit 1); no
  # `|| echo 0`, which would append a second line and break the -gt below.
  DEAD_ENDS=$(dead_ends_section "$LATEST" 2>/dev/null | grep -c "^- ")
  DEAD_ENDS=${DEAD_ENDS:-0}
  if [[ "$DEAD_ENDS" -gt 0 ]]; then
    echo "Scratchpad: $COUNT note(s) found — latest: $LATEST ($DEAD_ENDS dead-end entries — read them before retrying an approach)"
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
