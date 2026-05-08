#!/usr/bin/env bash
# PostToolUse hook: Programmatic Iron Law verification after Edit/Write.
# Inspired by AutoHarness (Lou et al., 2026) "harness-as-action-verifier" pattern:
# Code validates LLM output, feeds specific violation back for retry.
# Unlike security-reminder.sh (filename-based), this scans CODE CONTENT.

FILE_PATH=$(cat | jq -r '.tool_input.file_path // empty')
if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# Only check Elixir files
[[ "$FILE_PATH" == *.ex ]] || [[ "$FILE_PATH" == *.exs ]] || exit 0
[[ -f "$FILE_PATH" ]] || exit 0

VIOLATIONS=""

# Helper: grep lines that are NOT comments (skip lines starting with #)
# Uses grep -En (ERE) for macOS compatibility — no PCRE (-P) needed
check_violation() {
  local pattern="$1"
  # grep -n output is "NUM:content" — strip line number, check if content is a comment
  grep -En "$pattern" "$FILE_PATH" 2>/dev/null | while IFS= read -r line; do
    content="${line#*:}"
    # Skip if the trimmed content starts with #
    trimmed="${content#"${content%%[! ]*}"}"
    if [[ "$trimmed" != \#* ]]; then
      echo "$line"
      break
    fi
  done
}

# Iron Law 10: NO String.to_atom with user input
if [[ "$FILE_PATH" != *_test.exs ]]; then
  MATCH=$(check_violation 'String\.to_atom\(')
  if [[ -n "$MATCH" ]]; then
    LINE=$(echo "$MATCH" | cut -d: -f1)
    VIOLATIONS="${VIOLATIONS}\n- Iron Law #10 (line $LINE): String.to_atom/1 detected — atom exhaustion DoS. Use String.to_existing_atom/1 or a whitelist map"
  fi
fi

# Iron Law 4: NO :float for money
MATCH=$(check_violation 'field :(price|amount|cost|total|balance|fee|rate|charge|payment|salary|wage|budget|revenue|discount)[a-z_]*, :float')
if [[ -n "$MATCH" ]]; then
  LINE=$(echo "$MATCH" | cut -d: -f1)
  VIOLATIONS="${VIOLATIONS}\n- Iron Law #4 (line $LINE): :float used for money field — use :decimal or :integer (cents)"
fi

# Also check migrations: add :price, :float
MATCH=$(check_violation 'add :(price|amount|cost|total|balance|fee|rate|charge|payment|salary|wage|budget|revenue|discount)[a-z_]*, :float')
if [[ -n "$MATCH" ]]; then
  LINE=$(echo "$MATCH" | cut -d: -f1)
  VIOLATIONS="${VIOLATIONS}\n- Iron Law #4 (line $LINE): :float used for money field in migration — use :decimal or :integer (cents)"
fi

# Iron Law 12: NO raw/1 with variables (potential XSS)
# Match raw(variable) but not raw("literal") or raw(~s/~S)
MATCH=$(check_violation '[^a-z_]raw\([[:space:]]*[a-z_@]')
if [[ -n "$MATCH" ]]; then
  LINE=$(echo "$MATCH" | cut -d: -f1)
  VIOLATIONS="${VIOLATIONS}\n- Iron Law #12 (line $LINE): raw/1 with variable — XSS risk. Sanitize input or use Phoenix.HTML.safe_to_string/1"
fi

# Iron Law 15: NO implicit cross joins — from(a in A, b in B) without on:
MATCH=$(check_violation 'from\([[:space:]]*[a-z_]+[[:space:]]+in[[:space:]]+[A-Z][a-zA-Z]*[[:space:]]*,[[:space:]]*[a-z_]+[[:space:]]+in[[:space:]]+[A-Z]')
if [[ -n "$MATCH" ]]; then
  LINE=$(echo "$MATCH" | cut -d: -f1)
  VIOLATIONS="${VIOLATIONS}\n- Iron Law #15 (line $LINE): Implicit cross join detected — from(a in A, b in B) creates Cartesian product. Use explicit join()"
fi

# Iron Law 13/14: Bare GenServer.start_link or Agent.start_link outside supervisor
# Skip if file looks like it IS a supervisor (has use Supervisor)
if ! grep -q 'use Supervisor' "$FILE_PATH" 2>/dev/null; then
  MATCH=$(check_violation '(GenServer|Agent)\.start_link\(')
  if [[ -n "$MATCH" ]]; then
    # Check if it's inside a child_spec or start_link def (OK) vs bare call
    if ! grep -qE 'def (start_link|child_spec|init)\b' "$FILE_PATH" 2>/dev/null; then
      LINE=$(echo "$MATCH" | cut -d: -f1)
      VIOLATIONS="${VIOLATIONS}\n- Iron Law #14 (line $LINE): Bare GenServer/Agent.start_link outside module definition — supervise all long-lived processes"
    fi
  fi
fi

# Iron Law 21: assign_new for values that should refresh every mount
MATCH=$(check_violation 'assign_new\([[:space:]]*[a-z_]+[[:space:]]*,[[:space:]]*:(current_user|locale|timezone|current_org)')
if [[ -n "$MATCH" ]]; then
  LINE=$(echo "$MATCH" | cut -d: -f1)
  VIOLATIONS="${VIOLATIONS}\n- Iron Law #21 (line $LINE): assign_new for per-mount value — use assign/3 instead. assign_new skips if key exists"
fi

if [ -n "$VIOLATIONS" ]; then
  cat >&2 <<MSG
IRON LAW VIOLATION(S) in $(basename "$FILE_PATH"):
$(echo -e "$VIOLATIONS")

Fix these before proceeding. These are non-negotiable constraints.
MSG
  exit 2
fi
