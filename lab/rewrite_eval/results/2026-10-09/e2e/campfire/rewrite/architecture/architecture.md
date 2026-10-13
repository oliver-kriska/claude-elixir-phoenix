# Architecture — ONCE Campfire on Elixir/Phoenix

- **Source**: reference @ `90b330024dec` (Rails 8.2.0.alpha, read-only, never executed)
- **Bar**: ADR-000, Status **ASSUMED** (`--auto`). Replacement cutover, keep schema, keep sessions, keep the Hotwire UI and every wire and operator contract, retire Redis/Resque. Nothing here is approved.
- **Written**: 2026-10-09 by `/rewrite:architect --auto`. Inputs: charter, analysis (69 mechanisms, 25 runtime rows, 57 contracts), four consults, KB.
- **Claims**: none. No code exists in TARGET and nothing has run. Every ledger row is `pending` / `not-run`.

## 1. Overview

**Shape**: single-node web appliance (ADR-001). It is a single-tenant, server-rendered chat app with realtime fan-out, in-process background work and an operator CLI, shipped as one container over one SQLite file (C-50, C-52). `kb/app-shapes.md` is missing from the KB, so the shape was classified from the inventory and features.

**Framework defaults** apply: Phoenix 1.8 controllers and HEEx on Bandit, Ecto on ecto_sqlite3, Oban (Lite engine), Phoenix.PubSub. The bar adds three edge constraints:

1. The bundled Hotwire/Stimulus JS stays unchanged. So `/cable` speaks Action Cable through an isolated SHIM (ADR-008), and LiveView is not used.
2. Rails-format crypto at the edge: the session cookie and signed capabilities (ADR-010, ADR-011).
3. Rails' own migration ledger stays authoritative for Rails versions (ADR-004).

Core contexts never see Turbo, Cable or Rails formats.

**What changes underneath**:

| Legacy | Elixir |
|---|---|
| Redis (cable pub/sub, cache, rate limit, Resque) | PubSub, nothing, Hammer, Oban Lite |
| Resque at-most-once, volatile | Oban, enqueued in the domain transaction; at-most-once kept where the contract says so |
| DB presence counters | in-memory Registry |
| after-commit callback chains | one transaction per write intent |
| `bin/boot` + Puma + resque-pool | one release under `tini` → `thrust` |

## 2. Context Map

Contexts are drawn from invariants, not Rails models (ADR-002). Every table write goes through its owner; a Repo-call boundary check enforces it.

| Context | Owns | Invariants enforced | Key public functions | Emits (after commit) | Enqueues |
|---|---|---|---|---|---|
| `Campfire.Accounts` | `accounts`, `users` (human lifecycle), `sessions` | one account; only `active` users authenticate; a `sessions` row is the only proof of login; join code; first run atomic; deactivation frees the email | `first_run/1`, `register_via_join_code/2`, `authenticate_by_password/3`, `fetch_session/1`, `resume_session/2`, `end_session/2`, `transfer_session/2`, `update_profile/2`, `update_account/2`, `set_role/3`, `deactivate_user/2`, `reset_join_code/1`, `reset_password/2` (release) | `{:sockets_revoked, _}` on `user:<id>` | — |
| `Campfire.Rooms` | `rooms`, `memberships`; `Rooms.Presence` (Registry) | open rooms include every active user; one DM per exact user set; DMs never change type; access = membership; revocation closes sockets; present members are never marked unread | `list_sidebar/1`, `get_room!/3`, `create_open/2`, `create_closed/3`, `find_or_create_direct/2`, `update_room/4`, `delete_room/2`, `set_involvement/3`, `mark_read/2`, `fetch_membership/2`, `grant_open_rooms_multi/2`, `mark_unread_multi/3`, `Presence.user_ids/1` | sidebar events on `rooms:open` and `user:<id>`, `{:room_read, id}`, `{:sockets_revoked, reconnect: true}` | `Files.PurgeBlob` (room delete) |
| `Campfire.Chat` | `messages`, `action_text_rich_texts`, `boosts`, `message_search_index`, `searches` | message + body + index + derived state commit together; FTS rowid = message id; only reachable messages are readable or searchable; replies never trigger webhooks | `create_message/4` (`deliver_webhooks:` required), `update_message/3`, `delete_message/2`, `page/3`, `page_around/3`, `refresh/3`, `boost/3`, `unboost/2`, `search/2`, `record_search/2`, `clear_searches/1` | `{:message_created|updated|deleted, _}`, `{:boost_added|removed, _}` on `room:<id>`; `{:room_unread, id}` on `user:<id>` | `Push.Fanout`, `Bots.WebhookDelivery`, `Files.PurgeBlob` |
| `Campfire.Moderation` | `bans` | banned users lose access and content; banned public IPs cannot write | `ban_user/2`, `unban_user/2`, `ip_banned?/1` | `{:sockets_revoked, reconnect: false}` | `Moderation.RemoveBannedContent` |
| `Campfire.Bots` | `webhooks`; bot columns on `users` | bot key format and auth; webhook payload; at-most-once delivery | `authenticate/1`, `create_bot/2`, `update_bot/3`, `reset_key/2`, `deactivate_bot/2`, `webhook_targets/2` | — | — (Chat inserts webhook jobs) |
| `Campfire.Push` | `push_subscriptions` | endpoints on allowed hosts and public IPs only; recipients by involvement and presence; dead subscriptions removed | `subscribe/2`, `unsubscribe/2`, `list_devices/1`, `send_test/2` | — | — |
| `Campfire.Files` | `active_storage_*`, files under `storage/files` | Rails-readable key layout and variants; dangerous decoders never run; files purged after their rows | `attach/2`, `fetch_blob_by_signed_id/1`, `variant/2`, `purge_multi/2` | — | `Files.PurgeBlob` |
| `Campfire.Unfurl` | none | link previews only for public addresses | `fetch/2` | — | — |

