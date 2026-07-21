# Watcher Mechanics — Why Background Events Beat Polling

## The cost problem with hand-rolled loops

A foreground `while true; sleep 120; gh api ...` loop is the worst design
on both axes:

1. **Context burn** — every poll's `gh` JSON lands in the transcript.
   30 polls × full dumps = tens of KB of context for "nothing changed yet."
2. **Cache burn** — between-turn waits longer than the prompt-cache TTL
   (5 min default) force a full uncached context reload on the next turn:
   the ~35–55K-token prefix re-writes at 1.25×–2× instead of re-reading
   at 0.1×. A 300s interval lands exactly on the eviction boundary — the
   single worst choice. Under ~270s keeps the cache warm; anything longer
   should commit to 1200s+ so the reload price is paid once, not per poll.

The cheapest design pays the reload price ZERO times while idle: Claude
takes no turns at all between events. The script polls in its own process;
Claude's context is untouched until a real event arrives.

## Mechanism comparison

| Mechanism | Idle token cost | Notes |
|-----------|----------------|-------|
| Foreground bash loop | Worst — every poll in context | Reject |
| **Monitor tool** (v2.1.98+) | ≈0 — streams filtered event lines | **Preferred.** Purpose-built: background script, each stdout line returns as an event. Not available on Bedrock/Vertex/Foundry |
| Bash `run_in_background` | ≈0 — Claude re-invoked when the script exits | Portable fallback; one shot per launch (exit-on-first-terminal-event) |
| `/loop` + ScheduleWakeup | One full turn per wake (context reload each time) | Fallback only; clamped to [60s, 3600s]; Anthropic's own docs note dynamic /loop may switch to Monitor because it's cheaper |

Anthropic's scheduled-tasks doc states this directly: Monitor "avoids
polling altogether and is often more token-efficient and responsive than
re-running a prompt on an interval."

## Watcher contract (what watch-pr.sh implements)

- **Inputs**: PR number, dimensions (`reviews,comments,checks`), env
  overrides `WATCH_INTERVAL` (default 30s), `WATCH_MAX_DURATION` (3600s),
  `WATCH_BASELINE_TS`, `WATCH_DELTA_FILE`
- **One `gh pr view --json` per cycle** covers state, reviews, comments,
  and checks — cheaper than four REST calls, and the JSON never reaches
  Claude's context
- **Events**: one stdout line + one JSONL row in
  `.claude/watch/pr-{n}.jsonl` per genuinely-new item (dedup via seen-ID
  tracking, baseline timestamp filters out pre-existing reviews)
- **Terminal lines (silence ≠ success)**: `merged`, `pr_closed`,
  `watchdog` (max duration), `watch_error` (5 consecutive gh failures —
  don't loop forever on a dead token)

## Codex mode (`--codex`)

Verified against the ChatGPT Codex GitHub connector (2026-07-03,
reaction landing spots re-verified live 2026-07-10):

- **Trigger**: PR going ready auto-registers a review (codex reacts 👀 on
  the PR BODY — no comment needed), or comment `@codex review`. Pushing
  commits does NOT re-trigger — rounds after the first need a fresh
  trigger comment. The skill's preflight checks the PR body's bot
  reactions since the head commit and SKIPS posting when a review is
  already in flight (👀) or already clean (👍).
- **Signals**: 👀 reaction = codex acknowledged and is reviewing;
  👍 reaction = clean pass. A clean pass can ALSO arrive as a bot
  COMMENT — `Codex Review: Didn't find any major issues` with
  `Reviewed commit: {sha}` (confirmed live on a comment-triggered
  round); the watcher classifies it as `codex_clean`, and other bot
  comments containing "Codex Review" as `codex_review`. Auto-triggered
  reviews react on the PR body (confirmed live); comment-triggered
  rounds react on the trigger comment — the watcher polls both, with
  PR-level reactions time-filtered by `WATCH_CODEX_SINCE` so stale
  👀/👍 from earlier rounds or pushes can't fire spurious events.
- **Freshness anchor**: the `Reviewed commit: {sha}` marker beats every
  timestamp comparison — commit committer dates are client-set and skew
  (observed live: a clean comment predating its reviewed commit's
  committer date by 9 minutes). Compare shas when available; use
  reaction timestamps only as the in-flight heuristic.
- **Review arrival**: a PR review headed `### 💡 Codex Review` with
  `Reviewed commit: <sha>` — detected via body marker, not bot login
  (login differs per endpoint: `chatgpt-codex-connector[bot]` vs Bot type).
- **Latency**: 14–18 min per round on large PRs → `--codex` raises
  MAX_DURATION to 7200s. `codex_timeout` fires if no 👀 within 300s
  (`CODEX_ACK_TIMEOUT`) — the repo probably lacks the connector; the watch
  continues as a plain watch.
- **Round bookkeeping lives in the skill, not the script**: one watcher
  per round. After fixes are pushed, the skill posts a new `@codex review`,
  captures the new comment id, and restarts the watcher with
  `WATCH_CODEX_TRIGGER_ID=<new id>`. Rounds are capped (default 3) —
  each round consumes Codex cloud quota.
- **Env contract**: `WATCH_CODEX=1`; `WATCH_CODEX_TRIGGER_ID` (empty =
  auto-registered mode: PR-level reactions only); `WATCH_CODEX_SINCE`
  (ISO-8601 floor for PR-level reactions — head-commit time in
  auto-registered mode, defaults to watcher baseline otherwise);
  `CODEX_ACK_TIMEOUT` (default 300). At most two extra REST calls per
  30s tick (~240 req/hr) — still trivial against the 5,000/hr budget.

## Rate limits

30s cadence on a single PR is trivially within the 5,000 req/hr
authenticated budget. For multi-PR watching, the REST comments endpoint
supports conditional requests (`curl --etag-save/--etag-compare`) where
304 responses cost zero rate-limit points — GraphQL (`gh pr view`) does
not support ETags. Deferred until actually needed.

## CI-only watching

`gh pr checks {n} --watch --fail-fast --interval 10` already blocks until
all checks finish and exits with `0` = pass, `1` = fail, `8` = pending.
For "I just pushed, tell me when CI is green/red" there is nothing to
build — wrap it in `run_in_background` and the exit IS the signal.
`gh run watch {run-id}` is the equivalent for a single Actions run.
