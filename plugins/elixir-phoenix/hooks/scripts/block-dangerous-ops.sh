#!/usr/bin/env bash
# PreToolUse hook: block dangerous Bash operations before execution.
# Emits permissionDecision: "deny" via JSON output and includes
# `additionalContext` so the safer alternative survives into Claude's next
# turn (CC 2.1.110+ preserves additionalContext on blocked tool calls).
#
# Elixir-specific branches self-gate on mix.exs presence (see PR #55,
# "gate hooks on mix.exs to fix cross-project bleed"). The git force-push
# block is intentionally global and stays ungated.

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$TOOL" == "Bash" ]] || exit 0

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
[[ -n "$COMMAND" ]] || exit 0

proj="${CLAUDE_PROJECT_DIR:-$PWD}"
is_elixir=0
[ -f "$proj/mix.exs" ] && is_elixir=1

emit_block() {
  local reason="$1"
  local ctx="$2"
  jq -nc \
    --arg reason "$reason" \
    --arg ctx "$ctx" \
    '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: $reason,
        additionalContext: $ctx
      }
    }'
  exit 0
}

# Elixir-only: destructive Ecto operations.
# Anchored on start-of-line or shell command separators (;, &, |, &&, ||) so a
# quoted mention inside `echo "do not run mix ecto.reset"` doesn't trigger.
# Trailing class requires `reset`/`drop` to be followed by whitespace, separator,
# or end-of-command — preserving sibling tasks like `mix ecto.gen.migration`.
if [[ "$is_elixir" == 1 ]] && echo "$COMMAND" | grep -qE '(^|[;&|]+[[:space:]]*)mix ecto\.(reset|drop)([[:space:];&|]|$)'; then
  emit_block \
"BLOCKED: Destructive database operation detected.
mix ecto.reset/drop will destroy all data. If intentional, run manually
outside Claude Code. Safer alternatives:
- mix ecto.rollback --step 1 (undo last migration)
- mix ecto.migrate (apply pending migrations)" \
"The user's previous Bash call ('mix ecto.reset' / 'mix ecto.drop') was blocked by the elixir-phoenix plugin to prevent data loss. Prefer 'mix ecto.rollback --step 1' to undo the last migration, 'mix ecto.migrate' to apply pending ones, or author a corrective migration with 'mix ecto.gen.migration <name>'. Do not retry the reset/drop unless the user explicitly asks again."
fi

# Global: force-push (intentionally not gated on mix.exs).
#
# Issue #61: the previous pattern `git push.*(--force|-f)\b` matched
# `--force-with-lease` — in ERE, `\b` is a boundary between word (`e`) and
# non-word (`-`), so `--force-` triggered the boundary and the whole flag
# matched. It also scanned past `&&`/`;`/`|` and tripped on quoted strings
# elsewhere on the line. This anchored pattern fixes both:
#
#   - `(^|[;&|]+[[:space:]]*)` — start-of-line or after a shell command
#     separator. Plain whitespace is NOT an anchor, so `echo "git push --force"`
#     no longer matches (`git push` is preceded by a space inside the quote,
#     not a separator).
#   - `[^;|&]*[[:space:]]` — scan stays within the current command, so a later
#     `&& gh ... --force-with-lease` on the same line is out of scope.
#   - `(--force|-f)([[:space:];&|]|$)` — the flag must end at a word terminator
#     (whitespace, separator, or end-of-command). `--force-with-lease` ends in
#     `-`, which is not a terminator, so it is allowed; `--force` and `-f` as
#     real flags are still blocked.
if echo "$COMMAND" | grep -qE '(^|[;&|]+[[:space:]]*)git push[^;|&]*[[:space:]](--force|-f)([[:space:];&|]|$)'; then
  emit_block \
"BLOCKED: Force push detected — this rewrites remote history.
If intentional, run manually outside Claude Code.
Safer alternative: git push --force-with-lease" \
"The user's previous 'git push --force' / 'git push -f' was blocked by the elixir-phoenix plugin. Use 'git push --force-with-lease' which refuses to clobber unseen commits. Only the user should run an unguarded force-push (via '!' prefix in their terminal). Do not retry."
fi

# Elixir-only: production env warning. Anchored so a quoted mention inside
# `echo "never use MIX_ENV=prod mix in dev"` doesn't trigger.
if [[ "$is_elixir" == 1 ]] && echo "$COMMAND" | grep -qE '(^|[;&|]+[[:space:]]*)MIX_ENV=prod mix'; then
  emit_block \
"WARNING: MIX_ENV=prod detected. This runs in production mode.
If building a release, this is expected. Otherwise, reconsider." \
"The user's previous command used 'MIX_ENV=prod' and was blocked by the elixir-phoenix plugin. This is only appropriate when building releases ('mix release', 'mix phx.gen.release'). For local development omit MIX_ENV or use 'MIX_ENV=dev'/'MIX_ENV=test'. Confirm release intent with the user before retrying."
fi

exit 0
