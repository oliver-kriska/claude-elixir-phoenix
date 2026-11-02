#!/usr/bin/env bash
# PreToolUse hook: tiered deps-audit gate on `mix deps.get`, `mix deps.update`,
# `mix deps.compile`. Implements the Phase 3 fast-path architecture:
#
#   Tier 0 (<200ms): mix.lock cache hit via .claude/deps-audit/last-run.json.
#                    Vouches for mix.lock only, so it skips rule 1, never rule 5.
#   Tier 1 (<2s):    rule 1 (bidi) + rule 5 (new git/github/path deps)
#   Tier 2 (opt-in): full Phase 2 pipeline (only when block_on_unvetted = :full)
#
# Rule 5 always runs: a dep added to mix.exs is not in mix.lock until the
# `mix deps.get` being judged adds it, so no lock-keyed cache can vouch for it.
# A new non-Hex dep is cleared by a hex_vet.exs entry whose package and version
# match its pin (`/phx:deps-vet <name> <pin>`).
#
# Enforcement of `hex_vet.exs` policy.block_on_unvetted:
#   false       → warn-only, exit 0
#   :new_only   → block if PR ADDS an unvetted version (default for new projects)
#   :strict     → block if ANY locked version is unvetted
#   :full       → run Tier 2 pipeline then apply :strict rules
#
# Escape hatch: PHX_SKIP_DEPS_AUDIT=1 in the hook’s own environment (set before
# Claude Code starts) short-circuits to exit 0. A prefix on the judged command
# does not count: the block message reaches Claude, and a bypass Claude can
# type itself would make every block advisory.

set -u  # No -e: we need to handle every failure mode explicitly.

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')

# Filter: only Bash with deps-related mix commands
[[ "$TOOL" == "Bash" ]] || exit 0

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
[[ -n "$COMMAND" ]] || exit 0

if ! echo "$COMMAND" | grep -qE 'mix[[:space:]]+deps\.(get|update|compile)\b'; then
  exit 0
fi

# Escape hatch
if [[ "${PHX_SKIP_DEPS_AUDIT:-}" == "1" ]]; then
  echo "phx-deps-audit: skipped (PHX_SKIP_DEPS_AUDIT=1)" >&2
  exit 0
fi

# Locate project root (cwd, since the gate runs in the user’s project)
PROJECT_ROOT="$(pwd)"
LOCK_FILE="$PROJECT_ROOT/mix.lock"
[[ -f "$LOCK_FILE" ]] || exit 0  # no mix.lock yet → first deps.get, defer

CACHE_DIR="$PROJECT_ROOT/.claude/deps-audit"
LAST_RUN="$CACHE_DIR/last-run.json"
HEX_VET="$PROJECT_ROOT/hex_vet.exs"

# Read policy mode (default :new_only when ledger exists, :false when absent).
# Sets POLICY_MODE, and POLICY_INFERRED=true when the ledger exists but sets no
# block_on_unvetted key — creating hex_vet.exs alone flips warn-only to blocking,
# so block messages say where the mode came from.
#
# Parser hardening (v3.0.1 hotfix): strip Elixir line-comments (# ...) BEFORE
# matching, and take the LAST uncommented match. Elixir map literals follow
# last-assignment-wins semantics at compile time, so we mirror that. The
# previous head -1 of the raw file silently picked up commented examples like
# `# block_on_unvetted: false  # see migration guide` and downgraded
# enforcement — fail-open in the worst possible direction.
POLICY_MODE="false"
POLICY_INFERRED=false
read_policy_mode() {
  [[ -f "$HEX_VET" ]] || return 0
  local line count=0 mode=""
  local re='block_on_unvetted:[[:space:]]*(:[a-z_]+|true|false)'
  while IFS= read -r line || [[ -n "$line" ]]; do
    line=${line%%#*}
    while [[ $line =~ $re ]]; do
      mode=${BASH_REMATCH[1]}
      count=$((count + 1))
      line=${line#*"${BASH_REMATCH[0]}"}
    done
  done < "$HEX_VET"
  if [[ "$count" -gt 1 ]]; then
    echo "phx-deps-audit: hex_vet.exs has $count uncommented block_on_unvetted keys; using last (Elixir map-literal semantics)" >&2
  fi
  case "$mode" in
    "false"|":new_only"|":strict"|":full") POLICY_MODE="$mode" ;;
    "true")
      POLICY_MODE=":strict"
      echo "phx-deps-audit: block_on_unvetted: true is deprecated; treating as :strict" >&2
      ;;
    "")
      POLICY_MODE=":new_only"  # default when ledger exists
      POLICY_INFERRED=true
      ;;
    *) POLICY_MODE=":new_only" ;;  # unknown value: fail closed
  esac
}

