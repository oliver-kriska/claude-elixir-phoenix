# Scratchpad: rewrite-00-foundation

Seeded by /rewrite:roadmap --auto on 2026-10-09. Authoritative decisions live in
.claude/rewrite/architecture/; this file repeats the ones this slice needs.
Nothing here is approved: ASSUMED and proposed decisions are marked. The slice
is blocked-for-handoff until ADR-000, ADR-003, ADR-004 and ADR-010 are approved.

### [00:00] DECISION: Replacement cutover, in-place open, no destructive DDL (ADR-000, ASSUMED)
The port opens /rails/storage/db/production.sqlite3 in place. While the rollback
window is open (it has no end date while ADR-000 is ASSUMED), there is no
destructive DDL, no column reuse and no trigger that Rails would not maintain.

### [00:00] DECISION: One writer Repo plus a read-only Repo (ADR-003, proposed)
Campfire.Repo is the only writer:
- pool_size 1, default_transaction_mode :immediate
- WAL, synchronous :normal, foreign_keys :on
- busy_timeout 5_000 as an adapter option
- migration_source "ecto_schema_migrations"

Campfire.Repo.Read is read-only with pool_size min(schedulers, 8). Oban uses the
writer. Repo.reader/0 returns the writer inside a transaction.

### [00:00] DECISION: Campfire.Types.RailsTime on every legacy datetime column (ADR-003, proposed)
Dumps "%Y-%m-%d %H:%M:%S" and appends ".ffffff" only when usec > 0. The global
datetime_type stays :iso8601 and is used by Oban only. Schemas set
@timestamps_opts with inserted_at: :created_at.

### [00:00] DECISION: Legacy encodings kept as stored (ADR-003, proposed)
- role is member 0, administrator 1, bot 2.
- status is active 0, deactivated 1, banned 2.
- involvement uses nullable strings; "visible" means involvement != 'invisible', with NULL excluded.
- STI rooms.type strings are kept.
- record_type is an Ecto.Enum, falling back to :string if the 01 probe finds other values.
- settings is a :map with a defaults accessor that preserves unknown keys.

### [00:00] DECISION: Port DDL in ecto_schema_migrations only (ADR-004, ASSUMED)
Port-only migrations are additive, with versions greater than 20251212154340.
Rails' schema_migrations holds exactly the Rails versions; port versions are
never mirrored into it.

### [00:00] DECISION: Boot migrator in 00 is a gate only (roadmap, auto)
If the Rails ledger is not exactly the 15 versions up to 20251212154340, boot
halts with a clear message and runs no DDL. RailsMigrator, the fresh-install
baseline SQL and the pre-migration VACUUM INTO backup belong to slice 17.

### [00:00] DECISION: Oban Lite on the writer with no queues (ADR-006 ASSUMED + roadmap, auto)
oban_jobs is the first port-only migration. Oban starts with Engines.Lite,
Notifiers.PG (Erlang process groups, not PostgreSQL) and queues: []. Slice 02
needs Oban.insert inside the message transaction. Queues, plugins, the stale
guard and workers belong to slice 08.

### [00:00] DECISION: Auth edge is read-only (ADR-010, ASSUMED)
Compat.Rails.SessionCookie.verify/1 reads the Rails signed session_token
(purpose cookie.session_token). The sessions row is the authority, checked via
Accounts.fetch_session/1. CampfireWeb.Auth.fetch_current_scope/2 is the one
reader that HTTP (and later /cable) share. Slice 00 has no minting, no hourly
refresh write and no login; those land in slice 03, which closes C-20.

### [00:00] DECISION: One private purpose-exact Rails verifier (ADR-010/ADR-011, ASSUMED)
Compat.Rails.MessageVerifier requires a purpose argument and enforces:
- an exact pur match and the exp check;
- strict base64 and a size cap;
- comparison with Plug.Crypto.secure_compare/2.

