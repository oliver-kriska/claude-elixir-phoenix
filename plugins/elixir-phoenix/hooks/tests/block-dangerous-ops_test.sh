#!/usr/bin/env bash
# Regression tests for hooks/scripts/block-dangerous-ops.sh
#
# Run: bash plugins/elixir-phoenix/hooks/tests/block-dangerous-ops_test.sh
#
# Issue #61: the previous force-push regex `git push.*(--force|-f)\b` matched
# `--force-with-lease` (because `\b` is a word boundary and the hyphen after
# `--force` is non-word) and also scanned past command separators, so a real
# force-push, the lease variant, and unrelated commands sharing a line all
# triggered the same deny.
#
# Tests check three categories per pattern:
#   1. Real dangerous command  → MUST block
#   2. Safer alternative       → MUST allow
#   3. Lookalike string nearby → MUST allow (no scan-past-separator)

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="$SCRIPT_DIR/../scripts/block-dangerous-ops.sh"

if [[ ! -x "$HOOK" ]]; then
  echo "FATAL: $HOOK not executable" >&2
  exit 2
fi

PASS=0
FAIL=0
FAILED_CASES=()

# run_hook EXPECTED COMMAND TOOL_NAME
#   EXPECTED  = "block" | "allow"
#   COMMAND   = shell command string passed as tool_input.command
#   TOOL_NAME = "Bash" by default
run_hook() {
  local expected="$1"
  local cmd="$2"
  local tool="${3:-Bash}"

  local payload
  payload=$(jq -nc --arg t "$tool" --arg c "$cmd" \
    '{tool_name: $t, tool_input: {command: $c}}')

  local out
  out=$(echo "$payload" | bash "$HOOK" 2>/dev/null)

  local actual="allow"
  if [[ -n "$out" ]] && echo "$out" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null 2>&1; then
    actual="block"
  fi

  if [[ "$actual" == "$expected" ]]; then
    PASS=$((PASS + 1))
    printf '  \033[32m✓\033[0m %s: %s\n' "$expected" "$cmd"
  else
    FAIL=$((FAIL + 1))
    FAILED_CASES+=("expected=$expected actual=$actual cmd=$cmd")
    printf '  \033[31m✗\033[0m want=%s got=%s :: %s\n' "$expected" "$actual" "$cmd"
  fi
}

echo "── git push --force / --force-with-lease ──────────────────────"

# Real force-push: MUST block
run_hook block "git push --force"
run_hook block "git push -f"
run_hook block "git push --force origin main"
run_hook block "git push -f origin main"
run_hook block "git push origin main --force"
run_hook block "git push origin main -f"
run_hook block "git push --force-with-lease=ref --force"  # lease + raw force together
run_hook block "cd repo && git push --force"
run_hook block "cd repo; git push -f"

# Lease variant: MUST allow (issue #61 headline)
run_hook allow "git push --force-with-lease"
run_hook allow "git push --force-with-lease origin main"
run_hook allow "git push --force-with-lease=refs/heads/main origin main"
run_hook allow "git push origin main --force-with-lease"
run_hook allow "git push --force-with-includes"  # hypothetical future flag

# Scan-past-separator false positives: MUST allow
run_hook allow 'git push origin main && gh issue create --body "use --force-with-lease"'
run_hook allow 'git push origin main; echo "next step uses --force-with-lease"'
run_hook allow 'echo "do not run git push --force without --force-with-lease"'

# Unrelated commands: MUST allow
run_hook allow "git status"
run_hook allow "git push origin main"
run_hook allow "git push --tags"
run_hook allow "git pull --force"  # not a push
run_hook allow "tail -f /var/log/app.log"
run_hook allow "rm -f file.txt"
run_hook allow "find . -name '*.ex' -exec grep -f patterns {} +"

# Different tool: MUST allow (hook gates on Bash)
run_hook allow "git push --force" Edit

echo ""
echo "── mix ecto.reset / drop (Elixir-only, requires mix.exs) ───────"

# Without mix.exs in CWD, the elixir blocks are silent. Create a temp dir.
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
touch "$TMP/mix.exs"
export CLAUDE_PROJECT_DIR="$TMP"

run_hook block "mix ecto.reset"
run_hook block "mix ecto.drop"
run_hook block "mix ecto.reset --quiet"
run_hook block "cd app && mix ecto.reset"

run_hook allow "mix ecto.migrate"
run_hook allow "mix ecto.rollback --step 1"
run_hook allow "mix ecto.gen.migration add_users"
run_hook allow 'echo "do not run mix ecto.reset" && mix test'  # scan-past

echo ""
echo "── MIX_ENV=prod mix (Elixir-only) ───────────────────────────────"

run_hook block "MIX_ENV=prod mix release"
run_hook block "MIX_ENV=prod mix compile"
run_hook block "cd app && MIX_ENV=prod mix release"

run_hook allow "MIX_ENV=dev mix compile"
run_hook allow "MIX_ENV=test mix test"
run_hook allow 'echo "never use MIX_ENV=prod mix in dev" && mix compile'  # scan-past

# Without mix.exs: MUST allow even for prod (cross-project bleed guard from #55)
unset CLAUDE_PROJECT_DIR
TMP2=$(mktemp -d)
export CLAUDE_PROJECT_DIR="$TMP2"
run_hook allow "MIX_ENV=prod mix release"
run_hook allow "mix ecto.reset"
rm -rf "$TMP2"

echo ""
echo "────────────────────────────────────────────────────────────────"
echo "Passed: $PASS"
echo "Failed: $FAIL"

if (( FAIL > 0 )); then
  echo ""
  echo "Failed cases:"
  for c in "${FAILED_CASES[@]}"; do
    echo "  $c"
  done
  exit 1
fi

exit 0