**Support namespaces** (no tables, no processes unless listed in section 8):
- `Campfire.Content`: pure sanitizer, plain text, attachables, embed filter, sounds, emoji (ADR-012).
- `Campfire.Net.Guard`: pure surfguard port (ADR-015).
- `Campfire.Http`: Req over named Finch pools (ADR-015).
- `Campfire.Compat.Rails`: per-purpose Rails codecs (ADR-010, ADR-011).
- `CampfireWeb.Compat.ActionCable`: the protocol shim (ADR-008).
- `Campfire.Release`: BootMigrator, RailsMigrator, admin commands, backup (ADR-004, ADR-018).

**Cross-context calls** (one direction each):

| Caller | Callee | Why |
|---|---|---|
| `Accounts.first_run`, `Accounts.register_*`, `Bots.create_bot` | `Rooms.grant_open_rooms_multi/2` | open-room membership in the same transaction (M-06) |
| `Chat.create_message` | `Rooms.mark_unread_multi/3`, `Rooms.Presence.user_ids/1`, `Bots.webhook_targets/2`, `Files.attach/2` | unread, presence sampled at commit, webhook intents, attachment rows |
| `Moderation.ban_user` | `Accounts` revoke-access Multi steps | sessions deleted and status set in the ban transaction |
| `Accounts.deactivate_user` | `Rooms`, `Push`, `Chat` Multi steps | one transaction (M-16) |
| `Bots.WebhookDelivery` | `Chat.create_message(..., deliver_webhooks: false)` | reply loop guard |
| `Push.Fanout` | `Rooms.Presence.user_ids/1`, `Chat` unread counts | presence and badge sampled at run time |
| `CampfireWeb.Compat.ActionCable` | `Accounts.fetch_session/1`, `Rooms.fetch_membership/2`, `Rooms.mark_read/2`, `Rooms.Presence` | the shim only translates; it never writes tables |

## 3. Data Layer

- **Repo topology** (ADR-003):
  - `Campfire.Repo` is the **only writer**: `pool_size: 1`, `default_transaction_mode: :immediate`, WAL, `synchronous: :normal`, `foreign_keys: :on`, `busy_timeout: 5_000`, `migration_source: "ecto_schema_migrations"`.
  - `Campfire.Repo.Read` is read-only, with `pool_size: min(schedulers, 8)`.
  - Both open the same file, `/rails/storage/db/production.sqlite3`. Oban uses the writer.
