# ADR-003: SQLite Repo topology, journal mode and durability

**Status**: proposed (measurement-gated; nothing measured yet) · **Date**: 2026-10-09

## Context
ADR-000 keeps SQLite (`ecto_sqlite3`), single node, one writer (R-10). Legacy: Django defaults — rollback journal (not WAL), 5 s sqlite `timeout`,
autocommit (runtime.md R-10). Replacement cutover means no foreign writer at runtime; remaining foreign accessors are operator backups and the `sqlite3` CLI.
kb/sqlite-on-beam.md: a writer Repo plus a read-only reader Repo is a contention-control option, not a rule; measure it.

## Decision
- Writer `Conduit.Repo`: `pool_size: 1`, `default_transaction_mode: :immediate`, `busy_timeout: 5_000` (legacy 5 s, matched on purpose), `timeout: 15_000`,
  `queue_target`/`queue_interval` sized in slice 0. Never set `busy_timeout` by PRAGMA.
- Reader `Conduit.Repo.Read` (`read_only: true`, `mode: :readonly`, `pool_size: min(schedulers, 8)`) with `Repo.reader/0` returning the writer inside a
  transaction. **Adopted only if** the slice-0 measurement (VO-12) shows it wins or ties without busy errors against a single writer Repo. Otherwise
  every read goes through the single writer Repo. OD-4.
- `journal_mode: :wal` (change from legacy rollback journal; DV-22). `synchronous: :full`, keeping the legacy guarantee that an acknowledged write
  survives power loss; `:normal` would downgrade it silently.
- Boot logs `sqlite_version()`, `journal_mode`, `foreign_keys`.

## Guarantees
- Kept: single writer; durability of acknowledged writes (FULL); data at `db.sqlite3` (C-42).
- Changed: journal mode (WAL) — consumers: operators who copy the file (a live `cp` misses `-wal` content) → backups move to `VACUUM INTO` (ADR-012);
  rollback hand-back resets `journal_mode=DELETE` (ADR-013). Divergence DV-22 pending.

## Alternatives
- Keep rollback journal: readers block the writer during commits; viable at this load, and the fallback if DV-22 is refused.
- Pooled writers: no throughput gain on one file, risk of dirty-IO starvation (sqlite-on-beam rule 2); rejected.
- Postgres: OD-3; a separate ETL project with its own ADR.

## Consequences
DB tests run sequentially (no async sandbox on SQLite). Reads inside `Repo.transact/2` must use the writer.

## Validation
VO-12: matched slice-0 runs of (a) writer+reader and (b) single Repo on the baseline workload: busy errors, checkout queue time, p95 per route.
Kill/restart test: an acknowledged write survives a process kill.

## Ledger IDs
R-10
