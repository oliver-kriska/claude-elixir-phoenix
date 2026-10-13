# Consult: Oban Specialist (background work for the Campfire port)

**Role**: consult only. This file does not plan or implement anything.
**Inputs**: ADR-000 (ASSUMED), runtime.md R-30..R-34 and Q3/Q5/Q6, mechanisms.md M-01/M-17..M-22/M-25/M-28 and Q3/Q4, contracts.md C-35..C-38, C-59/C-60, features.md F-08/F-15/F-21/F-24 and T-06/T-07/T-12, kb/sqlite-on-beam.md (Oban Lite caveats).
**Source read**: `app/jobs/*` (4 files), `app/models/webhook.rb`, `app/models/user/bot.rb`, `app/models/room.rb:48-85`, `app/models/room/message_pusher.rb`, `app/models/membership/connectable.rb`, `lib/web_push/pool.rb`, `config/initializers/web_push.rb`, `app/models/user/bannable.rb`, `app/models/message.rb`, `app/controllers/messages_controller.rb`.
**Verification note**: there were no Oban deps on disk to check against (no `deps/oban`). Statements about Oban internals are from Oban 2.2x documentation and behaviour as I know it. Any statement I could not check is marked **UNVERIFIED** and needs a spike before the ADR cites it.

---

## Legacy facts that drive the answers

| Fact | Anchor | Consequence for the port |
|------|--------|--------------------------|
| `ApplicationJob` has retries commented out, and Redis has `appendonly no` and `save ""` | `app/jobs/application_job.rb`, `config/redis.conf` | Every job today is **at-most-once and non-durable**. A restart drops the backlog. |
| The webhook trigger lives in the **controller** (`deliver_webhooks_to_bots`). Replies are created through `room.messages.create!` inside `Webhook` | `messages_controller.rb:25,79-85`, `webhook.rb:61-74` | Webhook replies **do** trigger unread and push (model `after_create_commit`) but **do not** trigger webhooks. The port needs an explicit flag on the create path. |
| Bot eligibility (mentionees or DM members) is computed at request time. The webhook URL and the payload (creator name, room name, body) are read when the job runs | `messages_controller.rb:84`, `webhook.rb:41-47` | Args carry `{bot_id, message_id}` only, and the payload is built at run time (MAP). |
| Unread marking is a synchronous `UPDATE` in after_commit, using `disconnected` presence **at commit**. Push recipients use `disconnected` presence **when the job runs** | `room.rb:48-50,79-84`, `message_pusher.rb:56-60` | This answers Q4: unread is sampled at commit, push at run. |
| Push builds one notification per subscription. Delivery uses a 50-thread pool with a 10k queue, and overflow is silently dropped. Expired subscriptions and OpenSSL errors destroy the row on a 1-thread pool | `pool.rb:6,25-50`, `web_push.rb:6-13` | Fan-out is in-process and best-effort. Dead-subscription cleanup is a side effect of delivery. |
| A ban enqueues `RemoveBannedContentJob` **inside** the ban transaction. The job destroys messages one by one and broadcasts each removal. It never checks whether the user is still banned | `bannable.rb:4-10,19-28,37-41` | The job is idempotent by construction: it re-queries the remaining messages. |
| `has_one_attached` defaults to `purge_later`, which is the implicit `ActiveStorage::PurgeJob` | runtime.md R-33 | This is the only implicit Active Storage job, because analysis is synchronous. |
| No cron or recurring work exists | runtime.md "Scheduled and Background Work" | No `Oban.Plugins.Cron` is needed. |

---

## Answers

### Q1. Is Oban Lite on the shared SQLite file sound for this workload? Queue layout and concurrency

**Yes, it is sound**, provided four disciplines hold. The workload is small: about 1 push job per message, plus k webhook jobs only when a bot is mentioned or in a DM, plus rare ban and purge jobs. It is dominated by outbound HTTP waits, not database work.

**What Oban Lite adds to the single writer (per job):**
- **Insert**: this rides inside the message transaction that already holds the writer, so the extra cost is one `INSERT`.
- **Fetch**: one short writer transaction per producer poll. It is batched up to the queue's free demand, so a burst amortizes it.
- **Ack** (`completed` / `cancelled` / `discarded`): one short `UPDATE` per job. **UNVERIFIED**: whether 2.24 batches acks under Lite. Assume one write per job.
- **Background writes**: Stager, Pruner and Lifeline write periodically.

