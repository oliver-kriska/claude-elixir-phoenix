#!/usr/bin/env bash
# PostToolUse hook: Warn about debug statements left in Elixir files.
# Extends AutoHarness action-verifier pattern — catches IO.inspect,
# dbg(), IO.puts in production code (not tests).

FILE_PATH=$(cat | jq -r '.tool_input.file_path // empty')
[[ -z "$FILE_PATH" ]] && exit 0

# Only check Elixir source files (not tests, not scripts)
[[ "$FILE_PATH" == *.ex ]] || exit 0
[[ "$FILE_PATH" != *_test.exs ]] || exit 0
[[ "$FILE_PATH" != */test/* ]] || exit 0
[[ -f "$FILE_PATH" ]] || exit 0

DEBUGS=""

# IO.inspect (most common debug leftover)
MATCH=$(grep -n 'IO\.inspect\b' "$FILE_PATH" 2>/dev/null | head -3)
if [[ -n "$MATCH" ]]; then
  DEBUGS="${DEBUGS}\n  IO.inspect:\n${MATCH}"
fi

# dbg() calls
MATCH=$(grep -n '\bdbg(' "$FILE_PATH" 2>/dev/null | head -3)
if [[ -n "$MATCH" ]]; then
  DEBUGS="${DEBUGS}\n  dbg():\n${MATCH}"
fi

# IO.puts outside @moduledoc/@doc
MATCH=$(grep -n 'IO\.puts\b' "$FILE_PATH" 2>/dev/null | grep -v '@moduledoc\|@doc' | head -3)
if [[ -n "$MATCH" ]]; then
  DEBUGS="${DEBUGS}\n  IO.puts:\n${MATCH}"
fi

if [[ -n "$DEBUGS" ]]; then
  cat >&2 <<MSG
DEBUG STATEMENTS in $(basename "$FILE_PATH"):
$(echo -e "$DEBUGS")

Remove before committing. Use Logger for intentional logging.
MSG
  exit 2
fi
