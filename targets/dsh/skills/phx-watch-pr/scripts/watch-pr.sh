#!/usr/bin/env bash
# watch-pr.sh — quiet GitHub PR watcher. Emits ONE line per genuinely-new event.
# Designed for the Monitor tool / run_in_background. stdout = event stream.
# Exits (terminal line first) on: PR closed/merged, max duration, or repeated
# gh failures. Silence is never success — every terminal state emits a line.
set -uo pipefail

PR="${1:?usage: watch-pr.sh <pr-number> [reviews,comments,checks]}"
WATCH="${2:-reviews,comments,checks}"
INTERVAL="${WATCH_INTERVAL:-30}"
MAX_DURATION="${WATCH_MAX_DURATION:-3600}"
# Anchor to the project root, not cwd — relative .claude/ paths create stray
# state dirs when the script runs from elsewhere (same bug class as the
# cc-changelog nested-state-dir incident).
DELTA_FILE="${WATCH_DELTA_FILE:-${CLAUDE_PROJECT_DIR:-$PWD}/.claude/watch/pr-${PR}.jsonl}"
mkdir -p "$(dirname "$DELTA_FILE")"

START_EPOCH=$(date -u +%s)
BASELINE_TS="${WATCH_BASELINE_TS:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
FAIL_COUNT=0

emit() { # emit <json-line>  -> stdout event + append to delta file
  printf '%s\n' "$1"
  printf '%s\n' "$1" >> "$DELTA_FILE"
}
has() { case ",$WATCH," in *",$1,"*) return 0;; *) return 1;; esac; }

# Track what we've already reported (ids / conclusions) to avoid dupes.
SEEN_REVIEWS=""; SEEN_COMMENTS=""; LAST_CHECK_STATE=""

# Codex mode (WATCH_CODEX=1): poll the bot's reactions — 👀 = acknowledged,
# 👍 = clean pass (codex posts NO review when it has nothing to flag) — and
# tag the bot's reviews as codex_review. Two sub-modes:
#   WATCH_CODEX_TRIGGER_ID set   → skill posted "@codex review"; poll that
#                                  comment (+ PR body, time-filtered).
#   WATCH_CODEX_TRIGGER_ID empty → codex auto-registered on PR-ready (👀 on
#                                  the PR body); poll PR-level only.
# WATCH_CODEX_SINCE (ISO-8601, default watcher baseline) filters PR-level
# reactions — stale 👀/👍 from earlier rounds or pushes must not fire events.
# One watcher per codex round: the skill restarts us per re-request.
CODEX_ACKED=""; CODEX_CLEAN=""; CODEX_TIMEOUT_EMITTED=""
CODEX_ACK_TIMEOUT="${CODEX_ACK_TIMEOUT:-300}"
CODEX_SINCE="${WATCH_CODEX_SINCE:-$BASELINE_TS}"
codex_on() { [[ "${WATCH_CODEX:-0}" == "1" ]]; }

