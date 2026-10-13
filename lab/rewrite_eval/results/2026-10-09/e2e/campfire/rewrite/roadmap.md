# Rewrite Roadmap — ONCE Campfire → Elixir/Phoenix

Bar: ADR-000 (ASSUMED) · Mode: Replacement · Source @ `90b330024dec`

- **Written**: 2026-10-09 by `/rewrite:roadmap --auto`. Nothing here is approved. ADR-000 and every ADR are `ASSUMED` or `proposed`; every divergence (DV-01..DV-19) is `pending`; the ledger has one UNDECIDED row (M-69).
- **Inputs**: `charter.md`, `architecture/` (ADR-000..021, `architecture.md`, `decisions.md`, `divergences.md`), `ledger.md` (151 rows), `analysis/` (28 capabilities, 57 contracts).
- **Transition**: cutover is **Replacement** (ADR-000). The two runtimes never run live together, so no slice carries a per-slice transition contract. `architecture.md` §11 stands in for it, and slice 18 rehearses it. Nothing reaches users until slice 18 passes, so an intermediate slice may implement a safe subset of a behavior (for example escaped plain-text bodies before slice 12) as long as it says so.
- **Legacy runtime**: "pinned image" means the Rails image built from a clean `git archive` of SOURCE @ `90b330024dec`, run in an isolated sandbox on synthetic data only. SOURCE is never written to or executed in place.
- **State**: every slice is `blocked`. Each one depends on at least one ASSUMED consequential decision (ADR-000 always), per slicing rule 9. Slice 00 is seeded anyway as **blocked-for-handoff** (see the end of this file).

