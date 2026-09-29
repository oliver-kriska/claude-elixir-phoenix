---
name: watch-pr
description: Watch an Elixir/Phoenix PR with an Amp Orb keep-alive lease until required non-deployment CI is green and review threads are resolved. Use after opening or updating a PR.
effort: medium
argument-hint: <PR number or URL> [--checks-only] [--fix] [--max-hours N] [--quiet-minutes N]
---

# Watch PR — Amp-Native Lifecycle

Use the `elixir_phoenix_watch_pr` plugin tool. Do not launch `gh pr checks
--watch`, `gh run watch`, a foreground sleep loop, or the copied Claude watcher
script: none of those owns an Amp Orb keep-alive lease.

## Iron Laws

1. **Acquire one bounded keep-alive lease** — start the plugin lifecycle once,
   then let its durable state and dedupe handle polling and plugin reloads.
2. **Deployment is never readiness** — deployment, release, preview,
   production, and prod checks are reported under `excludedChecks`; they are
   never counted as passing or failing required CI.
3. **Never merge or deploy** — watching and `--fix` authorize neither action.
4. **`--fix` uses the same worker thread** — the plugin serializes one concise
   event turn at a time and directs that turn to the installed `phx-pr-review`
   workflow for actionable review feedback or failed required CI. Validate the
   cause before editing.
5. **Every watch is bounded** — timeout and every other terminal path release
   the lease. A timeout is incomplete, never success.

## Start

Parse the PR number/URL and flags, then call:

```text
elixir_phoenix_watch_pr {
  "action": "start",
  "pr": "<number-or-url>",
  "checksOnly": false,
  "fix": false
}
```

Map `--checks-only` and `--fix` to booleans. Map `--max-hours`,
`--quiet-minutes`, and `--poll-seconds` to `maxDurationHours`,
`quietPeriodMinutes`, and `pollIntervalSeconds`. Defaults are 2 hours maximum,
15 minutes quiet, and 60 seconds polling. Report the tool's initial snapshot
and then stop taking turns; the plugin wakes this thread only for actionable
failures or feedback and terminal outcomes.

## Event Handling

- Unchanged snapshots do not wake the model.
- A changed head SHA resets readiness but does not itself wake the model.
- Failed or cancelled required non-deployment CI wakes the model once per
  distinct actionable snapshot. Pending and passing progress keeps polling
  inference-silent.
- Excluded deployment-like checks appear separately in explicit status and
  terminal summaries. Their transitions do not reset readiness or wake the
  model.
- Any unresolved review thread keeps the lease active.
- A head push, required-check transition, review, or comment resets the quiet
  clock. This includes a review with no unresolved thread or dedicated check,
  but routine non-actionable activity does not wake the model.
- With `--fix`, unresolved feedback explicitly loads `phx-pr-review`; required
  CI failures include check names and links. Re-fetch threads or inspect logs,
  fix only valid branch-owned causes, verify, push the authorized PR branch
  update, reply, and resolve where appropriate. Do not blindly rerun shared CI.
- Required CI must remain green with zero unresolved threads and no relevant
  activity for the full quiet period before success releases the lease. Never
  accept an early green snapshot as immediate readiness.

## Status and Stop

Use the same tool with `"action": "status"` or `"action": "stop"`. Stop is
idempotent and releases the lease; it does not delete durable history.

## Post-Completion Boundary

The plugin registers an optional durable Amp webhook and stores its bearer URL
in the owner-only credential file reported by the tool. If a repository
administrator configures GitHub to send PR review/check events to that URL, a
later event can wake the paused Orb and probe the authoritative PR state.
Webhook events must identify the exact watched PR number or current watched
head SHA; empty or unrelated repository events are ignored.

The plugin never changes GitHub webhook settings. Without that external setup,
polling ends after the quiet period and a later human comment cannot wake a
paused Orb. Say this explicitly; do not imply polling continues after lease
release.

## Reference

- `references/watcher-mechanics.md` — lease, durability, filtering, webhook,
  and billing behavior
