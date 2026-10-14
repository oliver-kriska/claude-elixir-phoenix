#!/usr/bin/env bash
# PreToolUse hook: block dangerous Bash operations before execution.
# Emits permissionDecision: "deny" via JSON output and includes
# `additionalContext` so the safer alternative survives into Claude’s next
# turn (CC 2.1.110+ preserves additionalContext on blocked tool calls).
#
# Elixir-specific branches self-gate on mix.exs presence (see PR #55,
# "gate hooks on mix.exs to fix cross-project bleed"). The git force-push
# block is intentionally global and stays ungated.
#
# FAIL-OPEN CONTRACT: every intentional deny goes through emit_block (JSON
# permissionDecision + exit 0). Never add a deny path that relies on a
# non-zero exit code. A syntax error makes bash exit 2, the blocking exit
# code (a copy with merge-conflict markers once blocked every Bash call), so
# test_hook_scripts_parse keeps syntax errors and conflict markers out. The
# script must not re-run itself (`bash -n <path>`) or look programs up with
# `command -v`: the plugin directory blocks a script that runs another path.

if ! jq --version >/dev/null 2>&1; then
  printf '%s\n' \
    'elixir-phoenix safety hook disabled: jq is unavailable (failing open).' >&2
  exit 0
fi

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$TOOL" == "Bash" ]] || exit 0

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
[[ -n "$COMMAND" ]] || exit 0

proj="${CLAUDE_PROJECT_DIR:-$PWD}"
is_elixir=0
[ -f "$proj/mix.exs" ] && is_elixir=1

# emit_block CONTEXT REASON_LINE... joins the reason lines with newlines.
emit_block() {
  local ctx="$1" reason
  shift
  printf -v reason '%s\n' "$@"
  reason=${reason%$'\n'}
  jq -nc --arg reason "$reason" --arg ctx "$ctx" \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason, additionalContext: $ctx}}'
  exit 0
}

# Elixir-only: destructive Ecto operations.
# Anchored on start-of-line or shell command separators (;, &, |, &&, ||) so a
# quoted mention inside `echo "do not run mix ecto.reset"` doesn’t trigger.
# Tolerates an optional `env` and env-var assignment prefix run
# (`MIX_ENV=test mix ecto.reset`), `mix do ecto.drop`, and multiple spaces —
# a plain word like `echo` is not an assignment, so quoted mentions stay safe.
# Trailing class requires `reset`/`drop` to be followed by whitespace, comma
# (`mix do ecto.drop, ecto.create`), separator, `)`, or end-of-command —
# preserving sibling tasks like `mix ecto.gen.migration`.
# See ANCHOR NOTE below the force-push pattern for `^[[:space:](]*`.
if [[ "$is_elixir" == 1 ]] && echo "$COMMAND" | grep -qE '(^[[:space:](]*|[;&|]+[[:space:]]*)(env[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)*mix[[:space:]]+(do[[:space:]]+)?ecto\.(reset|drop)([[:space:];&|,)]|$)'; then
  emit_block \
    "The user’s previous Bash call (‘mix ecto.reset’ / ‘mix ecto.drop’) was blocked by the elixir-phoenix plugin to prevent data loss. Prefer ‘mix ecto.rollback --step 1’ to undo the last migration, ‘mix ecto.migrate’ to apply pending ones, or author a corrective migration with ‘mix ecto.gen.migration NAME’. Do not retry the reset/drop unless the user explicitly asks again." \
    "BLOCKED: Destructive database operation detected." \
    "mix ecto.reset/drop will destroy all data. If intentional, run manually" \
    "outside Claude Code. Safer alternatives:" \
    "- mix ecto.rollback --step 1 (undo last migration)" \
    "- mix ecto.migrate (apply pending migrations)"
fi