Under a chat burst of N messages/s, that is about 2N extra short writer transactions, each well under a millisecond. Those sit behind request writes in the DBConnection queue for the single writer (`pool_size: 1`). Inside one BEAM, Oban never meets `busy_timeout` (kb rule 12). It meets `queue_target: 500` / `queue_interval: 2000` instead. If the writer queue stays saturated, DBConnection drops checkouts. Oban's producer and stager then log errors and retry on their next tick. That is self-healing, but it will show up in Sentry. **Measure it in the chat-burst baseline** (ADR-000 Performance Goal).

**The four disciplines:**
1. **Use the writer Repo for Oban and keep `oban_jobs` in the same file.** This is what makes the M-01 enqueue atomic (kb: "Same database file").
2. **No HTTP, file IO or media work inside a writer transaction.** Workers do I/O first or after, then open short transactions. Webhook attachment replies must upload the blob file **before** the message transaction (kb rule 9).
3. **Long data jobs must chunk.** Ban removal must delete in batches of about 100 messages per transaction, never one transaction for a whole user's history. Otherwise one ban stalls every chat write for seconds.
4. **Keep queue limits modest.** The limits bound the number of *processes* that can ask for the writer, not database throughput. I/O-bound queues spend most of their time off the writer.

**Queue layout:**

| Queue | Limit | Workload | Why |
|-------|-------|----------|-----|
| `webhooks` | 10 | Outbound POST to bot endpoints, up to 7 s open + 7 s read, then one reply-message transaction | I/O-bound. 10 means one slow bot (or ten) cannot block all others for long. Raise it if bots are common. |
| `push` | 3 | One fan-out job per message, with bounded internal concurrency (Q4) | Each job runs `Task.async_stream` with `max_concurrency: 25`, so 3 × 25 = 75 concurrent push requests. That is above legacy's 50 threads, and pushes need little memory. |
| `maintenance` | 1 | Ban content removal, blob purge | Serializing these keeps bulk deletes from piling onto the writer. Ordering does not matter. |

- **C-60 queue sizing**: ADR-000 says limits "derive from CPU count". For these I/O-bound queues, CPU count is the wrong input. I recommend fixed defaults with an optional override, `JOB_CONCURRENCY` → `webhooks` limit, which gives that legacy env var a meaning again (C-60).
- **Plugins**:
  - `Oban.Plugins.Pruner` with `max_age: 86_400` (1 day) and `limit: 1_000`. A smaller limit keeps each prune transaction short on the writer.
  - `Oban.Plugins.Lifeline` with `rescue_after: :timer.minutes(15)`. It must exceed the longest job `timeout/1` (ban removal, 10 min).
  - No Cron and no Reindexer (the Reindexer is Postgres-oriented).
- **Other config**:
  - `shutdown_grace_period` should be below the container stop timeout (docker default 10 s), so about 8 s.
  - Keep the Lite engine defaults: `Notifiers.PG` and `Peers.Isolated`, so the node is always the leader.
  - Replacement cutover means no two releases ever share the file, so the lack of leader election (kb) is harmless. Never run two containers on one volume.
- **Latency**: job pickup latency is bounded by the stager and producer cadence, normally sub-second and at worst about 1 s. **UNVERIFIED**: whether the PG notifier wakes producers immediately for jobs inserted inside a transaction. F-15 and F-24 say "within seconds", so either way is acceptable. Measure it.

### Q2. Delivery semantics: at-most-once webhooks, durable push, and restored backups

**Webhooks: stay at-most-once (C-35 "once, no retry"; R-30; mechanisms Q3).**

1. **Use `max_attempts: 1`.** Any `{:error, _}`, raise or timeout then discards the job instead of retrying it, so the bot's reply can never be posted twice by a retry.
2. **Crash mid-flight.** A node crash or a stop beyond the grace period leaves the job `executing`. Lifeline later rescues it. Because `attempt >= max_attempts`, Lifeline **discards** it instead of making it `available`, so it is never re-POSTed. **UNVERIFIED** detail: confirm this Lifeline branch in 2.24 source during the spike. The fallback is an explicit `attempt > 1 -> {:cancel, :no_retry}` guard at the top of `perform/1`.
3. **Return values match C-36:**

   | Outcome | Return |
   |---------|--------|
   | 200 text reply | post the text message, `:ok` |
   | Reply whose content type maps to a known MIME (any status, T-06 preserved) | post the attachment message, `:ok` |
   | Open or read timeout | post "Failed to respond within 7 seconds", `:ok` |
   | Other error (connection refused, TLS) | `{:cancel, reason}`: no message, logged |
   | Bot gone, webhook removed, or message deleted before the run | `{:cancel, :gone}` (legacy raised and dropped) |

