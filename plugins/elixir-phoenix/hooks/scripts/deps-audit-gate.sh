#!/usr/bin/env bash
# PreToolUse hook: tiered deps-audit gate on `mix deps.get`, `mix deps.update`,
# `mix deps.compile`. Implements the Phase 3 fast-path architecture:
#
#   Tier 0 (<200ms): cache-hit check via .claude/deps-audit/last-run.json
#   Tier 1 (<2s):    rule 1 (bidi) + rule 5 (new :git/:path deps)
#   Tier 2 (opt-in): full Phase 2 pipeline (only when block_on_unvetted = :full)
#
# Enforcement of `hex_vet.exs` policy.block_on_unvetted:
#   false       → warn-only, exit 0
#   :new_only   → block if PR ADDS an unvetted version (default for new projects)
#   :strict     → block if ANY locked version is unvetted
#   :full       → run Tier 2 pipeline then apply :strict rules
#
# Escape hatch: PHX_SKIP_DEPS_AUDIT=1 short-circuits to exit 0.

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

# Locate project root (cwd, since the gate runs in the user's project)
PROJECT_ROOT="$(pwd)"
LOCK_FILE="$PROJECT_ROOT/mix.lock"
[[ -f "$LOCK_FILE" ]] || exit 0  # no mix.lock yet → first deps.get, defer

CACHE_DIR="$PROJECT_ROOT/.claude/deps-audit"
LAST_RUN="$CACHE_DIR/last-run.json"
HEX_VET="$PROJECT_ROOT/hex_vet.exs"

# Read policy mode (default :new_only when ledger exists, :false when absent).
#
# Parser hardening (v3.0.1 hotfix): strip Elixir line-comments (# ...) BEFORE
# matching, and take the LAST uncommented match. Elixir map literals follow
# last-assignment-wins semantics at compile time, so we mirror that. The
# previous head -1 of the raw file silently picked up commented examples like
# `# block_on_unvetted: false  # see migration guide` and downgraded
# enforcement — fail-open in the worst possible direction.
read_policy_mode() {
  if [[ ! -f "$HEX_VET" ]]; then
    echo "false"
    return
  fi
  local stripped matches count mode
  stripped=$(sed 's/#.*$//' "$HEX_VET")
  matches=$(printf '%s\n' "$stripped" \
            | grep -oE 'block_on_unvetted:[[:space:]]*(:[a-z_]+|true|false)' \
            | sed -E 's/.*block_on_unvetted:[[:space:]]*//')
  if [[ -n "$matches" ]]; then
    count=$(printf '%s\n' "$matches" | wc -l | tr -d ' ')
  else
    count=0
  fi
  if [[ "$count" -gt 1 ]]; then
    echo "phx-deps-audit: hex_vet.exs has $count uncommented block_on_unvetted keys; using last (Elixir map-literal semantics)" >&2
  fi
  mode=$(printf '%s\n' "$matches" | tail -1)
  case "$mode" in
    "false"|":new_only"|":strict"|":full") echo "$mode" ;;
    "true")
      echo ":strict"
      echo "phx-deps-audit: block_on_unvetted: true is deprecated; treating as :strict" >&2
      ;;
    *) echo ":new_only" ;;  # default when ledger exists
  esac
}

POLICY_MODE=$(read_policy_mode)

# ──────────── Tier 0: cache-hit (<200ms budget) ────────────
tier0_cache_hit() {
  [[ -f "$LAST_RUN" ]] || return 1

  local lock_sha cached_sha cached_passed cached_policy
  lock_sha=$(shasum -a 256 "$LOCK_FILE" | awk '{print $1}')
  cached_sha=$(jq -r '.lock_sha // empty' "$LAST_RUN" 2>/dev/null)
  cached_passed=$(jq -r '.audit_passed // false' "$LAST_RUN" 2>/dev/null)
  cached_policy=$(jq -r '.policy_mode // empty' "$LAST_RUN" 2>/dev/null)

  [[ "$lock_sha" == "$cached_sha" ]] || return 1
  [[ "$cached_passed" == "true" ]] || return 1
  [[ "$cached_policy" == "$POLICY_MODE" ]] || return 1
  return 0
}

if tier0_cache_hit; then
  exit 0  # silent — common path, no narration
fi

# ──────────── Tier 1: deterministic fast rules (<2s budget) ────────────
# Rule 1: bidi/RLO chars in newly-locked packages
# Rule 5: new :git or :path deps via mix.exs AST diff
#
# Both are zero-FP, no network, no LLM. If clean → exit 0 + soft warn.

