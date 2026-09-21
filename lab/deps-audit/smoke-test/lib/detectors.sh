#!/usr/bin/env bash
# Lightweight rule detectors used by smoke-test/runner.sh.
#
# These are a faithful subset of references/rules-impl.md tuned for
# smoke speed and macOS BSD-tool portability. Production audits run the
# full implementations in rules-impl.md; smoke only needs to verify
# detection signal on each fixture.
#
# Each detector echoes a non-negative integer count and never errors out
# on missing files (so the runner can drive heterogeneous fixtures).

count_rule_1() {
  # macOS BSD grep lacks -P; use perl for Unicode character classes.
  # Bidi controls + LRM/RLM + Arabic letter mark.
  find "$1" \( -name '*.ex' -o -name '*.exs' \) -print0 2>/dev/null \
  | xargs -0 perl -CSD -ne '
      print "$ARGV:$.:$_" if /[\x{202A}-\x{202E}\x{2066}-\x{2069}\x{200E}\x{200F}\x{061C}]/
    ' 2>/dev/null | wc -l | tr -d ' '
}

count_rule_2() {
  # Code.eval_string / Code.eval_quoted at module scope (start of line, no leading code).
  grep -RnE '^[[:space:]]*Code\.eval_(string|quoted)\(' \
    --include='*.ex' --include='*.exs' "$1" 2>/dev/null | wc -l | tr -d ' '
}

count_rule_3() {
  # System.cmd / :os.cmd / Port.open inside __before_compile__ or __after_compile__.
  # Heuristic via awk depth tracking.
  local files
  files=$(find "$1" \( -name '*.ex' -o -name '*.exs' \) 2>/dev/null)
  [ -z "${files}" ] && { echo 0; return; }
  # shellcheck disable=SC2086
  awk '
    /__before_compile__|__after_compile__|defmacro/ { in_compile=1 }
    in_compile && /System\.cmd|:os\.cmd|Port\.open/ { print FILENAME":"NR }
    in_compile && /^end$|^  end$/ { in_compile=0 }
  ' ${files} 2>/dev/null | wc -l | tr -d ' '
}

count_rule_4() {
  # :erlang.binary_to_term/1 without :safe option (single-arg call).
  grep -RnE ':erlang\.binary_to_term\([^,]+\)\s*$' \
    --include='*.ex' --include='*.exs' "$1" 2>/dev/null | wc -l | tr -d ' '
}

count_rule_5() {
  # New :git / :path deps in NEW mix.exs that are absent in OLD mix.exs.
  local old="$1" new="$2"
  [ -f "${old}/mix.exs" ] || { echo 0; return; }
  [ -f "${new}/mix.exs" ] || { echo 0; return; }
  local new_git old_git
  new_git=$(grep -cE 'git:[[:space:]]*"|path:[[:space:]]*"' "${new}/mix.exs" 2>/dev/null | tr -dc '0-9')
  old_git=$(grep -cE 'git:[[:space:]]*"|path:[[:space:]]*"' "${old}/mix.exs" 2>/dev/null | tr -dc '0-9')
  : "${new_git:=0}"; : "${old_git:=0}"
  local diff=$((new_git - old_git))
  [ "${diff}" -lt 0 ] && diff=0
  echo "${diff}"
}

count_rule_7() {
  # macOS BSD grep caps {n,} at 255 and lacks -P. Perl for portability.
  # Base64-like string literal >=256 chars in lib/ (skip priv/, test/, assets/).
  find "$1" \( -name '*.ex' -o -name '*.exs' \) \
    -not -path '*/priv/*' -not -path '*/test/*' -not -path '*/assets/*' \
    -print0 2>/dev/null \
  | xargs -0 perl -ne '
      print "$ARGV:$.:match\n" if /"[A-Za-z0-9+\/]{256,}={0,2}"/
    ' 2>/dev/null | wc -l | tr -d ' '
}

# Future detectors stub out here. Keep this file deterministic — no Hex API,
# no network. Rules 6 + 8 (Hex API maintainer change, typosquat) live in
# rules-impl.md and rely on VCR cassettes for smoke (see Component 8).