4. **Idempotency key: not needed** at `max_attempts: 1`, and adding a header would break byte-compatibility (C-35 "no signature"). If retries are ever approved (runtime Q5), they need a new delivery-id header and a recorded-reply check. That is a contract change and needs its own ADR.
5. **Loop prevention (T-07 preserved)**: the reply path calls `Chat.create_message(..., deliver_webhooks: false)`. That keeps push and unread for replies, as legacy does, but never enqueues a webhook. API posts by bots pass `true`, matching legacy, so bot↔bot API loops stay possible.

**Push: make the *enqueue* durable but keep *delivery* at-most-once. This is my recommendation for T-12, which stays "preserve" plus a free upgrade.**

- The fan-out job is in `oban_jobs` from the moment the message commits, so a restart before it runs no longer loses it. That upgrade costs nothing and has no duplicate risk.
- Run it with `max_attempts: 1`. Once delivery has started, a retry of the whole fan-out would re-notify every device that already got it. Duplicate notifications are a user-visible regression compared with today.
- A fully durable per-subscription delivery (T-12 "strengthen") is possible (see Q4). It costs about 2 writer writes per device per message and adds retry duplicates whenever a push service accepted the message but the response was lost.
- If T-12 is approved as "strengthen", do it per subscription with `max_attempts: 3` and send a Web Push `Topic` header (for example `m<message_id>`, at most 32 base64url chars). That header lets the push service collapse an undelivered duplicate. It is an HTTP header, not part of the payload, so C-37 is untouched. **UNVERIFIED**: support for collapsing by Topic differs between FCM, Mozilla, Apple and WNS.

**Restored backups (runtime Q3, kb "Backups"):**

A `prepare-backup` snapshot (`VACUUM INTO` or the backup API) now contains `oban_jobs` in every state. After `post-restore`, they become as follows:

| State in the snapshot | After restore | Risk |
|-----------------------|---------------|------|
| `available` / `scheduled` | Run on boot | A webhook re-POST and duplicate bot reply, a push for an old message |
| `executing` | Lifeline rescues it after 15 min. With `max_attempts: 1` it is discarded; idempotent maintenance jobs re-run | None for webhook and push. Maintenance re-runs are safe. |
| `retryable` | Only maintenance jobs can be in this state | Safe, because they are idempotent |
| `completed` / `cancelled` / `discarded` | Pruned | None |

**Recommendation**: use a **staleness guard in the workers** instead of a restore-time SQL purge.
- `WebhookDelivery` and `PushFanout` return `{:cancel, :stale}` when `now - job.inserted_at > 10 minutes` (configurable).
- This one rule covers a restore, a long outage, and a backlog after a crash.
- It approximates legacy, where any restart dropped volatile work.
- It needs no `sqlite3` CLI in the image and no change to the `post-restore` hook, which ONCE runs with the app stopped.
- Ban removal and blob purge **should** replay after a restore, since they are idempotent and converge to the right state. So a blanket purge of `oban_jobs` in the hook would be wrong.
- The cutoff is a new (ASSUMED) behaviour and must be recorded in the delivery ADR.

**Rollback to the Rails image** uses the pre-upgrade backup, which has no `oban_jobs` table. Even when Rails boots on a port-written file, Rails ignores the table. Pending jobs are simply lost, which equals legacy semantics. `oban_jobs` is an additive table, consistent with ADR-000 Data.

### Q3. M-01 side effects in the message transaction, and when presence is sampled

**Yes. Insert the jobs in the same writer transaction as the message.** Either a function-based `Repo.transact/2` calling `Oban.insert/2` inside, or `Ecto.Multi` with `Oban.insert(multi, name, changeset)`, works. Both join the transaction because Oban's repo is the same writer Repo, checked out by the same process. The transaction contains, in order:

1. `INSERT` the message, the rich text body, the attachment rows (blob already uploaded), and the FTS row (C-09).
2. Touch the room (C-13).
3. **Unread marking as a plain `UPDATE`, not a job**: `memberships.visible.disconnected.where.not(user: creator)` → `unread_at = message.created_at`. It is one statement, it is legacy-synchronous, and doing it in the transaction makes C-13 atomic.
4. `Oban.insert` for **one** `PushFanout` job with `%{message_id}`.
5. If `deliver_webhooks: true`: one `WebhookDelivery` per eligible bot with `%{bot_id, message_id}`. Eligibility is computed from mentionees or DM members **at commit**, as legacy does in the controller.