read_policy_mode

# ──────────── Tier 0: cache-hit (<200ms budget) ────────────
# Fields written by /phx:deps-audit (output-renderer.md §"Sidecar file").
tier0_cache_hit() {
  [[ -f "$LAST_RUN" ]] || return 1

  local lock_sha cached_sha cached_passed cached_policy
  lock_sha=$(shasum -a 256 "$LOCK_FILE")
  lock_sha=${lock_sha%% *}
  cached_sha=$(jq -r '.lock_sha // empty' "$LAST_RUN" 2>/dev/null)
  cached_passed=$(jq -r '.audit_passed // false' "$LAST_RUN" 2>/dev/null)
  cached_policy=$(jq -r '.policy_mode // empty' "$LAST_RUN" 2>/dev/null)

  [[ "$lock_sha" == "$cached_sha" ]] || return 1
  [[ "$cached_passed" == "true" ]] || return 1
  [[ "$cached_policy" == "$POLICY_MODE" ]] || return 1
  return 0
}

# ──────────── Tier 1: deterministic fast rules (<2s budget) ────────────
# Rule 1: bidi/RLO chars in newly-locked packages
# Rule 5: new git/github/path deps via a normalized mix.exs dep diff
#
# Both are zero-FP, no network, no LLM. If clean → exit 0 + soft warn.

tier1_findings_file="$(mktemp -t phx-tier1-findings.XXXXXX)"
trap 'rm -f "$tier1_findings_file"' EXIT

tier1_rule1_bidi() {
  # Scan mix.lock for bidi/RLO chars (U+202A–U+202E, U+2066–U+2069) that could
  # smuggle hostile content in dep entries. Matches their UTF-8 bytes under
  # LC_ALL=C, so no Unicode locale and no inline perl program is needed.
  if ! LC_ALL=C grep -qE $'\xe2\x80[\xaa-\xae]|\xe2\x81[\xa6-\xa9]' "$LOCK_FILE" 2>/dev/null; then
    return 0  # clean
  fi
  echo '{"rule_id":1,"severity":"block","file":"mix.lock","message":"Bidi control char in mix.lock"}' \
    >> "$tier1_findings_file"
  return 1
}