# Global: force-push (intentionally not gated on mix.exs).
#
# Issue #61: the previous pattern `git push.*(--force|-f)\b` matched
# `--force-with-lease` — in ERE, `\b` is a boundary between word (`e`) and
# non-word (`-`), so `--force-` triggered the boundary and the whole flag
# matched. It also scanned past `&&`/`;`/`|` and tripped on quoted strings
# elsewhere on the line. This anchored pattern fixes both:
#
#   - `(^[[:space:](]*|[;&|]+[[:space:]]*)` — start-of-line or after a shell
#     command separator. Plain whitespace is NOT an anchor mid-line, so
#     `echo "git push --force"` no longer matches (`git push` is preceded by a
#     space inside the quote, not a separator).
#   - `[^;|&]*[[:space:]]` — scan stays within the current command, so a later
#     `&& gh ... --force-with-lease` on the same line is out of scope.
#   - `(--force|-f)([[:space:];&|)]|$)` — the flag must end at a word terminator
#     (whitespace, separator, `)`, or end-of-command). `--force-with-lease` ends
#     in `-`, which is not a terminator, so it is allowed; `--force` and `-f` as
#     real flags are still blocked.
#
# ANCHOR NOTE (CC 2.1.223 class of bug, fixed here 2026-08-10). The
# start-of-line alternative was a bare `^`, which permitted NO leading
# whitespace — so `\tmix ecto.drop`, `  git push --force`, and
# `(MIX_ENV=prod mix release)` all executed while evading every deny. Claude
# Code fixed the same padding-hides-the-command hole in its own permission
# prompts in 2.1.223. `^[[:space:](]*` now absorbs leading whitespace and
# subshell parens.
#
# `(` is deliberately NOT added to the separator class `[;&|]`. Doing so would
# make `echo "(git push --force)"` match, reintroducing the quoted-mention
# false positive that issue #61 fixed. Only the start-of-line branch is widened.
#
# Invisible Unicode padding (U+00A0 et al) is intentionally out of scope: the
# shell would treat ` mix` as a command named ` mix`, which does not
# execute, so it is not an evasion path.
if echo "$COMMAND" | grep -qE '(^[[:space:](]*|[;&|]+[[:space:]]*)git push[^;|&]*[[:space:]](--force|-f)([[:space:];&|)]|$)'; then
  emit_block \
    "The user’s previous ‘git push --force’ / ‘git push -f’ was blocked by the elixir-phoenix plugin. Use ‘git push --force-with-lease’ which refuses to clobber unseen commits. Only the user should run an unguarded force-push (via ‘!’ prefix in their terminal). Do not retry." \
    "BLOCKED: Force push detected — this rewrites remote history." \
    "If intentional, run manually outside Claude Code." \
    "Safer alternative: git push --force-with-lease"
fi

[[ "$is_elixir" == 1 ]] || exit 0

# Everything below is Elixir-only. Each pattern is checked against the command
# and against the lines of any local script the command runs, so a denied step
# cannot hide in `scripts/x.sh`.
#
# START is the anchor from the ANCHOR NOTE above: start of a line (after
# whitespace or subshell parens) or a shell separator. A quoted mention such
# as `echo "pkill -f beam"` therefore never matches.
START='(^[[:space:](]*|[;&|]+[[:space:]]*)'
ASSIGNS='(env[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)*'
RUNNER='(sudo[[:space:]]+)?([^[:space:];&|()]*/)?'

# Pattern kills of BEAM processes. pkill/killall (and kill fed by pgrep) match
# every process on the machine, so `pkill -f beam` also stops the user’s own
# servers, IEx shells and ElixirLS. A name matches as a whole word, case-
# insensitively: `perl` does not match `erl`, `beam.smp` and `Elixir.App` do.
# Plain `kill PID`, `kill -0 PID` and `kill %1` never match.
KILL_ARGS='[[:space:]]([^;&|]*[^[:alnum:]_;&|])?'
BEAM_NAMES='(beam|beam[.]smp|erl|erlang|epmd|elixir|iex|mix|phx[.]server)([^[:alnum:]_]|$)'
WORD_END='([[:space:]]|$)'
KILL_PATTERN="${START}${RUNNER}(pkill|killall)${KILL_ARGS}${BEAM_NAMES}"
KILL_PGREP="${START}${RUNNER}kill[[:space:]][^;&|]*[$][(][[:space:]]*pgrep${KILL_ARGS}${BEAM_NAMES}"
PGREP_XARGS="${START}pgrep${KILL_ARGS}${BEAM_NAMES}([^;&|]*[|])?[[:space:]]*xargs[[:space:]]([^;&|]*[[:space:]])?kill${WORD_END}"

