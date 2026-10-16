# ADR-006: Background jobs on Oban Lite; delivery semantics; 10-minute stale cancel

**Status**: ASSUMED (auto; needs approval). New behavior recorded as DV-02 and DV-03. Revises ADR-000's C-60 wording (queue limits).
**Date**: 2026-10-09

## Context

- Legacy jobs run on Resque over a non-persistent Redis (`appendonly no`, `save ""`), with no retries (`ApplicationJob` retries commented out). Every job is at-most-once and lost on restart (M-25, R-24, C-59).
- Push fan-out runs in an in-memory 50-thread pool with a 10k queue, and overflow is silently dropped (M-22, R-09).
- Webhooks: "once, no retry" (C-35). A retry could post a duplicate bot reply (C-36).
- T-12 (push durability) is triaged `preserve` (ASSUMED).

## Decision

**Engine and placement.** Oban 2.24 with `Oban.Engines.Lite` on the writer `Campfire.Repo`, `oban_jobs` in the same SQLite file (atomic enqueue). Defaults: `Oban.Notifiers.PG` (Erlang process groups, **not** PostgreSQL) and `Oban.Peers.Isolated`. Never two containers on one volume.

**Queues.** `webhooks: 10`, `push: 3`, `maintenance: 1`. `JOB_CONCURRENCY`, if set, overrides the `webhooks` limit. This replaces ADR-000's "limits derive from CPU count": the queues are I/O-bound, so CPU count is the wrong input.

**Plugins.** `Oban.Plugins.Pruner` (`max_age: 86_400`, `limit: 1_000`) and `Oban.Plugins.Lifeline` (`rescue_after: 15 min`). No Cron, because no recurring work exists. `shutdown_grace_period` is about 8 s, below Docker's 10 s stop.

**Workers.** Args carry ids and blob keys only.

| Worker | Queue | max_attempts | Unique | Semantics |
|---|---|---|---|---|
| `Bots.WebhookDelivery` `%{bot_id, message_id}` | webhooks | **1** | none | At-most-once POST. Guards: `attempt > 1 → {:cancel, :no_retry}` (Lifeline-rescue safety); **stale > 10 min → `{:cancel, :stale}`**. Timeout → "Failed to respond within 7 seconds"; reply → `Chat.create_message(..., deliver_webhooks: false)` |
| `Push.Fanout` `%{message_id}` | push | **1** | none | Durable enqueue, at-most-once delivery. Recipients and badge sampled at run time. **Stale > 10 min → cancel.** Bounded `Task.Supervisor.async_stream_nolink` (`max_concurrency: 25`); dead subscriptions batch-deleted after the stream |
| `Moderation.RemoveBannedContent` `%{user_id}` | maintenance | 10 | `user_id`, incomplete states, `period: :infinity` | Idempotent; batches of 100 messages per short transaction; broadcasts per batch; no ban re-check (legacy parity) |
| `Files.PurgeBlob` `%{blob_id, key}` | maintenance | 5 | none | Files first, then rows; `:enoent` is success; skips blobs still attached elsewhere |

`timeout/1` per worker stays below Lifeline's `rescue_after` (10 min max).

**Restore.** A backup now contains `oban_jobs`. After a restore, the stale guard cancels old webhook and push jobs; maintenance jobs replay because they are idempotent. The `post-restore` hook stays unchanged. A rollback to Rails ignores `oban_jobs`; pending jobs are lost there, which equals legacy semantics.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| Webhook: at most one POST per (bot, message) | kept | bot endpoints (C-35, C-36) |
| Push: at most one notification per device per message | kept | push users (C-37) |
| Job **enqueue** survives restart and crash | **changed (strengthened)**: legacy lost the backlog on any restart (DV-02) | bots, push users |
| No silent overflow drop of push | **changed**: backlog waits in `oban_jobs`, bounded by the stale guard (DV-02) | push users |
| Jobs older than 10 min at pickup are dropped | **new behavior** (DV-03). Approximates legacy, where restarts dropped volatile work | bots after outages; restores |
| Ban content removal completes even across crashes | **changed (strengthened)**: retried and idempotent (DV-13) | admins, viewers |
| Pickup latency "within seconds" (F-15, F-24) | kept, **unmeasured**: producer wake-up for jobs inserted in a transaction is UNVERIFIED | push users, bots |

## Alternatives

- Webhook retries with a delivery-id header. Rejected: breaks byte-compatibility (C-35 "no signature") and duplicates replies. Needs its own ADR.
- Per-subscription push jobs with retries (T-12 "strengthen"). Not adopted: about 2 writer writes per device per message, and duplicate notifications on lost acks. Available behind a later ADR.
- No stale guard and a restore-time purge in `post-restore`. Rejected: needs the sqlite3 CLI in the image, and it would wrongly drop the idempotent maintenance jobs.
- Stale cutoff as config only, default off. Rejected: then a restore replays hour-old webhooks into live rooms.

## Consequences

- Every job fetch, ack and prune is a writer write shared with requests. Writer checkout queue time and Oban queue time become performance-gate metrics.
- A one-day spike against Oban 2.24.1 source must settle the UNVERIFIED items: Lite ack batching, PG-notifier wake inside a transaction, Lifeline discard at `max_attempts`, the `:incomplete` unique state group, unique-check cost on SQLite.

## Validation

- Lifeline test: an `executing` webhook job ends `discarded`, with no POST.
- Restore test: a 1-hour-old `available` webhook job is cancelled as stale; a maintenance job replays.
- Rollback test: a failed message transaction leaves no job.
- Ban removal of more than 250 messages runs in batches and emits every removal broadcast.
- Config test: every worker timeout < `rescue_after`.

## Ledger IDs

M-17, M-20, M-21, M-22, M-25, R-08, R-09, R-24, R-30, R-31, R-32, R-33, C-35, C-36, C-37, C-59, C-60