After commit come the PubSub broadcasts (message create, unread room) through the Action Cable shim. This closes the legacy crash windows: commit then crash before `receive`, and "Redis down" causing a 500 for a saved message (M-01).

**Presence sampling (mechanisms Q4): keep the legacy split.**
- **Unread** is sampled at commit, inside the transaction, from `memberships.connected_at` (or from whatever Q6 decides).
- **Push recipients** are sampled **at job run**.
  - The job usually runs within about a second, so the difference from commit-time sampling is negligible.
  - Run-time sampling is *more* correct for a delayed job: a user who opened the room in the meantime gets no stale push.
  - It keeps args tiny, which matters because a recipient list in args would be large (Iron Law 6).
  - The badge is each user's unread count at run time. Compute it with one grouped query, not one query per subscription.
- If Q6 moves presence to in-memory `Phoenix.Presence`, run-time sampling still works on a single node. The job reads it from the same BEAM.

**Unique constraints on these inserts**: none. Each job is inserted exactly once, by the transaction that creates its message, and that atomicity is the guarantee. A Lite unique check would add a `SELECT` over `oban_jobs` args **inside the hot writer transaction**. **UNVERIFIED**: there is likely no index on `args` under SQLite. Double-click duplicates are a message-creation concern (`client_message_id`), not a job concern.

### Q4. Push fan-out: per-subscription jobs vs `Task.async_stream` in one job

**Recommendation: one `PushFanout` job per message, with a bounded `Task.async_stream` inside.**

| | One job + `async_stream` | Per-subscription jobs |
|---|---|---|
| Writer cost per message | about 3 writes (insert in the message transaction, fetch, ack), plus one batched invalidation delete | about 2 writes per device (fetch and ack), plus `insert_all` |
| Matches legacy semantics | Yes (at-most-once, in-process concurrency like the 50-thread pool) | No (durable per device, retries) |
| Burst behaviour | Bounded by `push` limit × `max_concurrency` | Can flood `oban_jobs` and the writer (a 200-member room means 400+ writes per message) |
| Partial failure | Logged per subscription, never retried | Retried per device (risk of duplicate notifications) |

The per-subscription option only makes sense if T-12 is explicitly approved as "strengthen", and even then only for rooms below some size. I would not do it.

**Job shape:**
1. If the message is missing, or the stale guard trips → `{:cancel, reason}`.
2. Query recipients on the reader Repo: visible, disconnected, not the creator, `everything` plus mentioned `mentions` users (C-37). Join subscriptions and compute badge counts per user.
3. Build the payload once per message, then encrypt per subscription.
4. Run `Task.async_stream(subs, &deliver/1, max_concurrency: 25, timeout: 10_000, on_timeout: :kill_task, ordered: false)` under a `Task.Supervisor`.
5. In `deliver/1`: check the endpoint allow-list again, resolve DNS **at delivery**, reject private IPs, and connect pinned to the resolved IP with SNI and hostname verification for the real host (C-38). That means a one-off Mint connection per delivery, mirroring legacy, which bypasses the persistent pool for pinned requests.
6. Collect the ids of subscriptions that returned 404/410 (expired) or a TLS or crypto error. After the stream, run **one** `delete_all where id in ^ids` on the writer.
   - **UNVERIFIED (check `push/subscription.rb`)**: whether `Push::Subscription` has destroy callbacks that this delete would skip. Legacy uses `destroy`.
7. Return `:ok`, even if some deliveries failed. They are not retried (at-most-once).

**Dead-subscription cleanup** stays reactive, as in legacy: removal happens only on a delivery error. No sweeper job is needed, and none exists today.

### Q5. Banned-content removal and the Active Storage purge job