# MIX_ENV=prod is for building a release. PROD_STEP captures each command
# that sets it, up to the next separator; prod_step_allowed decides.
PROD_STEP="${START}${ASSIGNS}MIX_ENV=prod([[:space:]]+[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*)*[[:space:]]+[^;&|)]*"
LEAD_ASSIGN='^[[:space:]]+[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*'
MIX_WORD='^[[:space:]]+mix([[:space:]]|$)'
IEX_WORD='^[[:space:]]+iex([[:space:]]|$)'
DO_WORD='^[[:space:]]*do([[:space:]]|$)'
FIRST_WORD='^[[:space:]]*([^[:space:]]+)'
ONLY_PROD='[[:space:]]--only[[:space:]=]+prod([[:space:]]|$)'
STEP_TEXT='MIX_ENV=prod.*[^[:space:]]'

# Local scripts the command runs: `bash|sh|zsh|source|. FILE`, `./FILE`,
# `../FILE` and `DIR/FILE.sh`. The file path is the last word of each match.
SCRIPT_RUN="${START}${ASSIGNS}(([^[:space:];&|()<>]*/)?(bash|sh|zsh|source|[.])([[:space:]]+-[-A-Za-z]+)*[[:space:]]+[^[:space:];&|()<>-][^[:space:];&|()<>]*|[.][.]?/[^[:space:];&|()<>]+|[^[:space:];&|()<>=]*/[^[:space:];&|()<>/]*[.]sh)"

# prod_task_allowed TASK_AND_ARGS: succeeds for a build-only mix task.
prod_task_allowed() {
  [[ $1 =~ $FIRST_WORD ]] || return 1
  case "${BASH_REMATCH[1]}" in
    release | compile | deps.compile | assets.deploy | phx.digest) return 0 ;;
    deps.get) [[ $1 =~ $ONLY_PROD ]] ;;
    *) return 1 ;;
  esac
}

