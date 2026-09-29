# Amp Watcher Mechanics

## Lifecycle

The generated plugin owns the lifecycle rather than a shell process:

```text
start → validate PR → acquire keep-alive → persist snapshot → poll quietly
  ├─ required CI/reviews pending ───────────────────────────────┐
  ├─ actionable failure/feedback → deduplicated event/fix turn ──┤
  ├─ routine progress/activity → reset quiet, no model turn ─────┤
  ├─ ready → 15-minute activity quiet window → release → success│
  ├─ timeout/API error/closed/manual stop → release → incomplete│
  └─ plugin reload → release old lease → recover state/lease ───┘
```

Amp's normal inactivity pause is about five minutes. The default 15-minute
quiet period covers delayed check-backed and account-level reviews while the
lease—not an active model turn—keeps the Orb awake. A 60-second poll is
responsive without paying for model inference on unchanged state. The 2-hour
cap covers normal CI/review latency while limiting one HIGH worker to two
Orb-hours; raise it only when a known slow pipeline justifies the added cost.

All three values are configurable per watch within bounded ranges:

| Setting | Default | Range | Tradeoff |
| --- | ---: | ---: | --- |
| Poll interval | 60 seconds | 30–300 seconds | Faster response versus more GitHub API traffic |
| Quiet period | 15 minutes | 5–60 minutes | Catch delayed reviews versus extra Orb runtime after readiness |
| Active duration | 2 hours | 0.5–24 hours | Slow-pipeline reliability versus a hard billing ceiling |

## Durable and Idempotent Processing

Workspace Amp configuration stores watch identity, bound thread ID, options,
deadline, latest head SHA, normalized check/thread snapshot hashes, pending fix
event hash, and recent webhook IDs. Reload recovery reacquires a lease only for
an active, unexpired watch. Amp dispose releases all process-owned leases;
process exit also ends them server-side.

Snapshot and fix markers are written into appended user messages. Before an
append, the plugin scans recent full-thread messages for the marker. This makes
the append idempotent across a crash between the thread side effect and the
configuration update. `--fix` has one in-memory turn runner per PR, while its
pending and in-flight hashes remain durable. Failed or cancelled required CI
and unresolved threads share one actionable hash, so unchanged failures do not
queue duplicate turns and new evidence waits for the current turn to finish.

## Readiness Contract

`gh pr checks --required --json` is the source of required checks. Older GitHub
CLI versions fall back to its non-interactive tabular output. Buckets `pass`
and `skipping` are green; `pending`, `fail`, and `cancel` are not.

Names and workflows matching deployment, deployments, deploy, release,
preview, production, or prod are removed from readiness and retained in a
separate excluded list. Optional non-deployment checks are not promoted to
required checks. A draft PR is not ready. Every unresolved GitHub review
thread—including outdated but unresolved threads—is actionable until the
`phx-pr-review` turn validates and resolves or rejects it.

Do not treat the first green snapshot as ready. For example, Enaia starts
`Static checks`, `Design-system lifecycle`, `check_gettext`,
`migration_check`, `check_dialyzer`, `test`, `Integration tests`,
`Playwright E2E tests`, `Codex PR Review`, and aggregate `All checks`, while an
account-level Codex review may arrive later without its own check. Each current
head SHA change, required-check transition, review-thread change, top-level PR
comment, and submitted review resets the 15-minute quiet clock. Jobs such as
`deploy_branch`, `deploy_staging`, `draft_release`, and `tag_version` remain
excluded and do not reset it.

Polling and stabilization do not imply a model turn. Pending/passing required
check transitions, head pushes, submitted reviews without an unresolved
thread, and top-level comments reset the quiet clock but remain
inference-silent. Deployment-like transitions are even quieter: they are
persisted and reported by explicit status and terminal summaries, but neither
reset the clock nor append a message. Only failed/cancelled required checks,
unresolved threads, and terminal outcomes wake the model.

With `--fix`, actionable evidence is appended to the same serialized worker
thread with check names/links and unresolved-thread details. The turn may
inspect logs, fix branch-owned causes, verify, and push the authorized branch;
it must not blindly rerun shared CI, merge, or deploy. Without `--fix`, the
same evidence is reported once for inspection rather than repaired.

Review-thread GraphQL pagination is bounded at 1,000 threads. Exceeding that
bound or receiving malformed/incomplete API data is a polling error, never a
false green result. Five consecutive polling errors terminate incomplete and
release the lease.

## Durable Webhook Reactivation

`amp.createWebhook` registers a stable capability URL for the Orb thread and
plugin. The URL is a bearer secret: it is written under
`~/.config/amp/phx-watch-pr/` with owner-only permissions, never logged or put
in a normal thread message. Payloads only select a repository plus an exact
watched PR number or current watched head SHA; events that identify neither and
unrelated status/check events are ignored. All evidence is re-fetched through
authenticated `gh` calls and payload text is never used as agent instructions.

Webhook delivery is at least once, so Amp event IDs are retained and snapshot
markers deduplicate effects. A successful dormant watch reacts only to GitHub
check/status/PR/review events. It acquires a lease and probes for two minutes to
allow GitHub eventual consistency. No relevant change returns immediately to
dormant success; changed CI, head, or review state starts a fresh bounded
active window.

Creating the GitHub repository webhook requires shared administration
permission, so the plugin never does it automatically. Without external
configuration, the 15-minute quiet window is the final opportunity to catch a
comment before the Orb becomes eligible to pause.