| # | Slice | Capabilities | Ledger | Contracts | State | Blocked by |
|---|-------|--------------|--------|-----------|-------|------------|
| 00 | Foundation | — | M-05, M-54, M-63, R-25, R-26 | C-01 | blocked | ADR-000 ASSUMED; ADR-004 ASSUMED; ADR-003 proposed; ADR-010 ASSUMED (cookie read format) |
| 01 | Oracle fixtures | — | M-15 | C-02, C-03, C-06 | blocked | ADR-000 ASSUMED (keep-all → capture list); ADR-010, ADR-011 ASSUMED (vector list); ADR-003 proposed; contracts Q4 (oldest released schema) |
| 02 | Post a message and deliver it live | F-08 | M-01, M-02, M-03, M-04, M-26, M-29, M-30, M-31, M-39, M-52, M-61, R-20, R-27 | C-09, C-13, C-41, C-49 | blocked | ADR-000 ASSUMED (keep Hotwire UI → shim); ADR-005 proposed + DV-01, DV-12; ADR-006 ASSUMED; ADR-007 ASSUMED; ADR-008 proposed + DV-16; ADR-011 ASSUMED; M-69 UNDECIDED (`/cable` meta tag only) |
| 03 | Identity: first run, sign-in/out, join | F-01, F-02, F-03 | M-06, M-07, M-09, M-10, M-11, M-36, R-21, R-29 | C-07, C-08, C-12, C-14, C-20, C-21, C-22, C-25, C-43 | blocked | ADR-000 ASSUMED (no forced logout); ADR-010 ASSUMED + DV-06, DV-09; ADR-009 ASSUMED + DV-04; ADR-002 proposed + DV-18, DV-19; T-11, T-19 ASSUMED |
| 04 | Abuse controls without Redis (replacement) | — | M-47, R-23 | C-42 | blocked | ADR-016 ASSUMED + DV-10; ADR-019 ASSUMED (XFF from loopback); T-04, T-19 ASSUMED |
| 05 | Rooms, DMs, involvement, sidebar, revocation | F-05, F-06, F-07, F-14 | M-12, M-13, M-14, M-50 | C-04, C-05, C-28, C-44 | blocked | ADR-021 proposed + DV-17; ADR-009 ASSUMED + DV-04; ADR-002 proposed + DV-19; ADR-008 proposed; T-10, T-14 ASSUMED |
| 06 | Presence and unread on a Registry (replacement) | F-12 | M-27, M-28, R-05 | — | blocked | ADR-007 ASSUMED + DV-05; ADR-008 proposed; ADR-000 ASSUMED (rollback window) |
| 07 | Conversation: history, edits, boosts, typing, search | F-09, F-10, F-11, F-13, F-16 | M-08, M-32, M-33, M-34, M-60, R-22 | C-16, C-48 | blocked | ADR-021 proposed + DV-14; ADR-005 proposed + DV-12; ADR-017 proposed + DV-15; T-08, T-09, T-13 ASSUMED |
| 08 | Background jobs on Oban; Redis and Resque retired (replacement) | — | M-25, R-07, R-08, R-24 | C-59, C-60 | blocked | ADR-006 ASSUMED + DV-02, DV-03, DV-07; C-59 retirement ASSUMED; Oban spike (architecture open #4) |
| 09 | Files and media | F-26 | M-44, M-45, M-46, R-28, R-33, R-34 | C-11, C-27 | blocked | ADR-013 proposed + DV-11; ADR-011 ASSUMED (vectors 6, 8); ADR-006 ASSUMED; max upload size UNKNOWN |
| 10 | Account administration and moderation | F-20, F-21 | M-16, M-17, M-68, R-32 | C-17 | blocked | ADR-009 ASSUMED + DV-04; ADR-006 ASSUMED + DV-13; ADR-016 ASSUMED; ADR-012 proposed; T-03, T-04, T-05, T-15 ASSUMED |
| 11 | Profile, avatars and transfer links | F-04, F-19 | M-37 | C-23, C-24 | blocked | ADR-011 ASSUMED (vectors 4, 5); ADR-017 proposed + DV-15; T-01, T-02 ASSUMED |
| 12 | Content safety, mentions and link unfurl | F-17, F-18, F-25 | M-38, M-40, M-41, M-42, M-43, M-62, M-67 | C-10 | blocked | ADR-012 proposed; ADR-011 ASSUMED (vector 7); ADR-015 proposed (Net.Guard owner open); T-17, T-18 ASSUMED |
| 13 | Web Push | F-15 | M-21, M-22, M-23, M-24, M-64, M-65, R-09, R-31 | C-15, C-37, C-38, C-39 | blocked | ADR-014 proposed (library vector gate); ADR-006 ASSUMED + DV-02, DV-03; ADR-007 ASSUMED; T-12 ASSUMED; `RAILS_MASTER_KEY` VAPID fallback open |
| 14 | Bot management and bot HTTP API | F-22, F-23 | M-18, M-19, M-53 | C-26, C-30, C-31, C-32, C-33, C-34 | blocked | ADR-020 proposed; ADR-010 ASSUMED + DV-08; T-07, T-09, T-20 ASSUMED; wrong-key 302 vs 401 UNKNOWN |
| 15 | Bot webhooks | F-24 | M-20, R-30 | C-35, C-36 | blocked | ADR-020 proposed; ADR-006 ASSUMED + DV-02, DV-03; ADR-015 proposed; T-06, T-07 ASSUMED |
| 16 | Web shell: routes, PWA shell, browser gate, HTTP caching | F-27 | M-35, M-48, M-49, M-51, M-66, M-69 | C-40, C-45, C-46 | blocked | M-69 UNDECIDED; ADR-017 proposed + DV-15; ADR-001 proposed; T-16 ASSUMED; M-51 consumer question |
| 17 | Release image, boot migrator and operator surface | F-28 | M-55, M-56, M-57, M-58, M-59, R-01, R-02, R-03, R-04, R-06, R-10 | C-47, C-50, C-51, C-54, C-56, C-57, C-58 | blocked | ADR-018 ASSUMED + DV-07; ADR-019 ASSUMED; ADR-004 ASSUMED; runtime Q2, Q4; contracts Q4; M-69 UNDECIDED |
| 18 | Release rehearsal | — | — | C-52, C-53, C-55 | blocked | ADR-000 ASSUMED (cutover, rollback window without end date); DV-01..DV-19 pending; ADR-004, ADR-006 ASSUMED |

**Placement check**: 28 of 28 `F-` capabilities and 151 of 151 ledger IDs appear exactly once in the table above (69 M-, 25 R-, 57 C-). Nothing was left unplaced. A row lands in the slice whose exit gate **closes** it. When another slice builds or re-asserts part of it first, that is listed under "Deliberate splits".

## Why slice 02 is "post a message and deliver it live"

Campfire is a single-node web appliance with realtime fan-out (ADR-001). Slicing.md's "Web app" and "Realtime" rows both point at the same path: an authenticated write with its side effects, then an authorized broadcast and a negative permission probe. F-08 is that path, and it carries more guarantees and contracts than any other capability:

- **Atomicity (ADR-005, DV-01)**: message, body, FTS row, room touch, unread marking and job intents commit together. This is the longest writer transaction in the app.
- **Visibility**: broadcasts only after commit.
- **Durable work (ADR-006)**: `Oban.insert` inside the domain transaction, with the `deliver_webhooks:` loop guard.
- **Authorization twice**: membership on POST, then signature plus membership at Action Cable subscribe for harvested stream names (M-29).
- **Contracts**: C-09, C-13, C-41 and C-49 here, plus the C-02 timestamp format on the hottest write.

It is also the only path that exercises every new piece of the architecture at once: the single-writer Repo, `RailsTime`, raw FTS SQL, Oban Lite inside a transaction, presence sampled in the transaction, PubSub after commit, the encode-once dispatcher, the Action Cable SHIM and the Turbo stream-name codec. Post→broadcast p95 is the first metric in ADR-000's performance goal. If the architecture is wrong, this slice shows it.

Rejected candidates:
- **Identity (F-02)**: high risk, but mostly codec and vector work that proves little about the runtime design.
- **Ban (F-21)**: destructive, but it depends on rooms, message delete and jobs.
- **Bot API (F-23)**: a strict wire contract, but it rides on the same write pipeline, so it comes later and reuses it.

## Deliberate splits

| Item | Lands in (closed) | Also touched | Why |
|------|-------------------|--------------|-----|
| F-08 | 02 | 09 (file attachments, attachment-only plain text), 12 (sanitized rich-text render, mention chips, `/play` sounds, emoji presentation), 14 (bot posts reuse the path) | 02 proves the write-and-deliver core. It renders bodies as escaped plain text until 12, which is safe and never shipped (Replacement) |
| C-20 | 03 (both directions: port-minted cookie verified by the pinned image) | 00 builds the read direction and gates it on vectors 1–2 | rule 2: the foundation has a read-only auth edge |
| C-02 | 01 (byte round-trip through `RailsTime`) | 02 (port-written row byte-compare), 07 (mixed legacy/port page boundary) | the format is fixed at fixture time and re-asserted where it matters |
| C-13 | 02 | 06 (present member not marked unread), 07 (boost touches message) | derived state grows with each write path |
| C-14 | 03 | 10 (deactivation frees the address) | — |
| C-17 | 10 (public-IP bans) | 07 (10 recent searches per user) | one contract row covers two features |
| C-43 | 03 | 13 (push subscription deletion re-checked once Push owns the table) | 03 deletes the row scoped to the user |
| C-46 | 16 (full `curl -I` comparison) | 07, 09, 11 produce the headers | one comparison at the end |
| C-48 | 07 (paging, refresh) | 12 (autocomplete, unfurl goldens) | — |
| M-07, R-21 | 03 (logout revocation) | 05 (membership revoke), 10 (deactivate, ban) | first slice that needs revocation owns the mechanism |
| M-14 | 05 (room delete) | 07 (message delete), 09 (`PurgeBlob` worker) | — |
| M-25 | 08 | 00 creates `oban_jobs` and starts Oban Lite with **no queues**, so 02 can insert intents | rule 6: the queue replacement keeps its own gates |
| M-30 | 02 (UnreadRooms and ReadRooms channel mapping) | 06 (the `present` producer of `{:room_read, _}`) | — |
| M-43 `Net.Guard`, `Campfire.Http` | 12 | 13 (push pinning), 15 (webhook pool, no guard) | shared mechanism lands with its first user |
| M-48 | 16 (generated permission matrix across all routes) | every slice adds its rows | — |
| M-61 | 02 (message partial golden fragments) | later slices add their fragments | — |
| R-03, M-57 | 17 (full BootMigrator, RailsMigrator, fresh-install baseline SQL) | 00 has a minimal schema gate (open in place at `20251212154340`, port-only DDL, else halt) | — |
| `RemoteIp` plug (ADR-016) | 04 (vector table gate) | 03 writes `sessions.ip_address` through it | no ledger row of its own |
| Presence facade | 06 (M-28) | 02 calls `Rooms.Presence.user_ids/1`, which returns an empty set until 06 registers subscriptions | — |

---

## 00 Foundation
**Goal**: An Elixir/Phoenix release skeleton opens an existing Campfire SQLite file in place without changing anything the pinned Rails image depends on. It recognizes a legacy signed-in browser (read-only), and a measured legacy baseline exists for the "no regression" goal.
**Capabilities**: none (infrastructure for 02).
**Ledger rows**:
- M-05 (MAP → `%Campfire.Scope{user, session, account}`, explicit first argument)
- M-54 (MAP → writer `Campfire.Repo` with pool 1, `:immediate`, WAL, `busy_timeout` 5 000 as an adapter option, FKs on; read-only `Campfire.Repo.Read`)
- M-63 (DELETE → not ported: kredis, Purchaser, `Membership#read`, `generate.rake`, commented CSP)
- R-25 (DELETE → Kredis not ported)
- R-26 (MAP → writer and reader Repos on `/rails/storage/db/production.sqlite3`)

**Built here, closed later**:
- legacy schemas for the tables 02 touches: accounts, users, sessions, rooms, memberships, messages, `action_text_rich_texts`, webhooks; `message_search_index` is raw SQL. Encodings close in 01.
- `Campfire.Types.RailsTime` (C-02 closes in 01).
- the read direction of the `session_token` reader plus `Accounts.fetch_session/1` and `CampfireWeb.Auth.fetch_current_scope/2` (C-20 closes in 03).
- a minimal schema gate (full migrator in 17).
- `oban_jobs` through Ecto under `ecto_schema_migrations`, and Oban Lite started with `queues: []` (M-25 closes in 08).
- the `:rest_for_one` supervision tree skeleton.

**Contracts**:
- C-01 (in-place SQLite at `20251212154340`, Rails ledger intact). Witness: boot the port on a copy of a DB the pinned image produced. `SELECT version FROM schema_migrations` is unchanged; Ecto uses `ecto_schema_migrations`; the pinned image boots again on the same file and reports nothing pending.

**Acceptance criteria**:
- [ ] C-01 witness passes. `ecto_schema_migrations` and `oban_jobs` are the only new objects, and Rails ignores them.
- [ ] A DB whose Rails ledger is behind `20251212154340` halts boot with a clear message and no partial DDL (the upgrade path is slice 17).
- [ ] Writer settings hold:
  - PRAGMAs: `journal_mode=wal`, `foreign_keys=1`.
  - pool size 1, and transactions begin `IMMEDIATE`.
  - the reader rejects writes.
  - boot logs `sqlite_version()` and asserts FTS5 is compiled in.
- [ ] Read-only auth edge, tested with vectors 1–2 (key derivation, `session_token` Set-Cookie) captured from the pinned image:
  - valid cookie plus an existing `sessions` row → scope with that user;
  - tampered, wrong-purpose or expired cookie → anonymous;
  - deleted row → anonymous.
- [ ] Baseline P0/P1 on the pinned image labelled "untouched upstream `90b330024dec`":
  - metrics: p95 post→broadcast, room load, search; memory at idle and under a chat burst;
  - concurrency 1/16/64, with a hardware block;
  - P0 workload contract written down (numeric goal stays open).
- [ ] Dependencies contain no Redis client, no `phoenix_live_view` and no Ruby runtime.

**Exit gate**: `/rewrite:verify 00`. The C-01 witness passes on a fresh copy, the baseline table and hardware block are committed, and there is no BLOCKER.
**Blocked by**:
- ADR-000 ASSUMED (Replacement, keep schema, in place).
- ADR-004 ASSUMED (DDL authority, `ecto_schema_migrations`, port versions not mirrored).
- ADR-003 proposed (Repo topology, `RailsTime`).
- ADR-010 ASSUMED (Rails-format `session_token`, `sessions` row as authority).
- Open: the performance goal has no number yet (P0); the architecture #14 probes come from 01.

**Plan**: `.claude/plans/rewrite-00-foundation/` · State: blocked (seeded, blocked-for-handoff)

## 01 Oracle fixtures
**Goal**: Every later slice tests against truth produced by the legacy code. This is a synthetic, production-shaped corpus generated by the pinned image, with no production data, no customer content and no real secrets.
**Capabilities**: none.
**Contents**:
- **Synthetic databases** built through the pinned image's UI and console. They include the real-world quirks:
  - NULL involvement, NULL `settings`, boosts longer than 16 characters;
  - timestamps with usec = 0 and usec > 0;
  - Trix and Lexxy bodies, opengraph embeds, Rails-7 Marshal sgid mentions (from the legacy test vectors);
  - deactivated, banned and bot users; DMs;
  - push subscriptions with fake endpoints; bans;
  - blobs with variants on disk.
- **DB snapshots** at each released schema version, for the C-55 matrix in 17 and 18.
- **Security vectors 1–11** (security consult): key derivation, `session_token`, avatar, transfer, blob, sgid, `variation_digest`, the CSRF source check, the `remote_ip` table and the rate limit. They come with a reverse-direction harness that feeds port-minted values to the pinned image.
- **Captured payloads**:
  - Action Cable frame transcripts per channel: welcome, ping, confirm and reject, disconnect variants, turbo-stream appends;
  - bot API golden JSON and headers; webhook request bodies from a stub receiver;
  - a push payload decrypted with a test key;
  - a `to_plain_text` parity corpus and sanitizer outputs;
  - `curl -I` header captures;
  - golden HTML fragments;
  - admin-script stdout and exit codes.

**Ledger rows**: M-15 (MAP → `Ecto.Enum` with legacy values; STI and polymorphic strings; `settings` map accessor)
**Contracts**:
- C-02 (UTC text timestamps). Witness: Rails-written rows round-trip byte-equal through `RailsTime` for usec = 0 and usec > 0, and the port's `utc_now` dump matches the Rails format.
- C-03 (integer enums). Witness: fixture rows with each role and status integer load as the matching atom, and `:bot` dumps as 2.
- C-06 (polymorphic strings). Witness: `SELECT DISTINCT record_type, name` on the corpus equals the port's `Ecto.Enum` sets.

**Acceptance criteria**:
- [ ] A fixture manifest lists, for each artifact, the pinned image digest, the producing command and the consumer slice.
- [ ] A scan finds no real email domains, no production secrets (`SECRET_KEY_BASE` is a generated test value) and no customer content.
- [ ] The corpus loads through the 00 schemas with zero cast errors.
- [ ] Architecture open #14 is answered: timestamp text, PRAGMAs, `record_type` values, NULL involvement, boost lengths, the `has_json` boolean form, session token length.
- [ ] The reverse-direction harness records the pinned image's verdict on a port-minted value.

**Exit gate**: `/rewrite:verify 01`. Every fixture has a consumer slice, the C-02, C-03 and C-06 witnesses pass, and the PII/secret scan passes.
**Blocked by**:
- ADR-000 ASSUMED (keep-all contracts decides what to capture).
- ADR-010 and ADR-011 ASSUMED (the vector list).
- ADR-003 proposed.
- Contracts Q4: the oldest released schema that must upgrade directly (sets the snapshot matrix).

**Plan**: `.claude/plans/rewrite-01-oracle-fixtures/` · State: blocked

## 02 Post a message and deliver it live
**Goal** (F-08): A member posts into a room they belong to, and every member watching the room sees it appended within a second, in order. The message is durable and searchable, and it marks unread and records push and bot intents.
**Ledger rows**:
- M-01 (REPLACE → `Chat.create_message(scope, room, attrs, deliver_webhooks:)` in one writer `Repo.transact`; `Oban.insert` of `Push.Fanout` and `Bots.WebhookDelivery` intents; PubSub after `{:ok, _}`)
- M-02 (MAP → `Chat.SearchIndex` delete+insert in the transaction)
- M-03 (MAP → explicit room touch)
- M-04 (KEEP → `client_message_id`, DOM id `message_<cmid>`)
- M-26 (SHIM → `CampfireWeb.Compat.ActionCable` on `websock_adapter`)
- M-29 (SHIM → RoomMessages channel + `Compat.Rails.Turbo.StreamName`)
- M-30 (REPLACE → `{:room_unread, id}` on `user:<id>` → UnreadRooms; ReadRooms mapping)
- M-31 (REPLACE → domain events + HEEx turbo-stream encoder, encode-once dispatcher)
- M-39 (MAP → `Chat.RichText`, `Content.PlainText`, `Content.Attachables`)
- M-52 (MAP → URLs from the conn; shim Origin check against the request host)
- M-61 (KEEP → DOM ids and data attributes, golden fragments)
- R-20 (REPLACE → `Phoenix.PubSub`)
- R-27 (MAP → FTS raw SQL in the transaction)

**Contracts**:
- C-09 (FTS app-maintained). Witness: create through the port, then `SELECT rowid FROM message_search_index WHERE body MATCH ?`; porter stemming works; no triggers in the schema.
- C-13 (derived state). Witness: a port create advances the room's `updated_at` and sets `unread_at` on the other visible, non-author memberships.
- C-41 (`/cable` channels). Witness: replay the 01 frame transcripts against the shim.
- C-49 (`client_message_id` DOM keys). Witness: a composer send yields one message element after the broadcast.

**Acceptance criteria**:
- [ ] A and B are viewing R. When A posts "hi", B's tab receives the turbo-stream append within 1 s, in `created_at` order.
- [ ] C is a member who is not viewing R. C's membership gets `unread_at = message.created_at`, and C's UnreadRooms stream receives `{roomId: R}`.
- [ ] Negative: D is not a member. D's unread stream receives nothing. D's RoomMessages subscribe with a harvested signed name for R gets `reject_subscription`. The Turbo StreamsChannel rejects any `*:messages` name.
- [ ] Negative: a POST to a room the user is not in creates no message and renders `room_not_found`.
- [ ] Negative: an unauthenticated `/cable` handshake gets disconnect `unauthorized` with `reconnect:false`. A foreign Origin is refused.
- [ ] Atomicity (DV-01): an injected FTS failure leaves no message, no body, no unread change, no job row and no broadcast.
- [ ] Job intents:
  - one `Push.Fanout` row per message;
  - one `Bots.WebhookDelivery` row per eligible bot (in a DM: every active bot member with a webhook; in a shared room: mentioned active bots only; never the author);
  - `deliver_webhooks:` is required, and `false` inserts no webhook rows;
  - no worker runs (08, 13, 15).
- [ ] A retried POST with the same `client_message_id` creates a second message (M-04 kept).
- [ ] Encode-once: N subscribers cause one encoder call per event.
- [ ] `Content.PlainText` equals the 01 corpus for text and mention bodies. `Turbo.StreamName` vectors verify in both directions.
- [ ] Performance screen: p95 post→broadcast at c16 and writer checkout queue time are recorded against the 00 baseline. This is a screen, not a claim.

**Exit gate**: `/rewrite:verify 02`. All of the above and every witness pass. The idiom audit finds no broadcast inside a transaction and no GenServer queue, and xref shows core never references `CampfireWeb.Compat`.
**Blocked by**:
- ADR-000 ASSUMED (keep the Hotwire UI, hence the shim; keep the schema).
- ADR-005 proposed + DV-01 and DV-12 pending.
- ADR-006 ASSUMED (Oban insert in the transaction; the PG-notifier wake inside a transaction is unverified).
- ADR-007 ASSUMED (presence sampled in the transaction).
- ADR-008 proposed + DV-16 pending.
- ADR-011 ASSUMED (stream-name vectors).
- ADR-003 proposed.
- M-69 UNDECIDED: only the `/cable` URL meta tag; 02 assumes the root path.
- `verify`: phoenix_pubsub 2.4.1 subscription metadata.

**Plan**: `.claude/plans/rewrite-02-post-message-live/` · State: blocked

## 03 Identity: first run, sign-in/out, join
**Goal**:
- F-01: the first visitor creates the one account, its administrator and "All Talk" atomically.
- F-02: active users sign in with email and password and stay signed in on that device. Sign-out ends that device session, its sockets and its push subscription.
- F-03: a holder of the join link becomes a member of every open room.

**Ledger rows**:
- M-06 (MAP → `Rooms.grant_open_rooms_multi/2` in the user-create transaction)
- M-07 (REPLACE → `{:sockets_revoked, reconnect:}` after commit; the shim emits disconnect)
- M-09 (MAP → `Accounts.resume_session/2`, refreshed at most hourly)
- M-10 (MAP → `register_via_join_code/2` + `unique_constraint(:email_address)`)
- M-11 (MAP → `first_run/1` in one transaction + `singleton_guard`)
- M-36 (SHIM → `Compat.Rails.SessionCookie` verify and mint, `fetch_current_scope/2`, `Plug.CSRFProtection` on `_campfire_px`)
- R-21 (REPLACE → `user:<id>` revocation topic)
- R-29 (SHIM → `_campfire_session` not read)

**Contracts**:
- C-07: a legacy hash verifies; a wrong password, a NULL digest and a bot user fail; a 100-character password signup succeeds.
- C-08: deleting a row makes the next request redirect to login and refuses the socket connect. A resume within 1 h does not write; after 1 h it does.
- C-12: legacy and nil `settings` both yield the defaults; a second account insert fails; the join code matches `\w{4}-\w{4}-\w{4}`.
- C-14: a duplicate signup redirects to `/session/new?email_address=`.
- C-20: vectors (valid, tampered, expired, wrong purpose, rotated key) verify Rails→port; a port-minted cookie verifies in the pinned image; HTTP and `/cable` agree.
- C-21 (DV-06): a Rails-rendered form posted after cutover gets 422 with a reload prompt, and the Rails cookie stays untouched.
- C-22: a POST without a token gets 422; one with the `X-CSRF-Token` header is accepted.
- C-25: same route; a stale code gets 404.
- C-43: the session row and cookie are gone, sockets close, the device push row (scoped to the user) is deleted, and logout succeeds without realtime.

**Acceptance criteria**:
- [ ] F-01 probes:
  - first-run POST → one account, one admin and "All Talk" with that admin as member; the visitor is signed in at `/`;
  - two concurrent POSTs → one account, both requests redirect, no 500;
  - with an account present, `GET /first_run` redirects to `/`.
- [ ] F-02 probes:
  - correct credentials → session row, cookie, redirect to the original URL;
  - a deactivated or banned user → 401 and no session;
  - device A signs out → device B stays signed in, and A's sockets close.

  The rate-limit probe belongs to 04.
- [ ] F-03 probes: the current code → member of every open room; a stale code → 404; an existing email → redirect to login.
- [ ] DV-18: a failure injected after the account insert leaves nothing behind. DV-19: join grants commit in the same transaction. DV-09: `return_to` redirects only to local paths.
- [ ] Login timing: an unknown email and a wrong password do equal bcrypt work.

**Exit gate**: `/rewrite:verify 03`, with every C-20 vector green in both directions.
**Blocked by**:
- ADR-000 ASSUMED (identity: no forced logout).
- ADR-010 ASSUMED + DV-06 and DV-09 pending.
- ADR-009 ASSUMED + DV-04 pending.
- ADR-002 proposed + DV-18 and DV-19 pending.
- T-11 and T-19 ASSUMED.
- Vector 9 (Rails 8.2 `Sec-Fetch-Site` check) open.

**Plan**: `.claude/plans/rewrite-03-identity/` · State: blocked

## 04 Abuse controls without Redis (replacement)
**Goal**: Retire the Redis rate-limit counters while keeping two behaviors: 10 login POSTs per 3 minutes per client IP returns 429, and banned public IPs cannot write. Client IP must resolve exactly as Rails does behind Thruster. Serves F-02 and F-21; owns no capability.
**Ledger rows**:
- M-47 (REPLACE → Hammer 7.5 ETS `:fix_window` plug on `POST /session`)
- R-23 (REPLACE → Hammer ETS; state lost on restart, which is parity)

**Contracts**:
- C-42. Witness:
  - the 11th POST in the window gets 429, and successful logins count;
  - a banned IP gets 429 on POST and 200 on GET, including `/up`;
  - the 01 `remote_ip` vector table passes, including a spoofed XFF from an untrusted peer.

**Acceptance criteria**:
- [ ] The C-42 witness passes, including the F-02 probe "10 failures from one IP → the 11th is 429".
- [ ] Correctness gate: the banned-IP check runs only on non-GET/HEAD requests and uses the indexed reader query.
- [ ] Performance gate: ETS memory stays bounded under an IP-spray load (sweep), the limiter adds no writer writes, and login p95 is compared with the baseline.

**Exit gate**: `/rewrite:verify 04` with both gates.
**Blocked by**:
- ADR-016 ASSUMED + DV-10 pending (fallback: an exact first-hit ETS limiter).
- ADR-019 ASSUMED (XFF trusted from loopback).
- T-04 and T-19 ASSUMED.

**Plan**: `.claude/plans/rewrite-04-abuse-controls/` · State: blocked

## 05 Rooms, DMs, involvement, sidebar, revocation
**Goal**:
- F-05: members land in their last room with a live sidebar.
- F-06: members create, rename, convert and delete shared rooms.
- F-07: one DM per exact user set, never widened.
- F-14: per-room involvement drives visibility.
- Revoked members lose live access at once.

**Ledger rows**:
- M-12 (MAP → `find_or_create_direct/2` in one IMMEDIATE transaction)
- M-13 (MAP → `get_room!(scope, id, types:)`, direct type immutable)
- M-14 (MAP → `delete_room/2` Multi deleting children first, plus `PurgeBlob` intents)
- M-50 (MAP → `last_room` plug + `WelcomeController`)

**Contracts**:
- C-04: membership strings round-trip in open and direct rooms; `invisible` is excluded from the sidebar.
- C-05: all three STI types read; a direct type change is rejected; closed→open grants every active user.
- C-28: a member subscribes; the membership is revoked; a resubscribe with the same signed name is rejected.
- C-44: `last_room` cookie name and room ids are unchanged.

**Acceptance criteria**:
- [ ] F-05 probes: last room B → redirect to B, or to the oldest room after removal; a new open room appears in every sidebar live; a closed room I am not in sends me nothing.
- [ ] F-06 probes:
  - revise {A, B} → {A, C}: B's socket reconnects and B cannot resubscribe; C sees the room;
  - closed→open makes every active user a member;
  - with the restriction on → 403; a non-creator PATCH → 403;
  - a DM id on the opens or closeds route → not found and unchanged.
- [ ] F-07 probes: a DM with B twice → one room; {B} and {B, C} → two rooms; DELETE of a closed room through the directs route → nothing deleted.
- [ ] F-14 probes: `invisible` removes the room from the sidebar live and stops unread marking; a DM change sends no sidebar broadcast.
- [ ] DV-17: two concurrent DM creates produce one room. DV-04: a revise rolled back by an injected failure sends no disconnect frame.

**Exit gate**: `/rewrite:verify 05`.
**Blocked by**:
- ADR-021 proposed + DV-17 pending.
- ADR-009 ASSUMED + DV-04 pending.
- ADR-002 proposed + DV-19 pending.
- ADR-008 proposed.
- T-10 and T-14 ASSUMED.

**Plan**: `.claude/plans/rewrite-05-rooms/` · State: blocked

## 06 Presence and unread on a Registry (replacement)
**Goal** (F-12): Rooms with unseen activity show unread, and viewing a room clears it on every device. A member is present in a room while a tab is subscribed, with a 60 s liveness window. Presence now lives in memory instead of DB counters.
**Ledger rows**:
- M-27 (SHIM → Presence channel checks membership at subscribe)
- M-28 (REPLACE → `Rooms.Presence` facade over a duplicate-key `Registry`; `present` clears `unread_at` from a `Task.Supervisor` child)
- R-05 (DELETE → the registry starts empty)

**Contracts**: none owned. Re-asserts C-13 (02) for present members and the C-41 Presence and ReadRooms frames.
**Acceptance criteria**:
- [ ] F-12 probes:
  - B viewing R stays read;
  - a tab dead for 61 s without unsubscribe → unread;
  - two tabs with one closed → still present;
  - after a restart, nobody is present.
- [ ] Removing a membership removes its registry entries.
- [ ] Rollback probe: after the port runs, the pinned image boots and no membership claims to be connected. The port never writes `connections` or `connected_at` (byte-compare).
- [ ] Performance gate: at 500 visible tabs, refreshes cost zero writer transactions (legacy is about 10 per second). `present` latency is measured, and no socket process blocks on the writer.

**Exit gate**: `/rewrite:verify 06` with correctness and performance gates.
**Blocked by**:
- ADR-007 ASSUMED + DV-05 pending.
- ADR-008 proposed.
- ADR-000 ASSUMED (rollback window: the columns are retained, not dropped).

**Plan**: `.claude/plans/rewrite-06-presence/` · State: blocked

## 07 Conversation: history, edits, boosts, typing, search
**Goal**:
- F-09: latest 40, older and newer pages, permalinks, catch-up after being offline.
- F-10: author or admin edit and delete, seen live.
- F-11: boosts; members remove only their own.
- F-13: typing indicator.
- F-16: search across reachable messages, plus the last 10 searches.

**Ledger rows**:
- M-08 (MAP → `record_search/2`, `clear_searches/1`)
- M-32 (MAP → `Chat.refresh/3` + turbo-stream response)
- M-33 (REPLACE → shim typing channel on `typing:room:<id>`)
- M-34 (DELETE → HEEx per request, no fragment cache)
- M-60 (MAP → `(created_at, id)` keyset)
- R-22 (DELETE → no Redis fragment cache)

**Contracts**:
- C-16: a 40-character legacy boost loads, and there is no max-16 validation.
- C-48: golden responses for message paging (204 on empty, ETag) and refresh.

**Acceptance criteria**:
- [ ] F-09 probes: with 100 messages, the pages are 61–100, 21–60 (`before=61`) and 61–100 (`after=60`); an empty room returns 204; refresh returns 3 new and 1 updated; a non-member gets 404.
- [ ] F-10 probes: an admin edit is seen by every viewer, and search finds the new text only; a non-admin, non-author gets 403.
- [ ] F-11 probes: a boost is seen and removed live; deleting someone else's boost gets 404; a message in a foreign room gets 404.
- [ ] F-13 probes: a member receives `start` with id and name; a non-member subscribe is rejected; the indicator clears within 5 s.
- [ ] F-16 probes: porter stemming over member rooms only; 11 searches leave 10, and clear leaves 0; `"foo" OR bar*` causes no error.
- [ ] DV-14: 41 messages with the same `created_at` paginate without loss. C-02: a mixed legacy/port page boundary returns 40 contiguous messages. DV-12: an edit repairs a missing FTS row. DV-15: a name edit is visible on the next render.

**Exit gate**: `/rewrite:verify 07`.
**Blocked by**:
- ADR-021 proposed + DV-14 pending (fallback: the strict legacy predicate).
- ADR-005 proposed + DV-12 pending.
- ADR-017 proposed + DV-15 pending.
- T-08, T-09 and T-13 ASSUMED.

**Plan**: `.claude/plans/rewrite-07-conversation/` · State: blocked

## 08 Background jobs on Oban; Redis and Resque retired (replacement)
**Goal**: Background work keeps its delivery semantics but gains a durable enqueue, atomic with the domain write. No Redis process or client remains. Serves F-15, F-21, F-24 and F-26; owns no capability.
**Ledger rows**:
- M-25 (REPLACE → Oban 2.24 Lite on the writer; queues webhooks 10, push 3, maintenance 1; Pruner and Lifeline)
- R-07 (DELETE → no `redis-server`)
- R-08 (REPLACE → Oban queues)
- R-24 (REPLACE → `oban_jobs` in the same file)

**Contracts**:
- C-59 (retired). Witness: no Redis client or server in the deps or image; the app boots without `REDIS_URL`; a set `REDIS_URL` logs one line and is ignored.
- C-60 (changed). Witness: `JOB_CONCURRENCY` sets the webhooks limit, and the other knobs are ignored.

**Acceptance criteria**:
- [ ] A one-day Oban 2.24.1 spike settles the unverified items: Lite ack batching, the PG-notifier wake for jobs inserted inside a transaction (pickup latency measured), Lifeline discard at `max_attempts`, the `:incomplete` unique group, and unique-check cost on SQLite.
- [ ] Stale guard: a job older than 10 minutes at pickup is cancelled (`{:cancel, :stale}`) for the at-most-once classes. Restore test: a 1-hour-old webhook- or push-class job is cancelled, and a maintenance-class job replays. Test workers stand in until 09, 10, 13 and 15.
- [ ] Every worker `timeout/1` is below `rescue_after`, `shutdown_grace_period` is about 8 s, and a failed transaction leaves no job.
- [ ] Performance gate: writer checkout queue time and Oban queue time under a chat burst with job intents; post→broadcast p95 shows no regression against the 02 screen and the baseline.

**Exit gate**: `/rewrite:verify 08` with correctness and performance gates.
**Blocked by**:
- ADR-006 ASSUMED + DV-02, DV-03 and DV-07 pending.
- C-59 retirement ASSUMED (external `REDIS_URL` users are unknown).
- Architecture open #4 (the Oban spike).

**Plan**: `.claude/plans/rewrite-08-oban-jobs/` · State: blocked

## 09 Files and media
**Goal** (F-26): Files posted to rooms are stored, get thumbnails or previews safely, and are served to readers. Dangerous decoders never run, and anonymous callers cannot upload.
**Ledger rows**:
- M-44 (KEEP → `Campfire.Files` over the legacy tables; `image`/`vix` variants; processing outside the writer transaction)
- M-45 (MAP → content-type allow-list + Vix loader blocking)
- M-46 (DELETE → no direct-upload or disk `PUT` routes)
- R-28 (KEEP → disk layout)
- R-33 (REPLACE → `Files.PurgeBlob`)
- R-34 (MAP → synchronous in the request, outside `Repo.transact`)

**Contracts**:
- C-11: resolve 5 legacy blobs to disk paths and compare MD5; a legacy variant record is served without regeneration; the pinned image reads a port upload.
- C-27: legacy blob URLs serve without a session; a port-minted blob signed id verifies in the pinned image; anonymous upload is impossible.

**Acceptance criteria**:
- [ ] F-26 probes: a 4000×3000 JPEG gets a thumb no larger than 1200×800; an anonymous direct-upload POST gets 401 and creates no blob; a BMP or SVG produces no variant and the message still renders as a file.
- [ ] A message with an attachment goes through the 02 pipeline: the file is written before the transaction, and an attachment-only message uses its filename as plain text.
- [ ] DV-11: a purge skips a blob still attached elsewhere, and the job retries idempotently. The `variation_digest` vector 8 passes.

**Exit gate**: `/rewrite:verify 09`.
**Blocked by**:
- ADR-013 proposed + DV-11 pending.
- ADR-011 ASSUMED (vectors 6 and 8).
- ADR-006 ASSUMED.
- `verify`: the vix 0.42 loader-blocking API.
- Max upload size UNKNOWN.

**Plan**: `.claude/plans/rewrite-09-files/` · State: blocked

## 10 Account administration and moderation
**Goal**:
- F-20: admins manage the account name, logo, room policy, custom CSS, roles, deactivation and the join link.
- F-21: a ban logs the user out everywhere, removes their messages and blocks writes from their IPs. Unban restores the account.

**Ledger rows**:
- M-16 (MAP → `deactivate_user/2` Multi; disconnect after commit)
- M-17 (REPLACE → `Moderation.ban_user/2` + `RemoveBannedContent` + `BlockBannedIps`)
- M-68 (MAP → raw custom CSS inside `<style>`)
- R-32 (REPLACE → `Moderation.RemoveBannedContent`, batches of 100, idempotent)

**Contracts**:
- C-17: a ban stores public IPs only, and a private-IP session aborts the ban (T-04 preserve). Witness per `contracts.md` C-17; search retention is asserted in 07.

**Acceptance criteria**:
- [ ] F-20 probes:
  - deactivate B → sessions gone, sockets closed, shared memberships gone, DMs kept, email freed (the C-14 half);
  - a member setting role=admin gets 403;
  - role=bot becomes `member`.
- [ ] F-21 probes:
  - B's two IPs get 429 on POST, B's messages vanish live, and B cannot sign in;
  - a non-admin gets 403;
  - after unban, POST works and the messages stay deleted.
- [ ] DV-13: removal of more than 250 messages runs in batches with every removal broadcast, and retries are idempotent. A rolled-back ban leaves no job and sends no disconnect (DV-04). Logo variants large and small are served.

**Exit gate**: `/rewrite:verify 10`.
**Blocked by**:
- ADR-009 ASSUMED + DV-04 pending.
- ADR-006 ASSUMED + DV-13 pending.
- ADR-016 ASSUMED.
- ADR-012 proposed.
- T-03 (security: raw CSS), T-04, T-05 and T-15 ASSUMED.

**Plan**: `.claude/plans/rewrite-10-admin-moderation/` · State: blocked

## 11 Profile, avatars and transfer links
**Goal**:
- F-19: users edit their own profile; anyone signed in sees user cards; avatars come from stable, cacheable, unguessable URLs.
- F-04: a 4-hour sign-in link or QR moves a session to another device, and admins can mint one for any active user.

**Ledger rows**: M-37 (SHIM → `Compat.Rails.SignedId.Avatar` / `.Transfer`)
**Contracts**:
- C-23: legacy avatar URLs serve; the pinned image reads port URLs; a tampered token gets 404.
- C-24: valid for 4 h and reusable; an avatar token on the transfer route gets 400; a port-minted link verifies in the pinned image.

**Acceptance criteria**:
- [ ] F-19 probes: a bio edit shows on the card; `PATCH /users/B/profile` edits the caller; a tampered avatar token gets 404.
- [ ] F-04 probes: a 3-hour-old id signs in; a 5-hour-old id or a deactivated user gets 400.
- [ ] Wrong-purpose tests cover every pair (avatar, transfer, blob). Avatar headers and the variant match the captures (C-46 closes in 16).

**Exit gate**: `/rewrite:verify 11`.
**Blocked by**:
- ADR-011 ASSUMED (vectors 4 and 5).
- ADR-017 proposed + DV-15 pending (avatar freshness).
- T-01 and T-02 ASSUMED.

**Plan**: `.claude/plans/rewrite-11-profile-avatars/` · State: blocked

## 12 Content safety, mentions and link unfurl
**Goal**:
- F-25: no reader ever gets executable markup, while old messages keep their mentions, embeds and formatting.
- F-17: pasted public URLs unfurl safely, and private addresses are never fetched.
- F-18: @-mention autocomplete is scoped to the room.

**Ledger rows**:
- M-38 (SHIM → `Compat.Rails.GlobalId.Attachable`)
- M-40 (MAP → `Content.OpengraphEmbed`)
- M-41 (MAP → `Content.Sanitizer`)
- M-42 (MAP → `Unfurl.fetch/2` over `Campfire.Http` on `Finch.Unfurl`)
- M-43 (REPLACE → `Campfire.Net.Guard`)
- M-62 (DELETE → `Content.Emoji.all_emoji?/1`)
- M-67 (MAP → `Content.Sounds`)

**Contracts**:
- C-10: historical bodies render. User mentions resolve even with invalid signatures, including the Rails 7 Marshal form. A non-User sgid with a bad signature becomes a missing attachable. Trix and Lexxy embeds render, and same-host or non-http URLs are dropped.

**Acceptance criteria**:
- [ ] F-25 probes: no `javascript:` href, no `onerror`, `<script>` and `<iframe>` removed, and an old-secret mention still renders.
- [ ] F-17 probes: a `169.254.169.254` or `10.x` target gets 204 with no connection; a redirect to localhost gets 204; a 6 MB body gets 204; a same-host embed image is dropped.
- [ ] F-18 probes: autocomplete is scoped to the room; `<img onerror>` names are escaped; a foreign `room_id` gets 404.
- [ ] The message partial now renders sanitized rich text instead of 02's escaped text, with `/play` sounds and emoji presentation.
- [ ] The surfguard vector table passes, the sanitizer fuzz corpus is decoded-equivalent to 01, the full plain-text parity corpus passes, and the C-48 autocomplete and unfurl goldens match.

**Exit gate**: `/rewrite:verify 12`.
**Blocked by**:
- ADR-012 proposed.
- ADR-011 ASSUMED (vector 7).
- ADR-015 proposed (the Net.Guard owner is open, mechanisms Q6).
- T-17 and T-18 ASSUMED.
- Sanitizer library choice: a slice decision between `html_sanitize_ex` and `lazy_html`.

**Plan**: `.claude/plans/rewrite-12-content-safety/` · State: blocked

## 13 Web Push
**Goal** (F-15): Away members get an OS notification for messages they care about on each registered device, and dead subscriptions are cleaned up.
**Ledger rows**:
- M-21 (REPLACE → `Push.Fanout` recipient query + `Rooms.Presence`)
- M-22 (REPLACE → bounded `async_stream_nolink`)
- M-23 (MAP → changeset guard + `pinned_request/3`)
- M-24 (KEEP → same VAPID keys, RFC 8291 encryption)
- M-64 (MAP → `subscribe/2`, `unsubscribe/2`, `send_test/2`)
- M-65 (MAP → `PwaController` serving the legacy service worker and manifest)
- R-09 (REPLACE → Task.Supervisor)
- R-31 (REPLACE → `Push.Fanout`)

**Contracts**:
- C-15: a legacy subscription receives a port-sent test notification; an invalid re-register gets 422.
- C-37: a captured push decrypts to the legacy payload.
- C-38: guarded at save and at delivery; dead rows are deleted.
- C-39: same URLs, scope `/`.

**Acceptance criteria**:
- [ ] F-15 probes:
  - one push with title R and body "A: text";
  - no push when the member is connected, `invisible`, or `mentions` without being mentioned;
  - an evil-suffix host or `:8443` gets 422;
  - a 410 response deletes the row.
- [ ] Real-browser receipt on Chrome, Firefox and Safari. DV-02 (no overflow drop) and DV-03 (stale jobs cancelled) hold. `/service-worker` and `/webmanifest` are unauthenticated and CSRF-exempt. Logout deletes the device row (C-43 re-check).

**Exit gate**: `/rewrite:verify 13`.
**Blocked by**:
- ADR-014 proposed (adopt `web_push_elixir` only if it passes the vectors).
- ADR-006 ASSUMED + DV-02 and DV-03 pending.
- ADR-007 ASSUMED.
- ADR-015 proposed.
- T-12 ASSUMED (strengthen rejected).
- `RAILS_MASTER_KEY` VAPID fallback (architecture open #10).

**Plan**: `.claude/plans/rewrite-13-web-push/` · State: blocked

## 14 Bot management and bot HTTP API
**Goal**:
- F-22: admins create, edit and deactivate bots and rotate their keys.
- F-23: bots read, post, edit and delete their own messages and boosts over HTTP, in rooms they belong to.

**Ledger rows**:
- M-18 (MAP → `:bot_api` pipeline + strict key parse + `secure_compare`)
- M-19 (MAP → `BotApi.*` controllers + explicit JSON views)
- M-53 (MAP → `:filter_parameters`, Logger formatter, telemetry handler and Sentry `before_send` scrubbing bot keys)

**Contracts**:
- C-26: key format; malformed keys are rejected (DV-08).
- C-30: raw body, 201 + `Location`.
- C-31: golden JSON, `X-Total-Count`, `Link`.
- C-32: 204, 403 and 404.
- C-33: boost JSON, 422 when blank, 404 for a foreign boost.
- C-34: a bot key on any other route gets 403.

**Acceptance criteria**:
- [ ] F-22 probes: after a key reset, the old key is unauthenticated and the new key works; a member on `/account/bots` gets 403.
- [ ] F-23 probes:
  - "héllo ✓" gets 201 and is seen live;
  - 45 messages → 40 returned with `Link ?before=` and `X-Total-Count: 45`;
  - a PATCH of someone else's message gets 403; a foreign room gets 404.
- [ ] The golden JSON diff is empty, and the admin-view curl recipes replay. A log grep after bot traffic finds no key, including in `Link`.
- [ ] T-07: an API post that mentions another bot inserts that bot's webhook intent. The wrong-key status (302 or 401) matches the 01 capture.

**Exit gate**: `/rewrite:verify 14`.
**Blocked by**:
- ADR-020 proposed.
- ADR-010 ASSUMED + DV-08 pending.
- T-07, T-09 and T-20 ASSUMED.
- Wrong-key 302 vs 401 is UNKNOWN until 01 captures it.

**Plan**: `.claude/plans/rewrite-14-bot-api/` · State: blocked

## 15 Bot webhooks
**Goal** (F-24): A mentioned or DM'd bot's webhook receives the message, and its reply is posted as the bot. A timeout posts the apology message.
**Ledger rows**:
- M-20 (REPLACE → `Bots.WebhookDelivery`: `max_attempts: 1`, stale guard, `Finch.Webhook`, 7 s budgets)
- R-30 (REPLACE → the same worker)

**Contracts**:
- C-35: the payload is byte-compatible with the 01 capture, with no signature and at most one POST.
- C-36: 7 s timeouts and the text, attachment and timeout replies, including the T-06 quirk.

**Acceptance criteria**:
- [ ] F-24 probes:
  - `@X ping` → `plain == "ping"`, and a `pong` reply appears from X;
  - a hang longer than 7 s → "Failed to respond within 7 seconds";
  - a bot mentioning itself causes no webhook;
  - a bot that is a member but not mentioned gets no webhook.
- [ ] A reply uses `deliver_webhooks: false` and inserts no job. A Lifeline-rescued executing job ends discarded with no POST. `http://10.0.0.5` is allowed, because webhooks have no guard by design.

**Exit gate**: `/rewrite:verify 15`.
**Blocked by**:
- ADR-020 proposed.
- ADR-006 ASSUMED + DV-02 and DV-03 pending.
- ADR-015 proposed.
- T-06 and T-07 ASSUMED.

**Plan**: `.claude/plans/rewrite-15-bot-webhooks/` · State: blocked

## 16 Web shell: routes, PWA shell, browser gate, HTTP caching
**Goal** (F-27): The app installs as a PWA and refuses outdated browsers. It serves QR codes and logos publicly and labels responses with version headers. Every bookmarkable route and every permission matches the legacy app.
**Ledger rows**:
- M-35 (MAP → `CampfireWeb.Plugs.HttpCache`)
- M-48 (MAP → permission matrix generated over every route and actor)
- M-49 (MAP → user-agent plug with the same thresholds)
- M-51 (MAP → version header plug; DELETE stays blocked)
- M-66 (MAP → QR controller)
- M-69 (UNDECIDED → `SCRIPT_NAME` sub-path: endpoint `url: [path:]` plus a prefixed `/cable`, or DELETE with a release note)

**Contracts**:
- C-40: a route-parity table generated from `config/routes.rb`.
- C-45: Chrome 119 gets the floor page; Chrome 120 gets login.
- C-46: the `curl -I` header diff is empty for avatar, logo, QR, blob and message page, including `X-Version`/`X-Rev`.

**Acceptance criteria**:
- [ ] F-27 probes: the browser gate; `/service-worker` without login; a banned IP still gets `GET /up`.
- [ ] Every route × actor cell (anonymous, member, admin, creator, bot, deactivated) matches legacy.
- [ ] The route-parity table is complete, and the C-46 diff is empty.

**Exit gate**: `/rewrite:verify 16`.
**Blocked by**:
- M-69 UNDECIDED.
- ADR-017 proposed + DV-15 pending.
- ADR-001 proposed.
- T-16 ASSUMED.
- M-51 consumer question.
- Apple Messages UA behavior UNKNOWN.
- CSP stays absent (M-63 Q8).

**Plan**: `.claude/plans/rewrite-16-web-shell/` · State: blocked

## 17 Release image, boot migrator and operator surface
**Goal** (F-28): An operator runs the single container, generates secrets, resets a password and takes or restores consistent backups without the UI. The image is a drop-in replacement on the same volume, and every released schema upgrades on boot.
**Ledger rows**:
- M-55 (DELETE → one release under `tini` → `thrust`)
- M-56 (KEEP → pinned Thruster)
- M-57 (MAP → wrapper scripts over `bin/campfire rpc`, `VACUUM INTO`, BootMigrator)
- M-58 (MAP → `runtime.exs` with the legacy names)
- M-59 (MAP → `sentry`)
- R-01 (REPLACE → `tini` + `:rest_for_one`)
- R-02 (KEEP → Thruster → Bandit on loopback)
- R-03 (REPLACE → full BootMigrator: baseline SQL, RailsMigrator for 15 versions, Ecto port-only)
- R-04 (DELETE → Bandit; `/up` kept)
- R-06 (DELETE → `bin/campfire remote`)
- R-10 (REPLACE → multi-stage Dockerfile, same tags)

**Contracts**:
- C-47: `/up` returns 200 only after a full boot and is not logged.
- C-50: same image and tags, uid 1000, ports 80/443.
- C-51: env names; retired knobs are ignored (DV-07).
- C-54: script stdout and exit codes match the 01 captures.
- C-56: TLS modes, and certificates are reused.
- C-57: no key, password or email in logs.
- C-58: `purchased_by.yml` is read if present.

**Acceptance criteria**:
- [ ] F-28 probes: `reset-password` with an unknown email exits non-zero and changes nothing. Backup and restore probes are rehearsed in 18.
- [ ] `docker run` on a legacy volume leaves files owned by uid 1000.
- [ ] The fresh-install `.schema` diff against the pinned image's fresh DB is empty.
- [ ] RailsMigrator: a crash injected between steps leaves a consistent ledger, and the owner→admin remap (C-03 data step) runs first.
- [ ] Each retired knob logs one line (DV-07). Thruster starts with no new certificate issuance.

**Exit gate**: `/rewrite:verify 17`.
**Blocked by**:
- ADR-018 ASSUMED + DV-07 pending.
- ADR-019 ASSUMED (`verify` the Thruster version and `STORAGE_PATH`).
- ADR-004 ASSUMED.
- Runtime Q2 (`RAILS_MASTER_KEY`) and Q4 (source-ZIP export).
- Contracts Q4 (oldest schema).
- M-69 UNDECIDED (if yes, the endpoint path prefix).

**Plan**: `.claude/plans/rewrite-17-release-operator/` · State: blocked

## 18 Release rehearsal
**Goal**: Prove the Replacement cutover and its rollback on copies of production-shaped volumes before any install sees the port.
**Capabilities**: none (re-runs every probe from 02–17).
**Contracts**:
- C-52: after a week-equivalent soak, `find / -newer` shows writes only under `/rails/storage` (plus tmp).
- C-53: `pre-backup` during a write burst passes `PRAGMA integrity_check`; `post-restore` serves the restored data.
- C-55: the port boots on DB snapshots from every released tag and reaches the target schema.

**Acceptance criteria**:
- [ ] Cutover: stop the pinned Rails container, then start the port image on the same volume. The open is in place, BootMigrator takes a `VACUUM INTO` backup when anything is pending, and the full 02–17 probe suite passes.
- [ ] Restore: after `post-restore`, stale webhook and push jobs are cancelled (DV-03) and maintenance jobs replay.
- [ ] Rollback A: restore the pre-backup snapshot, and the pinned image boots with nothing pending.
- [ ] Rollback B: the pinned image boots directly on the port-written DB with nothing pending. On it:
  - port-minted cookies keep users logged in;
  - port-minted avatar URLs, blob links and sgids verify;
  - FTS is consistent;
  - Rails resets the presence columns.
- [ ] Operator commands pass via `docker exec`: `reset-password`, `generate-secrets`, `create-vapid-key`, `prepare-backup`.
- [ ] P4 matched performance run on the shipping SHA against the 00 baseline. No speed claim is made without it.
- [ ] Every divergence DV-01..DV-19 is approved or reverted, and ADR-000 is accepted.

**Exit gate**: `/rewrite:verify 18` plus human sign-off on ADR-000 and every DV row.
**Blocked by**:
- ADR-000 ASSUMED (cutover mode; the rollback window has no end date).
- DV-01..DV-19 pending.
- ADR-004 and ADR-006 ASSUMED.
- Contracts Q4.

**Plan**: `.claude/plans/rewrite-18-release-rehearsal/` · State: blocked

---

## Handoff

- **Next slice**: none is unblocked. Every slice depends on ADR-000 (ASSUMED), so slice **00** was seeded as **blocked-for-handoff**:
  - `.claude/plans/rewrite-00-foundation/interview.md`
  - `.claude/plans/rewrite-00-foundation/scratchpad.md`
- **`/phx:plan` was not invoked**: `--auto` never hands off while ADR-000 has an ASSUMED cutover, data, identity or clients decision. Approve ADR-000 (and ADR-003, ADR-004, ADR-010 for slice 00), then run `/phx:plan .claude/plans/rewrite-00-foundation/interview.md`.
- **To unblock the most slices at once**, decide:
  1. ADR-000 as a whole.
  2. M-69 (`SCRIPT_NAME`).
  3. The pending divergences DV-01..DV-19.
  4. The security-relevant triage items T-03, T-04, T-06, T-07.
