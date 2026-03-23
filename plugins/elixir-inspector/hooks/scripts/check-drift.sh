#!/usr/bin/env bash
# PostToolUse hook: Lightweight architecture drift detection after Edit/Write.
# Single-file checks only — must complete in <2s.

FILE_PATH=$(cat | jq -r '.tool_input.file_path // empty')
[[ -z "$FILE_PATH" ]] && exit 0
[[ "$FILE_PATH" == *.ex || "$FILE_PATH" == *.heex ]] || exit 0
[[ -f "$FILE_PATH" ]] || exit 0
[[ -f .claude/inspector/report.md ]] || exit 0

WARNINGS=""

# Check 1: Boundary violation — direct Repo calls from _web/ layer
if [[ "$FILE_PATH" == *_web/* ]]; then
  MATCH=$(grep -n 'Repo\.' "$FILE_PATH" 2>/dev/null | grep -v '^\s*#' | head -1)
  if [[ -n "$MATCH" ]]; then
    WARNINGS="${WARNINGS}\n- BOUNDARY DRIFT (line $(echo "$MATCH" | cut -d: -f1)): Direct Repo call in web layer. Move to context module"
  fi
fi

# Check 2: Naming convention — defmodule should match file path
if [[ "$FILE_PATH" == *.ex && "$FILE_PATH" == */lib/* ]]; then
  REL_PATH="${FILE_PATH##*/lib/}"
  REL_PATH="${REL_PATH%.ex}"
  EXPECTED=""
  IFS='/' read -ra PARTS <<< "$REL_PATH"
  for part in "${PARTS[@]}"; do
    EXPECTED="${EXPECTED}.$(echo "$part" | sed -E 's/(^|_)([a-z])/\U\2/g')"
  done
  EXPECTED="${EXPECTED:1}"
  ACTUAL=$(grep -m1 'defmodule ' "$FILE_PATH" 2>/dev/null | sed -E 's/.*defmodule +([A-Za-z0-9_.]+).*/\1/')
  if [[ -n "$ACTUAL" && -n "$EXPECTED" && "$ACTUAL" != "$EXPECTED" ]]; then
    WARNINGS="${WARNINGS}\n- NAMING DRIFT: defmodule $ACTUAL does not match path (expected $EXPECTED)"
  fi
fi

# Check 3: Unguarded handle_event in LiveView
if [[ "$FILE_PATH" == *_live.ex ]]; then
  while IFS= read -r event_line; do
    [[ -z "$event_line" ]] && continue
    LN=$(echo "$event_line" | cut -d: -f1)
    AUTH=$(sed -n "${LN},$((LN + 5))p" "$FILE_PATH" | grep -iE '(authorize|auth|policy|permitted|allowed|can\?)')
    [[ -z "$AUTH" ]] && WARNINGS="${WARNINGS}\n- UNGUARDED EVENT (line $LN): handle_event without visible auth check"
  done <<< "$(grep -n 'def handle_event(' "$FILE_PATH" 2>/dev/null)"
fi

if [[ -n "$WARNINGS" ]]; then
  echo -e "ARCHITECTURE DRIFT in $(basename "$FILE_PATH"):\n$(echo -e "$WARNINGS")\n\nReview against inspector scan (.claude/inspector/report.md)." >&2
  exit 2
fi