- **Legacy schema mapping**:
  - Table and column names are unchanged. Schemas use `timestamps(inserted_at: :created_at, type: Campfire.Types.RailsTime)`. This custom type writes Rails' text format; ecto_sqlite3's `:text_datetime` drops microseconds, so it is not used.
  - Enums keep the stored values: `Ecto.Enum` for `role` (`member: 0, administrator: 1, bot: 2`), `status` (`active: 0, deactivated: 1, banned: 2`), involvement strings, STI `rooms.type` strings and polymorphic `record_type` strings. `accounts.settings` is a `:map` read through an accessor that applies defaults.
  - Primary keys are default integer ids.
  - Queries never use `ago/2` or `datetime_add/3` against legacy columns.
- **DDL authority** (ADR-004): the port owns DDL after cutover, and `Campfire.Release.BootMigrator` applies it on boot.
  - Fresh install: runs a frozen Rails baseline SQL.
  - Existing install: `RailsMigrator` runs the 15 Rails migrations as ported steps and records each version in Rails' `schema_migrations`.
  - Port-only additive DDL (`oban_jobs`, optional indexes) runs through `Ecto.Migrator` under `ecto_schema_migrations`.
  - No destructive DDL while the rollback window is open (it has no end date while the bar is ASSUMED).
- **Transactions**: one context function per write intent, wrapped in `Repo.transact/2` or `Ecto.Multi`.
  - The transaction holds the row writes, derived state (touches, unread, FTS, open-room grants) and `Oban.insert` job intents.
  - Broadcasts and socket revocations happen only after `{:ok, _}`.
  - No HTTP, file IO, media work or rendering inside a writer transaction (ADR-005).
- **FTS5**: maintained by app code in the same transaction (delete + insert per rowid). There are no triggers, so Rails can maintain the index after a rollback.

## 4. Web, Realtime and UI

- **UI strategy**: keep the existing Hotwire/Stimulus frontend (`kb/ui-strategy.md` row 1, ADR-001).
  - Phoenix controllers plus HEEx reproduce the HTML, DOM ids, data attributes and `text/vnd.turbo-stream.html` responses.
  - Legacy JS and CSS are served as static assets with the same import map.
  - LiveView is excluded by the bar. Moving to it is a later ADR that retires C-41, C-48 and C-49.
- **Routing**: a route-parity table generated from `config/routes.rb`. There are two pipelines:
  - `:browser`: Rails-format session cookie, `Plug.CSRFProtection` with a 422 mapping, the AllowBrowser plug, `RemoteIp` and `BlockBannedIps`.
  - `:bot_api`: no session, no CSRF, `Bots.authenticate/1`.

  A bot key on any other route returns 403.
- **Realtime**: `Phoenix.PubSub` (local `:pg`) carries core-owned topics: `room:<id>`, `user:<id>`, `rooms:open` and `typing:room:<id>`. It is ephemeral and at-most-once; the catch-up is `GET /rooms/:id/refresh?since=` (M-32).
- **Action Cable shim** (ADR-008), `CampfireWeb.Compat.ActionCable`:
  - **Transport and handshake**: a raw `WebSockAdapter.upgrade` at `/cable`. The handshake checks the Origin, sets the subprotocol `actioncable-v1-json`, and authenticates with the same cookie reader as HTTP.
  - **Channels**: the seven legacy channels map to topics. Identifiers are echoed verbatim.
  - **Authorization**: checked per subscription (membership, signed stream names). Revocation arrives as `{:sockets_revoked, _}` and closes the socket.
  - **Fan-out**: each event is encoded once.
  - **Mailbox cap**: a connection whose mailbox exceeds 1,000 messages is closed with 1013.
  - **Ownership**: an owner and a deletion trigger are recorded in ADR-008.
  - **Protocol scope**: Phoenix Channels and LiveView are not on `/cable` and do not understand this protocol.
- **Presence** (ADR-007): a `Registry` keyed by `{:room, id}` and registered by the shim's connection process. It has an in-memory 60 s refresh window. Unread marking samples it at commit, and push samples it at job run time.

## 5. Jobs

Oban 2.24.1, `Oban.Engines.Lite` on the writer, `oban_jobs` in the same file (ADR-006). The notifier is `Oban.Notifiers.PG`, which uses Erlang process groups, **not** PostgreSQL. Plugins: Pruner (1 day) and Lifeline (15 min). There is no cron, because no recurring work exists.

