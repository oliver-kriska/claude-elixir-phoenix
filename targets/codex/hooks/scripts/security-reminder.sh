#!/usr/bin/env bash
# PostToolUse hook: Output security Iron Laws when auth-related files are edited
FILE_PATH=$(cat | jq -r '.tool_input.file_path // empty')
if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# Check if file path matches security-sensitive patterns
BASENAME=$(basename "$FILE_PATH")
if echo "$FILE_PATH" | grep -qiE '(auth|session|password|token|permission|admin|payment|login|credential|secret)'; then
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
