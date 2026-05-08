#!/usr/bin/env bash
# PreToolUse hook: Block dangerous operations before execution.
# Extends AutoHarness action-verifier pattern (iron-law-verifier.sh)
# to catch destructive operations BEFORE they run.

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')

# Only check Bash commands
[[ "$TOOL" == "Bash" ]] || exit 0

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
[[ -n "$COMMAND" ]] || exit 0

# Block destructive database operations
if echo "$COMMAND" | grep -qE 'mix ecto\.(reset|drop)'; then
  cat >&2 <<MSG
BLOCKED: Destructive database operation detected.
mix ecto.reset/drop will destroy all data. If intentional, run manually
outside Claude Code. Safer alternatives:
- mix ecto.rollback --step 1 (undo last migration)
- mix ecto.migrate (apply pending migrations)
MSG
  exit 2
fi

# Block force push
if echo "$COMMAND" | grep -qE 'git push.*(--force|-f)\b'; then
  cat >&2 <<MSG
BLOCKED: Force push detected — this rewrites remote history.
If intentional, run manually outside Claude Code.
Safer alternative: git push --force-with-lease
MSG
  exit 2
fi

# Warn about production mix in dev
if echo "$COMMAND" | grep -qE 'MIX_ENV=prod mix'; then
  cat >&2 <<MSG
WARNING: MIX_ENV=prod detected. This runs in production mode.
If building a release, this is expected. Otherwise, reconsider.
MSG
  exit 2
fi
