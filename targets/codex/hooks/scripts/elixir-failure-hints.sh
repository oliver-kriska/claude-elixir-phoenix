#!/usr/bin/env bash
# PostToolUseFailure hook: Provide Elixir-specific debugging hints when Bash commands fail.
# Only triggers for mix compile/test failures. Uses additionalContext to guide Claude.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
ERROR=$(echo "$INPUT" | jq -r '.error // empty')

# Only handle mix-related failures
echo "$COMMAND" | grep -qE '^mix\b|MIX_ENV=\S+ mix' || exit 0

HINTS=""

if echo "$COMMAND" | grep -qE 'mix compile'; then
  HINTS="Compile failure hints:
- Read the FIRST error — later errors are often cascading
- Check for missing module aliases or imports
- If struct error: ensure the struct's module compiles first
- If protocol not implemented: check if you need @derive
- Scope fix to files YOU changed — pre-existing warnings are not your problem"
elif echo "$COMMAND" | grep -qE 'mix test'; then
  HINTS="Test failure hints:
- Read the assertion error carefully — expected vs got
- Check test setup (setup/setup_all blocks) for stale data
- For async test failures: check for shared database state
- For LiveView test failures: ensure render returns before assertions
- Run the single failing test first: mix test path/to/test.exs:LINE"
elif echo "$COMMAND" | grep -qE 'mix credo'; then
  HINTS="Credo failure hints:
- Fix highest priority issues first (consistency > readability > refactoring)
- For module attribute warnings: move to module top
- For pipe chain warnings: ensure first arg flows through pipe
- Run with --strict for all issues or without for priority only"
elif echo "$COMMAND" | grep -qE 'mix ecto'; then
  HINTS="Ecto/migration failure hints:
- For migration failures: check if table/column already exists
- For rollback issues: ensure down/0 reverses up/0 exactly
- For constraint errors: check existing data violates new constraint
- Run mix ecto.reset in dev to start fresh (destructive)"
fi

if [ -n "$HINTS" ]; then
  echo "$HINTS" | jq -Rs '{hookSpecificOutput: {hookEventName: "PostToolUseFailure", additionalContext: .}}'
fi