**`RemoveBannedContent`:**
- **Insert**: in the **ban transaction** (atomic, like legacy's in-transaction enqueue but now durable). The transaction also creates the bans, deletes the sessions and sets the status. The socket disconnect is broadcast after commit.
- **Args**: `%{"user_id" => id}`.
- **Unique**: on `user_id` across incomplete states with `period: :infinity`, so double-clicking Ban or ban→unban→ban never stacks jobs. **UNVERIFIED**: the state-group name `:incomplete` exists in Oban ≥2.20. Otherwise list `[:available, :scheduled, :executing, :retryable]`.
- **Perform**: loop until no messages remain.
  1. Read up to 100 message ids where `creator_id = user_id`, inside the batch transaction on the writer.
  2. In **one short transaction per batch**, delete boosts, rich text, attachment rows and FTS rows, then the messages, and touch the rooms (C-13, `belongs_to :room, touch: true`). For each attachment blob, `Oban.insert` a `PurgeBlob` job in the same transaction. Children go first because `foreign_keys = ON` (mechanisms note 6).
  3. After each commit, broadcast the removals for that batch.
- **Retries**: idempotent, because it always re-queries what is left. Use `max_attempts: 10` and the default backoff.
- **Timeout**: `timeout/1` of 10 min, below Lifeline's `rescue_after`.
- **Preserve legacy**: it does **not** check whether the user is still banned (an unban before the run still deletes). Flag this as part of T-04 if the product wants otherwise.
- **Privacy bonus**: because args carry only ids, deleted message text never lingers in `oban_jobs` (Iron Law 6).

**`PurgeBlob` (replaces `ActiveStorage::PurgeJob`):**
- **Insert**: in the same transaction that deletes the owning attachment row. That covers message destroy, avatar or logo replace/remove, and ban removal.
- **Args**: `%{"blob_id" => id, "key" => blob.key}`. Carrying `key` lets a retry find the file even after the row is gone.
- **Perform, files first, then rows** (both steps idempotent):
  1. If any *other* attachment still references the blob → `:ok`. This is a safety check legacy lacks, and it is cheap.
  2. Delete the variant files, then the blob file under `storage/files/<k[0..1]>/<k[2..3]>/<key>` (C-11 layout). Treat `:enoent` as success.
  3. In one short transaction, delete `variant_records`, the variant blobs and attachments, then the blob row.
  4. If the row is already gone → `:ok`.

  A crash between steps 2 and 3 leaves rows without files for an already-deleted message. Only an old signed blob URL (C-27) could reach them, and it 404s either way. The retry finishes the cleanup.
- **Retries**: `max_attempts: 5`.
- **No unique**: the args are naturally distinct, and a duplicate is harmless.

---

## Risks

| # | Risk | Likelihood / impact | Mitigation |
|---|------|---------------------|------------|
| R1 | Writer contention: Oban fetch, ack and prune writes queue behind request writes during a chat burst. DBConnection `queue_interval` drops checkouts → Oban errors in Sentry, and push latency rises | med / med | Keep limits modest, use Pruner `limit: 1_000`, measure checkout queue time with jobs on in the slice-0 baseline, and add telemetry on `[:oban, :job, :stop]` queue time. kb "When to Move to Postgres" sets the exit criteria. |
| R2 | One long writer transaction in a job (ban removal of a prolific user) stalls every chat write and trips `busy_timeout` / `queue_target` | high if unchunked / high | Batches of 100 per transaction, with broadcasts after commit. Code review rule: no unbounded `delete_all` on messages. |
| R3 | Webhook re-delivery through Lifeline rescue, or a restore replay → duplicate bot replies (C-35/C-36 break) | low with mitigations / high | `max_attempts: 1`, plus an explicit `attempt > 1 -> cancel` guard, plus the 10-min stale guard. Test: insert an `executing` webhook job, run Lifeline, assert it is discarded and no POST is made. |
| R4 | Webhook reply processing holds the writer during blob upload or analysis | med / med | Upload and analyze outside the transaction, then insert the message in a short transaction. |
| R5 | The reply path accidentally enqueues webhooks (a new bot loop, beyond the T-07 API loop) | med / high | Explicit `deliver_webhooks:` option with no default (required keyword). Test from F-24's negative probe. |
| R6 | Retries of a durable push duplicate notifications (if T-12 "strengthen" is chosen) | med / low-med | Keep `max_attempts: 1` for the fan-out, or use per-subscription jobs with a `Topic` header (UNVERIFIED vendor support). |
| R7 | The stale-job cutoff (10 min) is a new behaviour: a webhook delayed by a long backlog is silently dropped | low / low | Record it as ASSUMED in the delivery ADR. Log `{:cancel, :stale}` at info level. |
| R8 | A job timeout above Lifeline `rescue_after` → a still-running job gets rescued and runs twice (ban removal is idempotent, but duplicate broadcasts are possible) | low / low | Invariant: every `timeout/1` is below `rescue_after` (10 min < 15 min). Assert it in a config test. |
| R9 | `oban_jobs` grows inside backups and the main file (VACUUM, WAL churn) | low / low | Pruner with a 1-day max age. Jobs carry ids only. |
| R10 | Library claims marked UNVERIFIED (Lite ack batching, PG-notifier wake inside a transaction, Lifeline discard branch, `:incomplete` state group, unique-check cost) | — | A one-day spike against Oban 2.24.1 source before the ADR is accepted. |

---

## Recommendations

### Worker list

| Worker | Queue | max_attempts | unique | Args (string keys on read) | timeout/1 | Return mapping |
|--------|-------|--------------|--------|----------------------------|-----------|----------------|
| `Campfire.Bots.WebhookDelivery` | `webhooks` | **1** | none (inserted once in the message transaction) | `%{"bot_id" => int, "message_id" => int}` | 30 s (7 s open + 7 s read + reply transaction; Mint's receive timeout is per-recv like Net::HTTP, so a slow-drip body can exceed 14 s) | reply/timeout-message → `:ok`; missing bot, webhook or message → `{:cancel, :gone}`; `attempt > 1` → `{:cancel, :no_retry}`; stale > 10 min → `{:cancel, :stale}`; transport error → `{:cancel, reason}` |
| `Campfire.Push.Fanout` | `push` | **1** (T-12 preserve; durable enqueue) | none | `%{"message_id" => int}` | 60 s | `:ok` after `async_stream` (per-device failures logged and invalid subscriptions batch-deleted); missing message or stale → `{:cancel, _}` |
| `Campfire.Push.Delivery` *(only if T-12 = strengthen)* | `push` | 3 | `[keys: ["message_id", "subscription_id"], period: :infinity]` | `%{"message_id" => int, "subscription_id" => int}` | 15 s | 2xx → `:ok`; 404/410/TLS → delete subscription, `{:cancel, :expired}`; 429/5xx → `{:error, _}` (retry); add a `Topic` header |
| `Campfire.Moderation.RemoveBannedContent` | `maintenance` | 10 | `[keys: ["user_id"], period: :infinity, states: :incomplete]` (UNVERIFIED group name) | `%{"user_id" => int}` | 10 min | `:ok` when no messages remain; DB error → `{:error, _}` (retry is safe) |
| `Campfire.Storage.PurgeBlob` | `maintenance` | 5 | none | `%{"blob_id" => int, "key" => string}` | 2 min | blob still attached elsewhere → `:ok`; files then rows deleted → `:ok`; IO error other than `:enoent` → `{:error, _}` |

### Oban config sketch

```elixir
config :campfire, Oban,
  engine: Oban.Engines.Lite,
  repo: Campfire.Repo,                 # writer, pool_size: 1
  queues: [webhooks: 10, push: 3, maintenance: 1],
  shutdown_grace_period: 8_000,
  plugins: [
    {Oban.Plugins.Pruner, max_age: 86_400, limit: 1_000},
    {Oban.Plugins.Lifeline, rescue_after: :timer.minutes(15)}
  ]
```

### Rules for the plan

1. `Chat.create_message/3` is the only message-insert path. It requires a `deliver_webhooks:` keyword. The transaction holds the message, FTS, room touch, unread `UPDATE`, `Push.Fanout` insert and webhook inserts. Broadcasts come after commit.
2. All job args are ids or blob keys only: never payloads, bodies, URLs or recipient lists.
3. Workers read through `Repo.reader()`, write in short writer transactions, and never do HTTP or file IO inside a transaction.
4. Webhook and push workers carry the stale guard (config `:job_stale_after`, default 10 min). Maintenance workers do not.
5. Tests:
   - `testing: :manual`, with `assert_enqueued` inside the message transaction.
   - A rollback test: a failed message insert leaves no job.
   - A Lifeline test: an `executing` webhook job ends `discarded` with no POST.
   - A restore test: a 1-hour-old `available` webhook job is cancelled as stale.
   - A loop test: a reply creates no webhook job.
   - Ban removal of more than 250 messages runs in batches, and its broadcasts are emitted.
6. Telemetry: attach `[:oban, :job, :exception]` to the Sentry handler (SENTRY_DSN / SKIP_TELEMETRY), and track queue time per queue in the performance gate.
7. Before ADR acceptance: a spike to resolve the UNVERIFIED items (R10) against the pinned Oban version.
