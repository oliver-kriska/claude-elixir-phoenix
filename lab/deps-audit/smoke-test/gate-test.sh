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
PLUGIN_ROOT="$(cd "${HARNESS_ROOT}/../../../plugins/elixir-phoenix" && pwd)"
GATE="${PLUGIN_ROOT}/hooks/scripts/deps-audit-gate.sh"

[ -x "$GATE" ] || { echo "gate-test: $GATE not found or not executable" >&2; exit 1; }

red()   { printf '\033[31m%s\033[0m' "$*"; }
green() { printf '\033[32m%s\033[0m' "$*"; }

gate_fail=0
gate_pass=0

# Pipe a deps.get command through the gate, capture stderr + exit.
# $1 = fixture cwd, $2 = optional command (default `mix deps.get`).
# Sets globals: GATE_OUT, GATE_EXIT.
run_gate() {
  local cwd="$1" cmd="${2:-mix deps.get}"
  local input
  input=$(jq -cn --arg c "$cmd" '{tool_name: "Bash", tool_input: {command: $c}}')
  GATE_OUT=$(cd "$cwd" && echo "$input" | env -u PHX_SKIP_DEPS_AUDIT PHX_DEPS_AUDIT_BASE=HEAD bash "$GATE" 2>&1)
  GATE_EXIT=$?
}

# Assert the gate output does NOT match a regex. $1 = name, $2 = regex.
refute_gate() {
  if echo "$GATE_OUT" | grep -qE "$2"; then
    echo "  $(red 'fail') gate:$1 stderr unexpectedly matched /$2/"
    printf '      %s\n' "${GATE_OUT//$'\n'/$'\n'      }"
    gate_fail=$((gate_fail + 1))
  else
    echo "  $(green 'ok'  ) gate:$1 no /$2/"
    gate_pass=$((gate_pass + 1))
  fi
}

# Rule 5 fixture: clean mix.lock, a base commit whose mix.exs has only Hex
# deps, then the working-tree mix.exs replaced with $2 (deps list body).
# $3 = hex_vet.exs content ("" = no ledger). Gate diffs against HEAD.
make_rule5_dir() {
  local fixture_name="$1" deps_body="$2" hex_vet_content="$3"
  local d
  d=$(mktemp -d -t "phx-gate-${fixture_name}.XXXXXX")
  printf '%%{"jason": {:hex, :jason, "1.4.4"}}\n' > "$d/mix.lock"
  printf 'defmodule X.MixProject do\n  use Mix.Project\n  defp deps do\n    [\n      {:jason, "~> 1.4"}\n    ]\n  end\nend\n' > "$d/mix.exs"
  [ -n "$hex_vet_content" ] && printf '%s' "$hex_vet_content" > "$d/hex_vet.exs"
  (cd "$d" && git init -q && git add . && git -c user.email=t@t -c user.name=t commit -q -m init >/dev/null 2>&1) || :
  printf 'defmodule X.MixProject do\n  use Mix.Project\n  defp deps do\n    [\n      {:jason, "~> 1.4"},\n%s\n    ]\n  end\nend\n' "$deps_body" > "$d/mix.exs"
  echo "$d"
}

LEDGER_NO_POLICY='%{imports: %{}, audits: [], policy: %{criteria_required: :safe_to_deploy}}'

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
    printf '      %s\n' "${GATE_OUT//$'\n'/$'\n'      }"
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

# ───── Fixture 18: github_dep_detected (issue #160 §1, §5) ─────
# A `github:` dep must count as a new non-Hex dep, and a ledger with no
# block_on_unvetted key must say the :new_only mode was inferred.
fixture_18_github_dep_detected() {
  local d
  d=$(make_rule5_dir "18_github" '      {:my_dep, github: "org/repo", tag: "1.0"}' "$LEDGER_NO_POLICY")
  run_gate "$d"
  assert_gate "18_github_blocked" 2 'BLOCKED \(:new_only\)\. New git/github/path dep'
  assert_gate "18_github_vet_hint" 2 '/phx:deps-vet my_dep github:org/repo@tag:1\.0'
  assert_gate "18_github_inferred_note" 2 'is the default because hex_vet\.exs sets no'
  rm -rf "$d"
}