| Worker | Queue (limit) | max_attempts | Semantics |
|---|---|---|---|
| `Bots.WebhookDelivery` | webhooks (10; `JOB_CONCURRENCY` overrides) | 1 | at-most-once POST; `attempt > 1` → cancel; stale > 10 min → cancel; reply with `deliver_webhooks: false` |
| `Push.Fanout` | push (3) | 1 | durable enqueue, at-most-once per device; `async_stream` max 25; dead subscriptions batch-deleted; stale > 10 min → cancel |
| `Moderation.RemoveBannedContent` | maintenance (1) | 10 | idempotent, batches of 100 per short transaction, unique per user |
| `Files.PurgeBlob` | maintenance (1) | 5 | files first, then rows; skips shared blobs |

Legacy queues are not drained: Redis has no persistence, so there is nothing to drain (C-59, ASSUMED). After a restore, the stale guard drops old webhook and push jobs, while maintenance jobs replay.

## 6. Caching

There is no fragment, response or query cache (ADR-017), because nothing has been measured that needs one. HTTP caching headers are reproduced exactly (C-46). If the room-load profile ever justifies a cache, the only permitted one is filtered body HTML keyed by `{message_id, updated_at, filter_version}`, added through an ADR amendment. The banned-IP check is an indexed query; there is no cache for it.

## 7. Auth Edge

- **Session** (ADR-010):
  - `Compat.Rails.SessionCookie` verifies and mints `session_token` in Rails' signed format (PBKDF2-SHA256 key, HMAC-SHA1 cookie digest, both **needs-vector**). The `sessions` row is the authority.
  - HTTP and `/cable` share `CampfireWeb.Auth.fetch_current_scope/2`.
  - `_campfire_session` is neither read nor written; CSRF, flash and `return_to` live in `_campfire_px`.
- **Passwords**: `bcrypt_elixir` 3.3.2 verifies the legacy `$2a$` hashes. `no_user_verify` covers missing, inactive and bot users. There is no rehash, because the cost is unchanged.
- **Signed capabilities** (ADR-011): avatar, transfer, blob, attachable sgid and Turbo stream names, each in its own purpose-exact module. The port mints them in Rails format so Rails can read them after a rollback. Marshal is never decoded.
- **Bots**: strict key parse, lookup by id, then `secure_compare`. Keys are scrubbed from logs and Sentry.
- **Abuse** (ADR-016): a Hammer ETS login limit, an indexed banned-IP check on writes, and Rails-equivalent `remote_ip` that trusts XFF from loopback only, because the port sits behind Thruster.
- **Revocation**: logout, deactivate, ban and membership removal broadcast after commit. Reconnect re-runs authentication and every subscription check (ADR-009).

## 8. Process Table

These are the only long-lived processes beyond Phoenix, Ecto, Oban and Bandit defaults.

| Name | Runtime reason | Supervisor | Restart | Overload policy |
|---|---|---|---|---|
| `Campfire.Release.BootMigrator` | ordering: migrations must finish before readers, Oban and the Endpoint start | `Campfire.Supervisor` (`:rest_for_one`) | runs in `init`, returns `:ignore` | n/a (boot only; failure halts boot) |
| `Campfire.Rooms.Presence` (`Registry`, `keys: :duplicate`, partitioned) | state: in-memory presence linked to socket processes | `Campfire.Supervisor` | permanent | entries die with their owner; bounded by connected sockets |
| `Campfire.RateLimit` (Hammer ETS + cleanup) | state: login counters | `Campfire.Services` (`:one_for_one`) | permanent | periodic sweep bounds memory under IP spray; loss on restart is parity |
| `Campfire.TaskSupervisor` | isolation: push fan-out tasks; off-socket `present` writes | `Campfire.Services` | permanent | `async_stream` `max_concurrency: 25`, `on_timeout: :kill_task` |
| `Finch` × 3 (`Webhook`, `Push`, `Unfurl`) | isolation: separate pools per outbound flow | `Campfire.Services` | permanent | per-pool size; idle pools reaped (`pool_max_idle_time`) |
| Action Cable connection process (one per WebSocket) | state and concurrency: subscriptions and timers per connection | Bandit / ThousandIsland | temporary | close 1013 when the mailbox exceeds 1,000 messages; `send_timeout`; `max_frame_size` |

There is no GenServer in front of the database, no hand-rolled queue, and no process per room or user.

## 9. Supervision Tree

