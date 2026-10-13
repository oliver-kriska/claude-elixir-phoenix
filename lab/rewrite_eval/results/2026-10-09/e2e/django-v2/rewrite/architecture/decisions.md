# Decisions — ADR Index

Date: 2026-10-09 · Bar: ADR-000 (ASSUMED, `--auto`). Nothing below is approved by the user.

| ADR | Title | Status | Ledger IDs (main) | Divergences |
|-----|-------|--------|-------------------|-------------|
| ADR-000 | Compatibility bar | ASSUMED | all | — |
| ADR-001 | App shape and stack: Phoenix JSON API, no Oban, no PubSub | proposed | R-01, R-02, M-03, M-35, M-41 | — |
| ADR-002 | Context map: Accounts, Social, Articles; Profile kept | proposed | M-39, M-40, C-01 | — |
| ADR-003 | SQLite Repo topology, WAL, synchronous FULL | proposed (measurement-gated, OD-4) | R-10 | DV-22 |
| ADR-004 | Legacy schema mapping and DDL authority | proposed | M-40, R-12, C-42, C-53, M-26 | DV-15, DV-21 |
| ADR-005 | LegacyDateTime Ecto type | proposed | M-11, C-03 | DV-24 |
| ADR-006 | Token authentication (Joken HS256, new secret) | ASSUMED (security) | M-04, M-05, M-06, C-10..C-16 | DV-01, DV-02, DV-25, DV-P5 |
| ADR-007 | Password hashing (Django PBKDF2; iterations open) | proposed; iteration raise UNDECIDED (OD-2) | M-16, C-02, R-33, M-17, C-13 | DV-P7, DV-P4 |
| ADR-008 | Object authorization (article update, comment delete) | ASSUMED (security) | M-27, C-32, C-33 | DV-03, DV-04, DV-P6 |
| ADR-009 | Wire contract and error envelopes | proposed / ASSUMED relaxations | M-08, M-09, M-28, C-17..C-30, C-34, C-45..C-56 | DV-05, DV-07..DV-13, DV-16, DV-18, DV-19 |
| ADR-010 | Atomic multi-write context operations | proposed (strengthening) | M-01, M-18, M-20, M-21 | DV-20 |
| ADR-011 | Runtime configuration, secrets, CORS | ASSUMED | C-44, M-36, C-31, C-34 | DV-05, DV-06 |
| ADR-012 | Operator surface; admin retired; backups | ASSUMED (admin purpose unknown, OD-5) | M-41, C-43, M-33, C-52, C-55 | DV-14, DV-17 |
| ADR-013 | Cutover runbook, scans, rollback | proposed (OD-6) | R-10, C-02..C-07, C-38 | DV-01 |

## Open decisions (architecture.md section 14)

| ID | Decision | Blocks |
|----|----------|--------|
| OD-1 | UNDECIDED defects C-08, C-09, C-16, C-35, C-36, C-37, C-38, C-39, C-40, C-41 | their slices only |
| OD-2 | PBKDF2 iterations: 30,000 (configured) vs ~600,000 with a login perf carve-out | S1 login gate |
| OD-3 | SQLite vs Postgres | none now |
| OD-4 | Repo topology (measured in slice 0) | S0 |
| OD-5 | Does anyone use `/admin/`? | S8 |
| OD-6 | Rollback method (hand-back vs restore) and window | S8 |
| OD-7 | Production CORS origins; observability | S8 |
| OD-8 | Stronger token revocation | none now |

## Review first

1. **ADR-006 / DV-01 + C-16**: the key rotation forces every client to log in once. C-16 decides whether refused tokens get 403 (legacy) or 401, and whether a stale token breaks public pages.
2. **ADR-007 / OD-2**: whether to raise PBKDF2 iterations, which conflicts with ADR-000's login performance goal.
3. **ADR-003 / DV-22 + ADR-013 / OD-6**: WAL changes how operators back up the file. The rollback method decides whether writes made after cutover survive a rollback.