# ───── Fixture 19: multiline_tuple ─────
# A formatter-split tuple keeps its name and ref.
fixture_19_multiline_tuple() {
  local d
  d=$(make_rule5_dir "19_multiline" "$(printf '      {:my_dep,\n       git: "https://example.com/org/repo.git",\n       ref: "abc123"}')" "$LEDGER_NO_POLICY")
  run_gate "$d"
  assert_gate "19_multiline" 2 '/phx:deps-vet my_dep git:https://example\.com/org/repo\.git@ref:abc123'
  rm -rf "$d"
}

# ───── Fixture 20: vetted_pin_clears (issue #160 §3) ─────
fixture_20_vetted_pin_clears() {
  local d
  d=$(make_rule5_dir "20_vetted" '      {:my_dep, github: "org/repo", tag: "1.0"}' "$(printf '%s\n' \
    '%{' \
    '  imports: %{},' \
    '  audits: [' \
    '    %{' \
    '      criteria: :safe_to_deploy,' \
    '      notes: "Our own repo",' \
    '      package: "my_dep",' \
    '      reviewed_at: ~D[2026-11-02],' \
    '      reviewer: "t@t",' \
    '      version: "github:org/repo@tag:1.0"' \
    '    }' \
    '  ],' \
    '  policy: %{criteria_required: :safe_to_deploy, block_on_unvetted: :new_only}' \
    '}')")
  run_gate "$d"
  assert_gate "20_vetted_pin_clears" 0 'Tier 1 clean'
  rm -rf "$d"
}

# ───── Fixture 21: vetted_other_ref_blocks ─────
# A vet for tag 0.9 must not clear tag 1.0; a commented entry must not count.
fixture_21_vetted_other_ref_blocks() {
  local d
  d=$(make_rule5_dir "21_other_ref" '      {:my_dep, github: "org/repo", tag: "1.0"}' "$(printf '%s\n' \
    '%{' \
    '  audits: [' \
    '    %{package: "my_dep", version: "github:org/repo@tag:0.9", criteria: :safe_to_deploy},' \
    '    # %{package: "my_dep", version: "github:org/repo@tag:1.0", criteria: :safe_to_deploy},' \
    '    %{package: "other", version: "1.0.0", criteria: :safe_to_deploy}' \
    '  ],' \
    '  policy: %{block_on_unvetted: :new_only}' \
    '}')")
  run_gate "$d"
  assert_gate "21_other_ref_blocks" 2 'BLOCKED \(:new_only\)'
  refute_gate "21_explicit_policy_no_note" 'is the default because'
  rm -rf "$d"
}

# ───── Fixture 22: cache_hit_does_not_skip_rule5 (issue #160 §4) ─────
fixture_22_cache_hit_does_not_skip_rule5() {
  local d sha
  d=$(make_rule5_dir "22_cache" '      {:my_dep, path: "../my_dep"}' "$LEDGER_NO_POLICY")
  sha=$(shasum -a 256 "$d/mix.lock"); sha=${sha%% *}
  mkdir -p "$d/.claude/deps-audit"
  printf '{"version":1,"lock_sha":"%s","audit_passed":true,"policy_mode":":new_only"}\n' "$sha" \
    > "$d/.claude/deps-audit/last-run.json"
  run_gate "$d"
  assert_gate "22_cache_hit_still_blocks_new_path_dep" 2 '/phx:deps-vet my_dep path:\.\./my_dep'
  rm -rf "$d"
}

# ───── Fixture 23: commented_dep_ignored ─────
fixture_23_commented_dep_ignored() {
  local d
  d=$(make_rule5_dir "23_commented" '      # {:my_dep, path: "../my_dep"}' "$LEDGER_NO_POLICY")
  run_gate "$d"
  assert_gate "23_commented_dep_ignored" 0 'Tier 1 clean'
  rm -rf "$d"
}

# ───── Fixture 24: command_prefix_is_not_an_override (issue #160 §2) ─────
# The gate reads its own environment; an in-command prefix must not bypass it,
# and the message must say so instead of suggesting the prefix.
fixture_24_command_prefix_is_not_an_override() {
  local d
  d=$(make_rule5_dir "24_prefix" '      {:my_dep, github: "org/repo"}' "$LEDGER_NO_POLICY")
  run_gate "$d" "PHX_SKIP_DEPS_AUDIT=1 mix deps.get"
  assert_gate "24_prefix_still_blocks" 2 'not from this command'
  refute_gate "24_no_prefix_suggestion" 'Override: +PHX_SKIP_DEPS_AUDIT=1 mix deps\.get'
  rm -rf "$d"
}

main() {
  echo "Gate smoke tests (deps-audit-gate.sh):"
  fixture_15_commented_policy
  fixture_16_multi_policy_warning
  fixture_17_clean_strict
  fixture_18_github_dep_detected
  fixture_19_multiline_tuple
  fixture_20_vetted_pin_clears
  fixture_21_vetted_other_ref_blocks
  fixture_22_cache_hit_does_not_skip_rule5
  fixture_23_commented_dep_ignored
  fixture_24_command_prefix_is_not_an_override
  echo
  echo "gate-test: ${gate_pass} pass, ${gate_fail} fail"
  [ "$gate_fail" -eq 0 ]
}

main "$@"