```elixir
# Campfire.Application.start/2 (design sketch, not code in TARGET)
Campfire.Storage.ensure_dirs!()                 # storage/db, storage/files, storage/backups (C-52)

children = [
  CampfireWeb.Telemetry,
  Campfire.Repo,                                # sole writer: pool_size 1, :immediate, WAL, busy_timeout 5_000
  Campfire.Release.BootMigrator,                # backup if pending, Rails ledger steps, Ecto port-only; :ignore
  Campfire.Repo.Read,                           # read-only pool, after migrations
  {Phoenix.PubSub, name: Campfire.PubSub},      # local :pg, ephemeral
  {Registry, keys: :duplicate, name: Campfire.Rooms.Presence,
   partitions: System.schedulers_online()},
  {Supervisor, name: Campfire.Services, strategy: :one_for_one, children: [
    {Finch, name: Campfire.Finch.Webhook},     # 7 s budgets set per request
    {Finch, name: Campfire.Finch.Push},
    {Finch, name: Campfire.Finch.Unfurl},
    {Task.Supervisor, name: Campfire.TaskSupervisor},
    Campfire.RateLimit                          # use Hammer, backend: :ets
  ]},
  {Oban, Application.fetch_env!(:campfire, Oban)},   # Lite engine, writer repo, PG notifier
  CampfireWeb.Endpoint                          # Bandit on 127.0.0.1:$PORT behind Thruster; /cable shim plug
]

Supervisor.start_link(children, strategy: :rest_for_one, name: Campfire.Supervisor)
# default max_restarts 3 / 5 s: exceeding it halts the VM and the container exits (parity with bin/boot)
```

Container process tree: `tini` (PID 1) → `thrust` → `bin/campfire start`.

