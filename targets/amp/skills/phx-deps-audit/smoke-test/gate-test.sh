#!/usr/bin/env bash
# Gate smoke harness — exercises deps-audit-gate.sh end-to-end with stdin JSON.
#
# The fixtures.d/ harness tests rule DETECTORS (counts rule N matches in file
# trees). This harness tests the POLICY PARSER and BLOCK ENFORCEMENT in the
# PreToolUse hook itself — different mechanism, kept separate.
#
# Each fixture is a function that:
#   1. Sets up a hex_vet.exs + mix.lock in an isolated tmpdir
#   2. Pipes a Bash tool_input JSON into the gate from that cwd
#   3. Asserts exit code AND stderr regex
#
# Usage: bash smoke-test/gate-test.sh
# Called automatically from runner.sh after fixtures.d/ pass.

set -u

HARNESS_ROOT="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(cd "${HARNESS_ROOT}/../../.." && pwd)"
GATE="${PLUGIN_ROOT}/hooks/scripts/deps-audit-gate.sh"

[ -x "$GATE" ] || { echo "gate-test: $GATE not found or not executable" >&2; exit 1; }

red()   { printf '\033[31m%s\033[0m' "$*"; }
green() { printf '\033[32m%s\033[0m' "$*"; }

gate_fail=0
gate_pass=0

# Pipe a deps.get command through the gate, capture stderr + exit.
# $1 = fixture cwd, sets globals: GATE_OUT, GATE_EXIT.
run_gate() {
  local cwd="$1"
  local input='{"tool_name":"Bash","tool_input":{"command":"mix deps.get"}}'
  GATE_OUT=$(cd "$cwd" && echo "$input" | bash "$GATE" 2>&1)
  GATE_EXIT=$?
}

# $1 = fixture name, $2 = expected exit, $3 = stderr regex
assert_gate() {
  local name="$1" want_exit="$2" want_regex="$3"
  local ok=1
  if [ "$GATE_EXIT" != "$want_exit" ]; then
    echo "  $(red 'fail') gate:${name} exit got=${GATE_EXIT} want=${want_exit}"
    ok=0
  fi
  if ! echo "$GATE_OUT" | grep -qE "$want_regex"; then
    echo "  $(red 'fail') gate:${name} stderr missing /${want_regex}/"
    echo "    got:"
    echo "$GATE_OUT" | sed 's/^/      /'
    ok=0
  fi
  if [ "$ok" = "1" ]; then
    echo "  $(green 'ok'  ) gate:${name} exit:${want_exit} /${want_regex}/"
    gate_pass=$((gate_pass + 1))
  else
    gate_fail=$((gate_fail + 1))
  fi
}

# Build a fixture tmpdir with mix.lock containing a bidi char (forces Tier 1 to
# fire so the policy mode actually applies). Returns path on stdout.
make_fixture_dir() {
  local fixture_name="$1"
  local hex_vet_content="$2"
  local d
  d=$(mktemp -d -t "phx-gate-${fixture_name}.XXXXXX")
  # mix.lock with bidi (\xe2\x80\xae = U+202E RLO) — triggers Tier 1 rule 1
  printf 'normal_pkg: line\nattacker\xe2\x80\xae sneaky\n' > "$d/mix.lock"
  printf '%s' "$hex_vet_content" > "$d/hex_vet.exs"
  # mix.exs (gate looks for it for rule 5)
  printf 'defmodule X.MixProject do\n  use Mix.Project\n  def project, do: [app: :x, deps: []]\nend\n' > "$d/mix.exs"
  # Init git so the rule 5 diff path doesn't blow up
  (cd "$d" && git init -q && git add . && git commit -q -m init >/dev/null 2>&1) || :
  echo "$d"
}

# ───── Fixture 15: commented_policy ─────
# hex_vet.exs has commented `block_on_unvetted: false` BEFORE the real `:strict`.
# Pre-v3.0.1 bug: gate grabs the first match (`false`) → exit 0 (warn-only).
# Post-fix: comments stripped → only `:strict` matches → BLOCK (exit 2).
fixture_15_commented_policy() {
  local d
  d=$(make_fixture_dir "15_commented_policy" "$(cat <<'ELIXIR'
# Phase 3 migration: previous default was
# block_on_unvetted: false  <- this MUST be ignored
%{
  imports: %{},
  audits: [],
  policy: %{
    criteria_required: :safe_to_deploy,
    block_on_unvetted: :strict
  }
}
ELIXIR
)")
  run_gate "$d"
  assert_gate "15_commented_policy" 2 'BLOCKED \(:strict\)'
  rm -rf "$d"
}

# ───── Fixture 16: multi_policy_warning ─────
# Two uncommented `block_on_unvetted:` keys. Elixir map-literal last-wins
# semantics → gate uses the LAST one (`:new_only`) and emits a stderr warning
# about the duplicate.
fixture_16_multi_policy_warning() {
  local d
  d=$(make_fixture_dir "16_multi_policy_warning" "$(cat <<'ELIXIR'
%{
  policy: %{
    block_on_unvetted: :strict
  }
}
%{
  policy: %{
    block_on_unvetted: :new_only
  }
}
ELIXIR
)")
  run_gate "$d"
  # :new_only with bidi in mix.lock → rule 1 hits → block exit 2.
  # Critical: stderr must include the multi-match warning.
  assert_gate "16_multi_policy_warning" 2 'has 2 uncommented block_on_unvetted keys'
  rm -rf "$d"
}

# ───── Sanity: clean policy (no commented_policy regression) ─────
# Standard :strict ledger, no commented keys, no duplicates. Should still block
# on the bidi finding. Acts as a guard against the parser over-stripping.
fixture_17_clean_strict() {
  local d
  d=$(make_fixture_dir "17_clean_strict" "$(cat <<'ELIXIR'
%{
  policy: %{block_on_unvetted: :strict}
}
ELIXIR
)")
  run_gate "$d"
  # Must NOT emit the multi-match warning (only 1 uncommented key)
  if echo "$GATE_OUT" | grep -q 'uncommented block_on_unvetted'; then
    echo "  $(red 'fail') gate:17_clean_strict spurious multi-match warning"
    gate_fail=$((gate_fail + 1))
  else
    assert_gate "17_clean_strict" 2 'BLOCKED \(:strict\)'
  fi
  rm -rf "$d"
}

main() {
  echo "Gate smoke tests (deps-audit-gate.sh):"
  fixture_15_commented_policy
  fixture_16_multi_policy_warning
  fixture_17_clean_strict
  echo
  echo "gate-test: ${gate_pass} pass, ${gate_fail} fail"
  [ "$gate_fail" -eq 0 ]
}

main "$@"