There is no public "verify anything" function. Keys are derived once at boot
into :persistent_term. No MessageVerifier or KeyGenerator code may exist
outside compat/.

### [00:00] DECISION: Explicit %Campfire.Scope{} first argument (ADR-002, proposed; ledger M-05)
Scope holds user, session and account. There are no request globals. The host
is taken from the conn.

### [00:00] DECISION: :rest_for_one tree in architecture order (architecture.md section 9, proposed)
Children start in this order: Telemetry, Repo, BootMigrator (returns :ignore),
Repo.Read, PubSub, Presence Registry, Services, Oban, Endpoint. Default restart
intensity applies, and exceeding it halts the VM (parity with bin/boot).
Storage.ensure_dirs! runs before the children.

### [00:00] DECISION: No LiveView, no Redis, no Ruby (ADR-000/ADR-001 + charter, ASSUMED)
Deps exclude phoenix_live_view, redix, exq and phoenix_pubsub_redis. The
release image carries no Ruby runtime.

### [00:00] DECISION: SECRET_KEY_BASE required; port salts are disjoint (ADR-010 section 8, ASSUMED)
Boot fails if SECRET_KEY_BASE is missing. Port salts are campfire/px/<purpose>
and never reuse a Rails salt.

### [00:00] DECISION: Baseline measured on the untouched pinned image (ADR-000 performance goal; kb/performance-gates P0/P1)
The image is labelled "untouched upstream 90b330024dec". The run uses:
- a dedicated native Linux host with at least 4 CPUs, and disjoint CPU sets for the load generator;
- pinned image digest and DB checksum;
- concurrency 1/16/64;
- p95 for post to broadcast, room load and search; memory at idle and under a chat burst.

### [00:00] DECISION: Pinned image built from a git archive and run sandboxed on synthetic data (roadmap, auto)
SOURCE is never written to or executed in place. Production data and real
secrets are never used.

### [00:00] DECISION: Dead code not ported (ledger M-63, R-25)
Not ported: kredis, Purchaser, Membership#read, generate.rake and the commented
CSP. CSP stays absent for parity.

### [00:00] DEAD-END: ecto_sqlite3 :text_datetime or :iso8601 on legacy columns
:text_datetime drops microseconds, and :iso8601 writes T...Z. Either breaks
text ordering against Rails-written rows (ADR-003; corrects kb/data-compat.md).

### [00:00] DEAD-END: Pooled writer, or busy_timeout set as a PRAGMA
A pooled writer causes SQLITE_BUSY between BEAM processes (ADR-003,
kb/sqlite-on-beam rules 1-2).

### [00:00] DEAD-END: Ecto writing Rails schema_migrations, or Rails migrations as Ecto migrations
ecto_sql cannot write Rails' version-only table, and a second ledger can
disagree with Rails' (ADR-004).

### [00:00] DEAD-END: Ruby in the image to run rails db:migrate
This conflicts with the charter goal of removing the Ruby runtime (ADR-004).

### [00:00] DEAD-END: phx.gen.auth tokens with a one-way legacy reader
A rollback to Rails would log everyone out, which breaks ADR-000 Identity (ADR-010).

### [00:00] DEAD-END: Decrypting _campfire_session or a general Rails verifier library
It costs an AES-GCM codec for one stale-form 422. A shared verifier enables
purpose confusion (ADR-010, ADR-011). plug_rails_cookie_session_store is stale
and does not cover session_token.

### [00:00] DEAD-END: A GenServer or hand-rolled connection owner in front of the database
architecture.md section 8 rules out a DB-owning process. ADR-003 would require a
P2 profile first.

### [00:00] DEAD-END: Starting Oban queues or workers in 00
The Resque-to-Oban replacement is slice 08, with its own correctness and
performance gates (slicing rule 6).

### [00:00] DEAD-END: Baseline against our own intermediate build
The baseline must be the untouched upstream image (kb/performance-gates P1).
