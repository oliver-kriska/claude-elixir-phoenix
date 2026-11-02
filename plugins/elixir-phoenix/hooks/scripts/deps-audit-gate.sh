#!/usr/bin/env bash
# PreToolUse hook: tiered deps-audit gate on every mix command that fetches
# deps: `mix deps.get`, `mix deps.update`, `mix deps.compile`, `mix igniter.install`,
# and any mix.exs alias that runs one of them (Phoenix’s `mix setup`). hooks.json
# fires it on `Bash(*mix *)`; every other mix command exits silently here.
# Implements the Phase 3 fast-path architecture:
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

[[ "$COMMAND" == *mix* ]] || exit 0

# Locate project root (cwd, since the gate runs in the user’s project)
PROJECT_ROOT="$(pwd)"
LOCK_FILE="$PROJECT_ROOT/mix.lock"
MIX_EXS="$PROJECT_ROOT/mix.exs"

# Flatten a file to one line with # comments stripped; sets FLAT. A dep tuple
# or alias list the formatter split across lines then parses like a one-liner.
flatten_source() {
  local line
  FLAT=""
  [[ -s "$1" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    FLAT+="${line%%#*} "
  done < "$1"
}

flatten_source "$MIX_EXS"
MIX_FLAT="$FLAT"

# True when mix.exs defines alias $1 and its task list runs a dep-fetching task,
# directly or through another alias (up to three levels deep).
alias_fetches_deps() {
  local name="$1" depth="$2" list item
  [[ "$depth" -lt 3 ]] || return 1
  local re="(^|[[:space:],[{])\"?${name//./\\.}\"?:[[:space:]]*\\[([^]]*)\\]"
  [[ $MIX_FLAT =~ $re ]] || return 1
  list=${BASH_REMATCH[2]}
  local re_item='"([a-z][a-z0-9_.]*)'
  while [[ $list =~ $re_item ]]; do
    item=${BASH_REMATCH[1]}
    list=${list#*"${BASH_REMATCH[0]}"}
    case "$item" in
      deps.get|deps.update|deps.compile|igniter.install) return 0 ;;
    esac
    [[ "$item" != "$name" ]] && alias_fetches_deps "$item" $((depth + 1)) && return 0
  done
  return 1
}

# The text after a task name, up to the next shell separator.
task_args() {
  local rest="${1%%[;&|]*}"
  printf '%s' "${rest%%$'\n'*}"
}

# Walk every `mix <task>` in the command. Sets FETCHES_DEPS, plus the arguments
# of a direct `mix deps.update` (branch-pin warning) and `mix igniter.install`
# (whose new dep isn’t in mix.exs until the command runs).
FETCHES_DEPS=false
DEPS_UPDATE=false
UPDATE_ARGS=""
IGNITER_ARGS=""
re_task='(^|[^[:alnum:]_.-])mix[[:space:]]+([a-z][a-z0-9_.]*)'
rest="$COMMAND"
while [[ $rest =~ $re_task ]]; do
  task=${BASH_REMATCH[2]}
  rest=${rest#*"${BASH_REMATCH[0]}"}
  case "$task" in
    deps.get|deps.compile) FETCHES_DEPS=true ;;
    deps.update)
      FETCHES_DEPS=true
      DEPS_UPDATE=true
      UPDATE_ARGS+=" $(task_args "$rest")"
      ;;
    igniter.install)
      FETCHES_DEPS=true
      IGNITER_ARGS+=" $(task_args "$rest")"
      ;;
    *) alias_fetches_deps "$task" 0 && FETCHES_DEPS=true ;;
  esac
done
$FETCHES_DEPS || exit 0

# Escape hatch
if [[ "${PHX_SKIP_DEPS_AUDIT:-}" == "1" ]]; then
  echo "phx-deps-audit: skipped (PHX_SKIP_DEPS_AUDIT=1)" >&2
  exit 0
fi

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
  local flat chunk name spec
  local re_name='^([a-z_0-9]+)'
  local re_src='(^|[[:space:],])(git|github|path):[[:space:]]*"([^"]*)"'
  local re_ref='(^|[[:space:],])(tag|ref|branch):[[:space:]]*"([^"]*)"'
  flatten_source "$1"
  flat="$FLAT"
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
  local mix_exs="$MIX_EXS"
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

