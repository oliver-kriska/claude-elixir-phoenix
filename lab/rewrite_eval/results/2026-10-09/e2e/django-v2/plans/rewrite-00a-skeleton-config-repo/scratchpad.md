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
