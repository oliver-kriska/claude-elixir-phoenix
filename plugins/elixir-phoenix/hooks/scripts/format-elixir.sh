#!/usr/bin/env bash
# PostToolUse hook: Check Elixir file formatting after Edit/Write
# Only warns — does NOT modify files (prevents "file modified since read" race condition)

# Skip in non-Elixir projects (defense in depth — issue #55)
proj="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -f "$proj/mix.exs" ] || exit 0

FILE_PATH=$(cat | jq -r '.tool_input.file_path // empty')
if [[ "$FILE_PATH" == *.ex ]] || [[ "$FILE_PATH" == *.exs ]]; then
  if ! mix format --check-formatted "$FILE_PATH" 2>/dev/null; then
    # PostToolUse: exit 2 + stderr feeds message to Claude (stdout is verbose-mode only)
    echo "NEEDS FORMAT: $FILE_PATH — run 'mix format' before committing" >&2
    exit 2
  fi
fi