# Rule 5 for `mix igniter.install name@git:URL | name@github:org/repo | name@path:DIR`.
# The dep isn’t in mix.exs until the command runs, so read it from the arguments.
# The pin is everything after the name, so a ref suffix makes a distinct pin.
tier1_rule5_igniter() {
  local word name spec rc=0
  local -a words
  local re='^([a-z_0-9]+)@(git|github|path):(.+)$'
  read -r -a words <<< "$IGNITER_ARGS"
  for word in "${words[@]+"${words[@]}"}"; do
    word=${word//\"/}
    word=${word//\'/}
    [[ $word =~ $re ]] || continue
    name=${BASH_REMATCH[1]}
    spec="${BASH_REMATCH[2]}:${BASH_REMATCH[3]}"
    ledger_vets_pin "$name" "$spec" && continue
    jq -cn --arg dep "$name" --arg pin "$spec" \
      '{rule_id: 5, severity: "warn", file: "igniter.install", message: "New non-Hex dep", dep: $dep, pin: $pin}' \
      >> "$tier1_findings_file"
    rc=1
  done
  return $rc
}

# The commit mix.lock holds for git dep $1 (first 12 chars), or nothing.
locked_git_sha() {
  local line re="\"$1\": \\{:git, \"[^\"]*\", \"([0-9a-f]+)\""
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ $line =~ $re ]]; then
      printf '%s' "${BASH_REMATCH[1]:0:12}"
      return 0
    fi
  done < "$LOCK_FILE"
}

# `mix deps.update` on a git dep pinned to a branch (or to nothing) pulls new
# commits without any mix.exs change, so rule 5 can’t see it and a vetted pin
# still matches. Warn, never block: name the locked commit to review from.
BRANCH_WARNINGS=()
collect_branch_warnings() {
  $DEPS_UPDATE || return 0
  local all=false arg name spec sha targets=" "
  local -a args
  read -r -a args <<< "$UPDATE_ARGS"
  for arg in "${args[@]+"${args[@]}"}"; do
    case "$arg" in
      --all) all=true ;;
      -*) ;;
      *) targets+="$arg " ;;
    esac
  done
  while read -r name spec; do
    [[ -n "$name" ]] || continue
    case "$spec" in git:*|github:*) ;; *) continue ;; esac
    case "$spec" in *@tag:*|*@ref:*) continue ;; esac
    $all || [[ "$targets" == *" $name "* ]] || continue
    sha=$(locked_git_sha "$name")
    BRANCH_WARNINGS+=("  $name ($spec) will move to the branch head${sha:+ from $sha}; vetting recorded the pin, not this code. After the update, review: git -C deps/$name log --oneline ${sha:-<locked-sha>}..HEAD")
  done < <(non_hex_dep_specs "$MIX_EXS")
}
collect_branch_warnings

branch_note=""
if [[ ${#BRANCH_WARNINGS[@]} -gt 0 ]]; then
  branch_note="phx-deps-audit: branch-pinned git deps will pull unreviewed commits:"
  for w in "${BRANCH_WARNINGS[@]}"; do
    branch_note+=$'\n'"$w"
  done
fi

# Allow the command, passing the branch-pin warning to Claude when there is one.
# PreToolUse stderr on exit 0 never reaches Claude; additionalContext does.
allow_with_note() {
  if [[ -n "$branch_note" ]]; then
    jq -cn --arg ctx "$branch_note" \
      '{hookSpecificOutput: {hookEventName: "PreToolUse", additionalContext: $ctx}}'
  fi
  exit 0
}

tier0_hit=false
tier0_cache_hit && tier0_hit=true

tier1_clean=true
if ! $tier0_hit; then
  tier1_rule1_bidi || tier1_clean=false
fi
tier1_rule5_git_path_deps || tier1_clean=false
tier1_rule5_igniter || tier1_clean=false

if $tier1_clean; then
  $tier0_hit && allow_with_note  # silent unless a branch pin moves
  # Soft hint, no block. The user can still opt into full audit explicitly.
  echo "phx-deps-audit: Tier 1 clean. Run /phx:deps-audit for full pipeline." >&2
  allow_with_note
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
  "            the user run the command themselves (prefix it with \`!\` in Claude Code). Do not retry."
)

print_block() {
  local headline="$1"
  printf '%s\n' "$headline" "  $findings_summary" >&2
  if [[ -n "$vet_hints" ]]; then
    printf '%s\n' "  Vet each new non-Hex dep (records its exact pin in hex_vet.exs):" "$vet_hints" >&2
  fi
  [[ -n "$policy_note" ]] && printf '%s\n' "$policy_note" >&2
  [[ -n "$branch_note" ]] && printf '%s\n' "$branch_note" >&2
  printf '%s\n' "${override_lines[@]}" >&2
}

case "$POLICY_MODE" in
  "false")
    printf '%s\n' \
      "phx-deps-audit: Tier 1 found risk signals (warn-only mode)." \
      "  $findings_summary" \
      "  Run /phx:deps-audit for full triage." >&2
    allow_with_note
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
    allow_with_note
    ;;

  ":strict"|":full")
    # Tier 2 invocation is intentionally NOT chained here — the hook budget is
    # already exceeded once we’re past Tier 1. :full mode runs Tier 2 via the
    # /phx:deps-audit skill body, not from the hook.
    print_block "phx-deps-audit: BLOCKED ($POLICY_MODE). Tier 1 found risk signals."
    exit 2
    ;;
esac

allow_with_note