# prod_step_allowed SEGMENT: succeeds unless SEGMENT runs iex, or a mix task
# outside the build allowlist, under MIX_ENV=prod. `mix do` passes only when
# every task in it does. Other programs (`MIX_ENV=prod make`) pass.
prod_step_allowed() {
  local rest=${1#*MIX_ENV=prod} list
  while [[ $rest =~ $LEAD_ASSIGN ]]; do
    rest=${rest:${#BASH_REMATCH[0]}}
  done
  [[ $rest =~ $IEX_WORD ]] && return 1
  [[ $rest =~ $MIX_WORD ]] || return 0
  rest=${rest:${#BASH_REMATCH[0]}}
  if [[ $rest =~ $DO_WORD ]]; then
    list=${rest:${#BASH_REMATCH[0]}}
    list=${list//+/,}
    while :; do
      prod_task_allowed "${list%%,*}" || return 1
      [[ $list == *,* ]] || return 0
      list=${list#*,}
    done
  fi
  prod_task_allowed "$rest"
}

# prod_violation: reads shell text on stdin and prints LINE:SEGMENT for the
# first MIX_ENV=prod step that is not allowed.
prod_violation() {
  local hit
  grep -nIoE "$PROD_STEP" | while IFS= read -r hit; do
    if ! prod_step_allowed "${hit#*:}"; then
      printf '%s\n' "$hit"
      break
    fi
  done
}

# block_beam_kill WHERE: WHERE is empty or names the script and line.
block_beam_kill() {
  emit_block \
    "The previous Bash call was blocked by the elixir-phoenix plugin: it runs a pattern kill naming a BEAM process$1 (‘pkill -f beam’, ‘pkill -f phx.server’, ‘killall beam.smp’, or ‘kill’ fed by ‘pgrep’). A pattern kill stops every matching process on the machine, including the user’s own Phoenix servers, IEx shells and ElixirLS. Stop only the process you started, by PID: start it in the background, record its PID with ‘pid=\$!’ right after, and stop it with ‘kill \$pid’. If you started it as a background task, stop that task instead. When the kill sits in a script, change the script the same way. Do not retry the pattern kill." \
    "BLOCKED: pattern kill of BEAM processes$1." \
    "pkill/killall, or kill fed by pgrep, naming beam, erl, epmd, elixir," \
    "iex, mix or phx.server stops every matching process on the machine," \
    "including the user’s other servers, IEx shells and ElixirLS." \
    "Stop only the process you started, by PID:" \
    "- start it in the background and record pid=\$! right after" \
    "- stop it with kill \$pid (kill -0 \$pid checks it is still running)"
}

# block_prod_step STEP WHERE
block_prod_step() {
  emit_block \
    "The previous Bash call was blocked by the elixir-phoenix plugin: it runs ‘$1’$2. Under MIX_ENV=prod only build steps are allowed: ‘mix release’, ‘mix compile’, ‘mix deps.compile’, ‘mix assets.deploy’, ‘mix phx.digest’ and ‘mix deps.get --only prod’. Every other mix task, and ‘iex -S mix’, runs the app or its code with production config and is denied. Run it under MIX_ENV=dev or MIX_ENV=test, or ask the user to run it outside Claude Code. Do not retry it under MIX_ENV=prod, and do not move it into a script: the scripts a command runs are checked too." \
    "BLOCKED: $1$2." \
    "MIX_ENV=prod is allowed only for build steps:" \
    "- mix release, mix compile, mix deps.compile" \
    "- mix assets.deploy, mix phx.digest, mix deps.get --only prod" \
    "Every other mix task under MIX_ENV=prod, and iex, is denied: it runs" \
    "the app or its code with production config (mix ecto.migrate," \
    "mix run, mix phx.server, iex -S mix). If intentional, run it" \
    "manually outside Claude Code."
}

# step_text SEGMENT: the step from MIX_ENV=prod on, for the deny message.
step_text() {
  if [[ $1 =~ $STEP_TEXT ]]; then
    printf '%s' "${BASH_REMATCH[0]}"
  else
    printf '%s' "$1"
  fi
}

if [[ $COMMAND == *kill* || $COMMAND == *pgrep* ]] &&
  printf '%s\n' "$COMMAND" | grep -qiE -e "$KILL_PATTERN" -e "$KILL_PGREP" -e "$PGREP_XARGS"; then
  block_beam_kill ""
fi

if [[ $COMMAND == *MIX_ENV=prod* ]]; then
  hit=$(printf '%s\n' "$COMMAND" | prod_violation)
  [[ -n "$hit" ]] && block_prod_step "$(step_text "${hit#*:}")" ""
fi

# Scripts: a file that does not exist or cannot be read is skipped (fail
# open). Relative paths resolve against the hook input cwd.
runs=$(printf '%s\n' "$COMMAND" | grep -oE "$SCRIPT_RUN")
[[ -n "$runs" ]] || exit 0
cwd=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
[[ -n "$cwd" ]] || cwd=$proj

while IFS= read -r run; do
  path=${run##*[[:space:]]}
  path=${path##*[;&|(]}
  case "$path" in
    /*) file=$path ;;
    *) file="$cwd/$path" ;;
  esac
  [[ -f "$file" && -r "$file" ]] || continue
  hit=$(grep -m 1 -nIiE -e "$KILL_PATTERN" -e "$KILL_PGREP" -e "$PGREP_XARGS" "$file" 2>/dev/null)
  [[ -n "$hit" ]] && block_beam_kill " in $path, line ${hit%%:*}"
  hit=$(prod_violation < "$file" 2>/dev/null)
  [[ -n "$hit" ]] && block_prod_step "$(step_text "${hit#*:}")" " in $path, line ${hit%%:*}"
done <<< "$runs"

exit 0