tier1_findings_file="$(mktemp -t phx-tier1-findings.XXXXXX)"
trap 'rm -f "$tier1_findings_file"' EXIT

tier1_rule1_bidi() {
  # Scan mix.lock for bidi/RLO chars that could smuggle hostile content in
  # dep entries. Fast: single file, single perl pass. -CSD enables UTF-8 so
  # the \x{NNNN} character classes match the UTF-8 encoding, not bytes.
  if perl -CSD -ne 'exit 1 if /[\x{202A}-\x{202E}\x{2066}-\x{2069}]/' "$LOCK_FILE" 2>/dev/null; then
    return 0  # clean
  fi
  echo '{"rule_id":1,"severity":"block","file":"mix.lock","message":"Bidi control char in mix.lock"}' \
    >> "$tier1_findings_file"
  return 1
}

tier1_rule5_git_path_deps() {
  # Detect :git or :path deps newly added in mix.exs since the reference commit.
  # Reference defaults to origin/main; override via PHX_DEPS_AUDIT_BASE.
  local base="${PHX_DEPS_AUDIT_BASE:-origin/main}"
  local mix_exs="$PROJECT_ROOT/mix.exs"
  [[ -f "$mix_exs" ]] || return 0

  # Pull base mix.exs; fall back to empty (treats whole file as new)
  local base_exs
  base_exs=$(mktemp -t phx-base-mix.XXXXXX)
  git -C "$PROJECT_ROOT" show "${base}:mix.exs" >"$base_exs" 2>/dev/null || : >"$base_exs"

  # Lines mentioning :git or :path in NEW but not in BASE
  local added
  added=$(comm -13 \
            <(grep -E '(\sgit:|\spath:)' "$base_exs" | sort -u) \
            <(grep -E '(\sgit:|\spath:)' "$mix_exs"  | sort -u))
  rm -f "$base_exs"

  [[ -z "$added" ]] && return 0

  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    local dep
    dep=$(echo "$line" | grep -oE '\{:[a-z_0-9]+' | head -1 | sed 's/{://')
    printf '{"rule_id":5,"severity":"warn","file":"mix.exs","message":"New non-Hex dep","dep":"%s"}\n' "$dep" \
      >> "$tier1_findings_file"
  done <<< "$added"
  return 1
}

tier1_clean=true
tier1_rule1_bidi || tier1_clean=false
tier1_rule5_git_path_deps || tier1_clean=false

if $tier1_clean; then
  # Soft hint, no block. The user can still opt into full audit explicitly.
  echo "phx-deps-audit: Tier 1 clean. Run /phx:deps-audit for full pipeline." >&2
  exit 0
fi

# ──────────── Findings: apply policy ────────────
findings_count=$(wc -l < "$tier1_findings_file" | tr -d ' ')
findings_summary=$(jq -s 'group_by(.rule_id) | map("\(.[0].rule_id): \(length) findings") | join(", ")' \
                   "$tier1_findings_file" 2>/dev/null || echo "Tier 1 findings: $findings_count")

case "$POLICY_MODE" in
  "false")
    cat >&2 <<MSG
phx-deps-audit: Tier 1 found risk signals (warn-only mode).
  $findings_summary
  Run /phx:deps-audit for full triage.
MSG
    exit 0
    ;;

  ":new_only")
    # Only block if findings are on NEW dep additions
    if grep -q '"rule_id":1' "$tier1_findings_file"; then
      cat >&2 <<MSG
phx-deps-audit: BLOCKED (:new_only). Bidi control char in mix.lock.
  $findings_summary
  Override: PHX_SKIP_DEPS_AUDIT=1 mix deps.get
MSG
      exit 2
    fi
    if grep -q '"rule_id":5' "$tier1_findings_file"; then
      cat >&2 <<MSG
phx-deps-audit: BLOCKED (:new_only). New :git/:path dep needs vetting.
  $findings_summary
  Vet first: /phx:deps-vet <pkg> <ver>
  Override:  PHX_SKIP_DEPS_AUDIT=1 mix deps.get
MSG
      exit 2
    fi
    exit 0
    ;;

  ":strict"|":full")
    cat >&2 <<MSG
phx-deps-audit: BLOCKED ($POLICY_MODE). Tier 1 found risk signals.
  $findings_summary
  Vet:      /phx:deps-vet
  Override: PHX_SKIP_DEPS_AUDIT=1 mix deps.get
MSG
    # Tier 2 invocation is intentionally NOT chained here — the hook budget is
    # already exceeded once we're past Tier 1. :full mode runs Tier 2 via the
    # /phx:deps-audit skill body, not from the hook.
    exit 2
    ;;
esac

exit 0
