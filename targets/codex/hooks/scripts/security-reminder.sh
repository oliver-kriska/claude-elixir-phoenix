#!/usr/bin/env bash
# PostToolUse hook: Output security Iron Laws when auth-related Elixir files are edited.
#
# Gates:
#   1. mix.exs must exist in project root — skip in non-Elixir projects (#55).
#   2. File must be an Elixir source extension — security Iron Laws target code patterns.
#   3. Basename token match with word-boundary separators — no parent-dir false positives.

# Skip in non-Elixir projects (cross-project bleed guard — issue #55)
proj="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -f "$proj/mix.exs" ] || exit 0

FILE_PATH=$(cat | jq -r '.tool_input.file_path // empty')
if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

BASENAME=$(basename "$FILE_PATH")

# Restrict to Elixir source extensions
case "$BASENAME" in
  *.ex|*.exs|*.heex|*.eex|*.leex) ;;
  *) exit 0 ;;
esac

# Anchored token match on basename (separators: start, end, _, ., -)
# Prevents tokenizer.cpp matching `token`, /admin_panel/x.ex matching via dir, etc.
if echo "$BASENAME" | grep -qiE '(^|[_.-])(auth|session|password|token|permission|admin|payment|login|credential|secret)([_.-]|$)'; then
  # PostToolUse: exit 2 + stderr feeds message to Claude (stdout is verbose-mode only)
  cat >&2 <<MSG
SECURITY FILE DETECTED: $BASENAME
Iron Laws — verify these apply:
  - AUTHORIZE in EVERY LiveView handle_event (don't trust mount auth)
  - NO String.to_atom with user input (atom exhaustion DoS)
  - NEVER use raw/1 with untrusted content (XSS)
  - Pin values with ^ in Ecto queries (no user input interpolation)
Consider: /phx:review security for full security audit
MSG
  exit 2
fi