On shutdown, the Endpoint drains first, then Oban (`shutdown_grace_period` about 8 s, below Docker's 10 s), then the Repo.

## 10. Dependencies

Versions are from `kb/stacks/rails.md` and `kb/infrastructure.md`, verified on hex.pm on 2026-10-09. Rows marked `verify` were not in the KB.

| Package | Constraint | Use |
|---|---|---|
| `phoenix` | `~> 1.8` (1.8.15) | router, controllers, HEEx |
| `bandit` | `~> 1.12` (1.12.5) | HTTP server |
| `phoenix_pubsub` | `~> 2.4` (2.4.1) | fan-out |
| `websock_adapter` | `~> 0.6` (0.6.0) | Action Cable shim transport |
| `ecto_sql` / `ecto` | `~> 3.14` | `Repo.transact/2` |
| `ecto_sqlite3` | `~> 0.25` (0.25.0) | SQLite adapter |
| `phoenix_ecto` | `~> 4.7` | 404 on missing records |
| `oban` | `~> 2.24` (2.24.1) | jobs, Lite engine |
| `plug_crypto` | `~> 2.2` (2.2.0) | Rails key derivation and HMAC |
| `bcrypt_elixir` | `~> 3.3` (3.3.2) | legacy password hashes |
| `hammer` | `~> 7.5` (7.5.0) | login rate limit |
| `req` / `finch` | `~> 0.7` (0.7.5) / `~> 0.24` (0.24.0) | outbound HTTP |
| `image` / `vix` | `~> 0.72` / `~> 0.42` | variants (libvips) |
| `html_sanitize_ex` or `lazy_html` | `~> 1.5` (1.5.5) / `~> 0.1` (0.1.13) | sanitizer and HTML parsing (slice decision) |
| `web_push_elixir` | `~> 0.8` (0.8.0), candidate | RFC 8291 encryption, vector-gated (ADR-014) |
| `sentry` | `verify` | error reporting |
| `eqrcode` | `verify` | QR SVG |
| `jason` | `verify` | JSON |
| external binaries | `thrust` (pinned image version, `verify`), `tini`, `ffmpeg`, libvips | edge, PID 1, video previews, images |

Not adopted: `phoenix_live_view` (bar), `redix` / `exq` / `phoenix_pubsub_redis` (Redis retired), `cachex` (no measured need), `plug_rails_cookie_session_store` (stale; it does not cover the signed session_token).

## 11. Transition Contract

Cutover mode is **Replacement** (ADR-000). The two runtimes never run live together, so the per-aggregate coexistence contract does not apply. These requirements stand in for it:

| Concern | Decision |
|---|---|
| Write owner | the port only, after the image swap |
| Routing | the same image name and tags; ONCE pulls and recreates the container |
| Schema authority | the port (BootMigrator); Rails' `schema_migrations` holds Rails versions only; additive port DDL in `ecto_schema_migrations` |
| Identity | the port reads and mints the Rails `session_token`; `sessions` rows stay the authority; no forced logout |
| Jobs and events | no legacy queue to drain (volatile Redis); Oban intents are atomic with writes; PubSub is ephemeral |
| Data movement | none (in place); BootMigrator takes a `VACUUM INTO` backup before pending migrations |
| Cutover | stop Rails container → start port container on the same volume (single writer guaranteed by one container) |
| Rollback | restore the `/hooks/pre-backup` snapshot, **and** the pinned Rails image must boot on a port-written DB: no destructive DDL, Rails-format timestamps, cookies, sgids and capabilities, app-maintained FTS. The window has no end date while ADR-000 is ASSUMED. After a rollback, `oban_jobs` is ignored by Rails, so pending jobs are lost (equal to legacy semantics) |

## 12. Performance Plan

- **Goal** (ADR-000): no regression against a measured legacy baseline.
  - Metrics: p95 for message post→broadcast, room load and search; memory at idle and under a chat-burst workload.
  - Additional metrics: writer checkout queue time, Oban queue time per queue, and fan-out completeness at 100, 500 and 1,000 clients.
- **Slice 0** (P0/P1 in `kb/performance-gates.md`):
  - Run the pinned Rails image on a dedicated native Linux host with ≥4 CPUs and a production-shaped DB copy, labelled "untouched upstream `90b330024dec`".
  - Workload: populated read routes, message writes, fan-out, uploads and job drain, at concurrency 1, 16 and 64.
- **Profiles** (P2) of both apps come before any optimization. Each optimization gets its own one-variable screen (P3). A full matched run (P4) is done only on the shipping SHA after parity passes.
- **Known risks to measure**:
  - single-writer contention from Oban fetch and ack plus request writes;
  - render cost without fragment caches;
  - the longer message transaction;
  - shim encode-once.
- **No speed claim exists** until P4 evidence names both SHAs, the command, the result and the denominator.

## 13. Open Decisions

| # | Question | Blocks | Where |
|---|---|---|---|
| 1 | ADR-000 itself is ASSUMED: cutover mode, keep-all contracts, no forced logout, keep Hotwire UI | everything | ADR-000 |
| 2 | M-69: is `SCRIPT_NAME` sub-path serving supported? (the only UNDECIDED ledger row) | web-edge/router slice, `/cable` URL | ledger |
| 3 | Rails crypto parameters: test vectors from the pinned image in both directions | identity slice, capability URLs, Turbo stream names | ADR-010, ADR-011 |
| 4 | Oban 2.24.1 spike: Lite ack batching, PG-notifier wake inside a transaction, Lifeline discard, `:incomplete` unique group | jobs slice acceptance | ADR-006 |
| 5 | Divergences DV-01..DV-19, all `pending` | slices that implement them | `divergences.md` |
| 6 | Triage T-01..T-20 all ASSUMED `preserve`, including security-relevant T-03 (raw custom CSS), T-04, T-06, T-07 | content, moderation and bot slices | features.md |
| 7 | M-51 `X-Version`/`X-Rev` consumers (kept as MAP; DELETE blocked) | none | ledger |
| 8 | Thruster version and `STORAGE_PATH` in the pinned image | release slice | ADR-019 |
| 9 | Source-ZIP export to once-store hosts (runtime Q4) | release packaging | ADR-018 |
| 10 | `RAILS_MASTER_KEY` credentials fallback for VAPID (runtime Q2) | push config | ADR-018 |
| 11 | Owner of `Campfire.Net.Guard` tracking surfguard (mechanisms Q6) | none (ships regardless) | ADR-015 |
| 12 | CSP: legacy emits none (initializer commented out); parity keeps none (mechanisms Q8) | none | ledger M-63 |
| 13 | Oldest released schema that must upgrade directly (contracts Q4) | BootMigrator test matrix | ADR-004 |
| 14 | Probes on production-shaped copies: timestamp text, PRAGMAs, `record_type` values, NULL involvement, boost lengths, `has_json` boolean form, session token length | data slice | ADR-003 |