# Print one line per non-Hex dep in a mix.exs: "<name> <kind>:<source>[@<refkind>:<ref>]",
# e.g. "my_dep github:org/repo@tag:v1.0". Comments are stripped and the file is
# flattened first, so a dep tuple the formatter split across lines normalizes
# the same as a one-liner. A tuple whose name doesn’t parse prints as "?" so it
# still gets flagged (and can never be vetted).
non_hex_dep_specs() {
  local file="$1" line flat="" chunk name spec
  local re_name='^([a-z_0-9]+)'
  local re_src='(^|[[:space:],])(git|github|path):[[:space:]]*"([^"]*)"'
  local re_ref='(^|[[:space:],])(tag|ref|branch):[[:space:]]*"([^"]*)"'
  [[ -s "$file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    flat+="${line%%#*} "
  done < "$file"
  while [[ "$flat" == *"{:"* ]]; do
    flat=${flat#*"{:"}
    chunk=${flat%%\}*}
    [[ $chunk =~ $re_src ]] || continue
    spec="${BASH_REMATCH[2]}:${BASH_REMATCH[3]}"
    if [[ $chunk =~ $re_ref ]]; then
      spec+="@${BASH_REMATCH[2]}:${BASH_REMATCH[3]}"
    fi
    name="?"
    [[ $chunk =~ $re_name ]] && name=${BASH_REMATCH[1]}
    printf '%s %s\n' "$name" "$spec"
  done
}

# True when hex_vet.exs has an uncommented audit map with package == $1 and
# version == $2. Fields are paired per map (reset on each `%{`), so a package
# from one entry never pairs with a version from another.
ledger_vets_pin() {
  [[ -f "$HEX_VET" ]] || return 1
  local want_pkg="$1" want_ver="$2" line pkg="" ver=""
  local re_pkg='package:[[:space:]]*"([^"]*)"'
  local re_ver='version:[[:space:]]*"([^"]*)"'
  while IFS= read -r line || [[ -n "$line" ]]; do
    line=${line%%#*}
    if [[ "$line" == *"%{"* ]]; then
      pkg=""
      ver=""
    fi
    [[ $line =~ $re_pkg ]] && pkg=${BASH_REMATCH[1]}
    [[ $line =~ $re_ver ]] && ver=${BASH_REMATCH[1]}
    if [[ "$pkg" == "$want_pkg" && "$ver" == "$want_ver" ]]; then
      return 0
    fi
  done < "$HEX_VET"
  return 1
}

tier1_rule5_git_path_deps() {
  # Detect git/github/path deps newly added in mix.exs since the reference
  # commit. Reference defaults to origin/main; override via PHX_DEPS_AUDIT_BASE.
  local base="${PHX_DEPS_AUDIT_BASE:-origin/main}"
  local mix_exs="$PROJECT_ROOT/mix.exs"
  [[ -f "$mix_exs" ]] || return 0

  # Pull base mix.exs; fall back to empty (treats whole file as new)
  local base_exs added name spec rc=0
  base_exs=$(mktemp -t phx-base-mix.XXXXXX)
  git -C "$PROJECT_ROOT" show "${base}:mix.exs" >"$base_exs" 2>/dev/null || : >"$base_exs"

  # Dep pins in NEW but not in BASE
  added=$(comm -13 \
            <(non_hex_dep_specs "$base_exs" | sort -u) \
            <(non_hex_dep_specs "$mix_exs"  | sort -u))
  rm -f "$base_exs"

  [[ -z "$added" ]] && return 0

  while read -r name spec; do
    [[ -z "$name" ]] && continue
    ledger_vets_pin "$name" "$spec" && continue
    jq -cn --arg dep "$name" --arg pin "$spec" \
      '{rule_id: 5, severity: "warn", file: "mix.exs", message: "New non-Hex dep", dep: $dep, pin: $pin}' \
      >> "$tier1_findings_file"
    rc=1
  done <<< "$added"
  return $rc
}

tier0_hit=false
tier0_cache_hit && tier0_hit=true

tier1_clean=true
if ! $tier0_hit; then
  tier1_rule1_bidi || tier1_clean=false
fi
tier1_rule5_git_path_deps || tier1_clean=false

if $tier1_clean; then
  $tier0_hit && exit 0  # silent — common path, no narration
  # Soft hint, no block. The user can still opt into full audit explicitly.
  echo "phx-deps-audit: Tier 1 clean. Run /phx:deps-audit for full pipeline." >&2
  exit 0
fi

# ──────────── Findings: apply policy ────────────
findings_count=$(wc -l < "$tier1_findings_file" | tr -d ' ')
findings_summary=$(jq -rs 'group_by(.rule_id) | map("rule \(.[0].rule_id): \(length) findings") | join(", ")' \
                   "$tier1_findings_file" 2>/dev/null || echo "Tier 1 findings: $findings_count")
vet_hints=$(jq -rs 'map(select(.rule_id == 5) | "    /phx:deps-vet \(.dep) \(.pin)") | join("\n")' \
            "$tier1_findings_file" 2>/dev/null)

policy_note=""
if $POLICY_INFERRED; then
  policy_note="  Policy $POLICY_MODE is the default because hex_vet.exs sets no policy.block_on_unvetted; set it to false for warn-only."
fi

override_lines=(
  "  Override: PHX_SKIP_DEPS_AUDIT=1 is read from Claude Code’s environment, not from this command,"
  "            so a prefix on the command does not work. Set it before starting Claude Code, or have"
  "            the user run the command themselves (\`! mix deps.get\` in Claude Code). Do not retry."
)

print_block() {
  local headline="$1"
  printf '%s\n' "$headline" "  $findings_summary" >&2
  if [[ -n "$vet_hints" ]]; then
    printf '%s\n' "  Vet each new non-Hex dep (records its exact pin in hex_vet.exs):" "$vet_hints" >&2
  fi
  [[ -n "$policy_note" ]] && printf '%s\n' "$policy_note" >&2
  printf '%s\n' "${override_lines[@]}" >&2
}

case "$POLICY_MODE" in
  "false")
    printf '%s\n' \
      "phx-deps-audit: Tier 1 found risk signals (warn-only mode)." \
      "  $findings_summary" \
      "  Run /phx:deps-audit for full triage." >&2
    exit 0
    ;;

  ":new_only")
    # Only block if findings are on NEW dep additions
    if grep -q '"rule_id":1' "$tier1_findings_file"; then
      print_block "phx-deps-audit: BLOCKED (:new_only). Bidi control char in mix.lock."
      exit 2
    fi
    if grep -q '"rule_id":5' "$tier1_findings_file"; then
      print_block "phx-deps-audit: BLOCKED (:new_only). New git/github/path dep needs vetting."
      exit 2
    fi
    exit 0
    ;;

  ":strict"|":full")
    # Tier 2 invocation is intentionally NOT chained here — the hook budget is
    # already exceeded once we’re past Tier 1. :full mode runs Tier 2 via the
    # /phx:deps-audit skill body, not from the hook.
    print_block "phx-deps-audit: BLOCKED ($POLICY_MODE). Tier 1 found risk signals."
    exit 2
    ;;
esac

exit 0
