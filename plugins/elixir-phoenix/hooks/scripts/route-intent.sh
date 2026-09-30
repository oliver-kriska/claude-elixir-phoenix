#!/usr/bin/env bash
# UserPromptSubmit hook: detect high-signal task intents and inject a one-line
# /phx: command suggestion into Claude’s context.
#
# Why a hook (not CLAUDE.md prose): session analysis of 400 sessions found
# CLAUDE.md routing rules fire ~0% of the time. UserPromptSubmit stdout IS
# injected into Claude’s context (one of two events with that property, the
# other being SessionStart), so detection here actually reaches the model.
#
# Conventions mirror block-dangerous-ops.sh / error-critic.sh:
#   - read stdin once, parse with jq, fail open (exit 0) on any miss
#   - gate Elixir-specific suggestions on mix.exs (cross-project bleed, PR #55)
#   - inject via hookSpecificOutput.additionalContext JSON
# No `set -e`: a non-zero from grep/jq must never erase the user’s prompt.
# NEVER exit 2 from this hook — for UserPromptSubmit that BLOCKS processing
# and erases the user’s prompt. Every path exits 0.

INPUT=$(cat)

# Parse prompt + session id. jq failure or empty prompt → fail open.
PROMPT=$(printf '%s' "$INPUT" | jq -r '.prompt // empty' 2>/dev/null)
[ -n "$PROMPT" ] || exit 0
SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // "nosession"' 2>/dev/null)

# Anti-annoyance #1: never fire on explicit slash commands. If the user already
# typed a command, they’ve routed themselves — stay silent.
case "$PROMPT" in
  /*) exit 0 ;;
esac

# Performance: only ever scan the first 4000 chars. Long pastes (stack traces,
# diffs) keep the relevant signal up front, and grep over a 50KB prompt on every
# keystroke-submit is wasted work. Truncation keeps the hook well under 100ms.
HEAD=$(printf '%s' "$PROMPT" | head -c 4000)

# Per-session, per-category dedup state. Keyed by session_id so a new session
# starts fresh. /tmp matches error-critic.sh’s failure-tracking convention.
STATE_DIR="/tmp/.claude-elixir-routing/${SESSION_ID}"

# already_fired CATEGORY → returns 0 (true) if we’ve already suggested it.
already_fired() {
  [ -f "${STATE_DIR}/$1" ]
}

# mark_fired CATEGORY → record that we’ve suggested it this session.
mark_fired() {
  mkdir -p "$STATE_DIR" 2>/dev/null || return 0
  : > "${STATE_DIR}/$1" 2>/dev/null || true
}

# emit HINT → inject one line into Claude’s context and exit. Only one
# suggestion per prompt (first match wins) to avoid stacking hints.
emit() {
  printf '%s' "$1" | jq -Rs \
    '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", additionalContext: .}}'
  exit 0
}

proj="${CLAUDE_PROJECT_DIR:-$PWD}"
is_elixir=0
[ -f "$proj/mix.exs" ] && is_elixir=1

# ── Category 1: PR review intent ──────────────────────────────────────────
# A GitHub PR URL, or explicit review-feedback phrasing. PR work isn’t
# Elixir-specific in principle, but /phx:pr-review is — gate on mix.exs.
# URL form: github.com/<owner>/<repo>/pull/<n>  (also matches /pulls/ rarely).
if [ "$is_elixir" = 1 ] && ! already_fired pr-review; then
  if printf '%s' "$HEAD" | grep -qiE 'github\.com/[^/[:space:]]+/[^/[:space:]]+/pull/[0-9]+' \
     || printf '%s' "$HEAD" | grep -qiE 'review (this|the|my) pr|pr (comments|feedback|review)|reviewer feedback|address .{0,20}review|code review'; then
    mark_fired pr-review
    emit "[plugin hint] This looks like PR review work — consider /phx:pr-review to fetch comments, draft replies, and resolve threads. (suggestion only)"
  fi
fi

# ── Category 2: Tidewave current-page UI-bug context ───────────────────────
# Tidewave injects <context name="current-page">…</context> describing the
# live page. Its presence on a prompt almost always means "this UI is broken".
if [ "$is_elixir" = 1 ] && ! already_fired investigate-ui; then
  if printf '%s' "$HEAD" | grep -qF '<context name="current-page">'; then
    mark_fired investigate-ui
    emit "[plugin hint] Tidewave page context detected — if something on this page is broken, /phx:investigate runs structured root-cause analysis. (suggestion only)"
  fi
fi

# ── Category 3: Elixir error / stack-trace paste ───────────────────────────
# Match canonical Elixir crash signatures. Require a real exception shape, not
# just the word "error", to avoid firing on "fix the error message copy".
#   ** (SomeError)            → raised exception banner
#   (elixir 1.x.y) / (stdlib  → frame attribution line
#   lib/foo.ex:42 / test/..exs:N (in a stacktrace frame)
if [ "$is_elixir" = 1 ] && ! already_fired investigate-error; then
  if printf '%s' "$HEAD" | grep -qE '\*\* \([A-Z][A-Za-z.]*(Error|Exception|ArgumentError|RuntimeError)\)' \
     || printf '%s' "$HEAD" | grep -qE '\*\* \([A-Z][A-Za-z.]+\) ' \
     || printf '%s' "$HEAD" | grep -qE '\((elixir|stdlib|ecto|phoenix|ex_unit) [0-9]' \
     || printf '%s' "$HEAD" | grep -qE '(lib|test)/[A-Za-z0-9_./-]+\.exs?:[0-9]+'; then
    mark_fired investigate-error
    emit "[plugin hint] Looks like a stack trace / error paste — /phx:investigate does structured root-cause analysis (add --parallel for deep dives). (suggestion only)"
  fi
fi

exit 0
