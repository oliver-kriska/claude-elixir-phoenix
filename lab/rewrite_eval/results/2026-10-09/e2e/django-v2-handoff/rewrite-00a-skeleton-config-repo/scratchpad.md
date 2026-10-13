# Scratchpad: rewrite-00a-skeleton-config-repo

Seeded by /rewrite:roadmap on 2026-10-09. Authoritative decisions live in
.claude/rewrite/architecture/; this file repeats the ones this slice needs.

### [00:00] DECISION: D-01 One Phoenix JSON-only release on Bandit (ADR-001, proposed)
No Oban, PubSub, LiveView, HTML, mailer or cache. Legacy has no jobs, realtime
or cache (runtime.md); R-20/R-21 stay in-request.

### [00:00] DECISION: D-02 Keep the legacy SQLite file via ecto_sqlite3 (ADR-000, ASSUMED)
Schema kept as-is; Postgres is OD-3, not a default.

### [00:00] DECISION: D-03 One writer Repo: pool_size 1, BEGIN IMMEDIATE, busy_timeout 5000, synchronous FULL (ADR-003, proposed)
Reader Repo deferred to the slice-01 measurement (OD-4). WAL is DV-22, pending.
synchronous FULL because the legacy rollback journal gave that durability.

### [00:00] DECISION: D-04 Secrets and paths from runtime env only, fail-closed (ADR-011, ASSUMED)
JWT_SECRET ≥32 bytes, SECRET_KEY_BASE ≥64, DATABASE_PATH, PHX_HOST, PORT required;
CORS_ORIGINS optional, `*` rejected. Never compile_env for secrets.

### [00:00] DECISION: D-05 Corsica with configured origins, no credentials (ADR-011, C-31)
Defaults: http(s)://localhost:4000, http(s)://0.0.0.0:4000; allow headers authorization, content-type.

### [00:00] DECISION: D-06 No debug error pages outside dev (ADR-011, C-34)

### [00:00] DEAD-END: X-01 Bare Plug.Router instead of Phoenix
Rebuilds routing, pipelines and fallback by hand (ADR-001).

### [00:00] DEAD-END: X-02 Oban or PubSub without a legacy need
Unused durable queue adds SQLite writer contention (ADR-001).

### [00:00] DEAD-END: X-03 Deriving the JWT key from SECRET_KEY_BASE
Couples rotations (ADR-011).

### [00:00] DEAD-END: X-04 Reusing the legacy committed SECRET_KEY
Security defect C-14; legacy tokens are rejected (DV-01).

### [00:00] DEAD-END: X-05 synchronous: :normal
Silent durability downgrade vs legacy FULL (ADR-003).

### [plan] DECISION: P-1 journal_mode :delete until DV-22 is approved
ecto_sqlite3 0.25 Connection.default_opts/1 does Keyword.put_new(:journal_mode, :wal), and WAL
persists in the file. Shipping the default would apply DV-22 silently. Set :delete explicitly.

### [plan] DECISION: P-2 Conduit.Boot = synchronous child start returning :ignore
A temporary Task that crashes does not stop the app, which breaks §10 fencing. start: {Boot, :run, [opts]}
runs BEGIN IMMEDIATE + PRAGMA logging before the Endpoint; {:error, _} aborts the boot.

### [plan] DECISION: P-3 CORS allow_headers = legacy corsheaders 1.x default list, max_age 86400
A superset of ADR-011's two headers keeps C-31 parity. Verify against the legacy pinned version.

### [plan] DEAD-END: a list of origins passed to Corsica from runtime.exs
Plug opts are compiled into the Endpoint; use an MFA origin checker that reads app env.

### [plan] NOTE: phx_new 1.8.15 sqlite template adds Ecto.Migrator (runs migrations in releases),
DNSCluster and PubSub, and reads POOL_SIZE (default 5). All removed or overridden in Phase 1/2.

### [plan] NOTE: Phoenix 1.8.15 put_secure_browser_headers has no x-frame-options (CSP frame-ancestors
'self' instead). DV-13 wording is stale.
