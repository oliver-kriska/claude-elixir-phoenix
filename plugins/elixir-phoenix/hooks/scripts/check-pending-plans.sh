#!/usr/bin/env bash
# Stop hook: surface session-created risks the user might forget on exit.
#
# Output model (CC hooks ref): a Stop hook’s plain stdout goes to the debug log
# ONLY — it is never shown in the transcript. The two ways to reach anyone are:
#   - hookSpecificOutput.additionalContext / exit 2  → feeds Claude and CONTINUES
#     the turn. Wrong here: it would force Claude to keep working on every stop.
#   - JSON `systemMessage`                           → shown to the USER; Claude
#     still stops normally. Correct for an advisory reminder.
#
# Stop fires once per turn, so we gate the systemMessage on the RARE,
# session-created signals — running background_tasks[] and session_crons[]
# (added to Stop input in CC 2.1.145). A forgotten `mix phx.server` / `iex` /
# scheduled job is exactly what SessionStart can’t know about. Pending plans and
# an uncommitted working tree are already surfaced by the SessionStart resume
# (check-resume.sh) and branch-freshness (check-branch-freshness.sh) hooks, so we
# only fold them in as supporting context WHEN a background signal is present —
# keeping the common (clean) stop completely silent, no per-turn noise.
INPUT=$(cat)
if [ "$(echo "$INPUT" | jq -r '.stop_hook_active' 2>/dev/null)" = "true" ]; then
  exit 0
fi

BG_COUNT=$(echo "$INPUT" | jq -r '(.background_tasks // []) | length' 2>/dev/null)
CRON_COUNT=$(echo "$INPUT" | jq -r '(.session_crons // []) | length' 2>/dev/null)
[[ "$BG_COUNT" =~ ^[0-9]+$ ]] || BG_COUNT=0
[[ "$CRON_COUNT" =~ ^[0-9]+$ ]] || CRON_COUNT=0

# Common path: nothing session-created to surface → stay silent (no git/grep spawn).
if (( BG_COUNT == 0 && CRON_COUNT == 0 )); then
  exit 0
fi

warnings=()
(( BG_COUNT > 0 )) && warnings+=("$BG_COUNT background task(s) still running — stop them or detach explicitly")
(( CRON_COUNT > 0 )) && warnings+=("$CRON_COUNT session cron(s) scheduled — see /schedule list")

# Supporting context (only computed once a background signal fired).
PENDING=$(grep -rl '\[ \]' .claude/plans/*/plan.md 2>/dev/null | wc -l | tr -d ' ')
[[ "$PENDING" =~ ^[0-9]+$ ]] && (( PENDING > 0 )) && warnings+=("$PENDING plan(s) have uncompleted tasks")

# Lost-work guard: uncommitted changes on a feature branch are one rebase away
# from being gone (session-analysis 2026-06-11).
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
if [[ -n "$BRANCH" && "$BRANCH" != "main" && "$BRANCH" != "master" && "$BRANCH" != "HEAD" ]]; then
  DIRTY=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  [[ "$DIRTY" =~ ^[0-9]+$ ]] && (( DIRTY > 0 )) && \
    warnings+=("$DIRTY uncommitted change(s) on ‘$BRANCH’ — commit or stash before switching/rebasing")
fi

MSG="⚠ Before you leave:"
for w in "${warnings[@]}"; do
  MSG+=$'\n  • '"$w"
done

jq -nc --arg msg "$MSG" '{systemMessage: $msg}'
exit 0