while :; do
  NOW_EPOCH=$(date -u +%s)
  if (( NOW_EPOCH - START_EPOCH >= MAX_DURATION )); then
    emit "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"kind\":\"watchdog\",\"summary\":\"stopped after ${MAX_DURATION}s\"}"
    exit 0
  fi

  # One cheap call covers state, reviews, comments, checks. || true keeps us alive.
  VIEW=$(gh pr view "$PR" \
    --json state,mergedAt,reviews,comments,statusCheckRollup,updatedAt 2>/dev/null) || true
  if [[ -z "$VIEW" ]]; then
    FAIL_COUNT=$((FAIL_COUNT+1))
    if (( FAIL_COUNT >= 5 )); then
      emit "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"kind\":\"watch_error\",\"summary\":\"5 consecutive gh failures\"}"
      exit 1
    fi
    sleep "$INTERVAL"; continue
  fi
  FAIL_COUNT=0

  STATE=$(jq -r '.state' <<<"$VIEW")

  # --- reviews (bot + human) newer than baseline, not yet seen ---
  if has reviews; then
    while IFS=$'\t' read -r rid author rstate submitted is_codex; do
      [[ -z "$rid" ]] && continue
      [[ "$submitted" > "$BASELINE_TS" ]] || continue
      case " $SEEN_REVIEWS " in *" $rid "*) continue;; esac
      SEEN_REVIEWS="$SEEN_REVIEWS $rid"
      RKIND="review"
      # Match the body marker, not the bot login — login differs per endpoint.
      if codex_on && [[ "$is_codex" == "true" ]]; then RKIND="codex_review"; fi
      emit "{\"ts\":\"$submitted\",\"kind\":\"$RKIND\",\"author\":\"$author\",\"state\":\"$rstate\"}"
    done < <(jq -r '.reviews[] | [(.id|tostring), .author.login, .state, .submittedAt, ((.body // "") | contains("Codex Review") | tostring)] | @tsv' <<<"$VIEW")
  fi

  # --- comments newer than baseline, not yet seen ---
  if has comments; then
    while IFS=$'\t' read -r cid author created bodyhead; do
      [[ -z "$cid" ]] && continue
      [[ "$created" > "$BASELINE_TS" ]] || continue
      case " $SEEN_COMMENTS " in *" $cid "*) continue;; esac
      SEEN_COMMENTS="$SEEN_COMMENTS $cid"
      CKIND="comment"
      # A codex clean pass can arrive as a bot COMMENT ("Codex Review:
      # Didn't find any major issues" + Reviewed commit sha) — seen live.
      if codex_on && [[ "$bodyhead" == *"Codex Review"* ]]; then
        if [[ "$bodyhead" == *"find any major issues"* ]]; then
          CKIND="codex_clean"; CODEX_CLEAN=1
        else
          CKIND="codex_review"
        fi
      fi
      emit "{\"ts\":\"$created\",\"kind\":\"$CKIND\",\"author\":\"$author\"}"
    done < <(jq -r '.comments[] | [(.id|tostring), (.author.login // "unknown"), .createdAt, ((.body // "") | gsub("[\n\r\t]"; " ") | .[0:160])] | @tsv' <<<"$VIEW")
  fi

  # --- codex mode: bot reactions (👀 ack / 👍 clean) ---
  if codex_on; then
    REACTS=""
    if [[ -n "${WATCH_CODEX_TRIGGER_ID:-}" ]]; then
      REACTS=$(gh api "repos/{owner}/{repo}/issues/comments/${WATCH_CODEX_TRIGGER_ID}/reactions" \
        --jq '[.[].content] | unique | join(",")' 2>/dev/null) || REACTS=""
    fi
    # Auto-triggered (PR-ready) reviews react on the PR body — confirmed live
    # on EnaiaInc/enaia. Time-filter so stale reactions can't fire.
    # gh's --jq takes no --arg — bind $since via standalone jq instead.
    # shellcheck disable=SC2016  # $since is a jq --arg variable, not shell
    PR_REACTS=$(gh api "repos/{owner}/{repo}/issues/${PR}/reactions" 2>/dev/null \
      | jq -r --arg since "$CODEX_SINCE" \
          '[.[] | select(.created_at >= $since) | .content] | unique | join(",")' 2>/dev/null) || PR_REACTS=""
    ALL_REACTS="${REACTS},${PR_REACTS}"
    if [[ -z "$CODEX_ACKED" && "$ALL_REACTS" == *eyes* ]]; then
      CODEX_ACKED=1
      emit "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"kind\":\"codex_ack\",\"summary\":\"codex acknowledged the review request (eyes reaction)\"}"
    fi
    if [[ -z "$CODEX_CLEAN" && "$ALL_REACTS" == *"+1"* ]]; then
      CODEX_CLEAN=1
      emit "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"kind\":\"codex_clean\",\"summary\":\"codex reacted +1 — clean pass, no review will be posted\"}"
    fi
    if [[ -z "$CODEX_ACKED" && -z "$CODEX_TIMEOUT_EMITTED" ]] && (( NOW_EPOCH - START_EPOCH >= CODEX_ACK_TIMEOUT )); then
      CODEX_TIMEOUT_EMITTED=1
      emit "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"kind\":\"codex_timeout\",\"summary\":\"no ack after ${CODEX_ACK_TIMEOUT}s — repo may lack the Codex connector; continuing normal watch\"}"
    fi
  fi

  # --- checks: emit on terminal conclusion change ---
  if has checks; then
    CHECK=$(jq -r '
      (.statusCheckRollup // [])
      | {pending: ([.[] | select((.status // .state) != "COMPLETED" and (.conclusion // "") == "")] | length),
         failure: ([.[] | select((.conclusion // .state) == "FAILURE" or (.conclusion // "") == "FAILURE")] | length),
         total:   (length)}
      | "pending=\(.pending) failure=\(.failure) total=\(.total)"' <<<"$VIEW")
    if [[ "$CHECK" != "$LAST_CHECK_STATE" ]]; then
      LAST_CHECK_STATE="$CHECK"
      PENDING=$(sed -n 's/.*pending=\([0-9]*\).*/\1/p' <<<"$CHECK")
      FAILS=$(sed -n 's/.*failure=\([0-9]*\).*/\1/p' <<<"$CHECK")
      if [[ "${PENDING:-1}" == "0" ]]; then
        CONC=$([[ "${FAILS:-0}" == "0" ]] && echo success || echo failure)
        emit "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"kind\":\"check\",\"conclusion\":\"$CONC\",\"summary\":\"$CHECK\"}"
      fi
    fi
  fi

  # --- terminal: PR no longer open ---
  if [[ "$STATE" != "OPEN" ]]; then
    KIND=$([[ "$STATE" == "MERGED" ]] && echo merged || echo pr_closed)
    emit "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"kind\":\"$KIND\",\"state\":\"$STATE\"}"
    exit 0
  fi

  sleep "$INTERVAL"
done
