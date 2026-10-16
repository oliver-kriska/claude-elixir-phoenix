# ADR-004: DDL authority — Rails-ledger migrator plus Ecto for port-only DDL

**Status**: ASSUMED (auto; needs approval). Clarifies ADR-000 Data.
**Date**: 2026-10-09

## Context

- C-55: every older released schema auto-migrates on boot with no operator step. C-01: Rails `schema_migrations` and `ar_internal_metadata` stay intact, and the pinned Rails image must still boot on a port-written file (ADR-000 rollback).
- ecto_sql 3.14 cannot write Rails' `schema_migrations(version)` table, because it inserts `inserted_at` too (ecto consult Q2).
- One Rails migration is data-critical: `20240115124901` remaps role 2 (owner) to 1 before role 2 means bot (C-03). `20251126115722` drops `users.active` (Rails' own history).

## Decision

One boot sequence, two ledgers, run by `Campfire.Release.BootMigrator` (a supervised child that returns `:ignore`) before the reader pool, Oban and the Endpoint start:

1. Open the writer only. Log `sqlite_version()`. If anything is pending, take an online backup first (`VACUUM INTO` a sibling file under `/rails/storage/backups/`).
2. **Fresh install** (no `schema_migrations`): execute a frozen `priv/repo/rails_baseline.sql` (the `.schema` of a DB created by the pinned image at `20251212154340`, including the FTS5 table). Insert all 15 Rails versions and the `ar_internal_metadata` row (`environment = production`).
3. **Existing install**: `Campfire.Release.RailsMigrator` holds a fixed ordered list of `{version, step}` for the 15 Rails versions. For each missing version it runs one `BEGIN IMMEDIATE` transaction that executes the step's SQL and inserts the version into Rails' `schema_migrations`. Steps are ported from each migration's observed effect (ecto consult table), including the `NULL → ''` digest data step and the `singleton_guard` preflight (abort with a clear message if `count(accounts) > 1`).
4. **Port-only DDL** (Oban's table, optional indexes): `Ecto.Migrator` with `migration_source: "ecto_schema_migrations"`, versions greater than `20251212154340`, additive only, port-prefixed names. Port versions are **not** mirrored into Rails' table. That table holds exactly Rails versions.
5. Start the reader Repo, then the rest of the tree.

While the rollback window is open: no destructive DDL, no column reuse, no trigger that Rails would not maintain.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| C-55 auto-migrate from any released schema, zero operator steps | kept | ONCE upgrades |
| C-01 Rails ledger intact, Rails boots afterwards with nothing pending | kept | rollback |
| C-03 owner→admin remap runs before any port code loads users | kept | admins on old installs |
| Atomic per-step migration (SQLite DDL is transactional) | kept (Rails per-migration transaction) | all installs |

## Alternatives

- Port the 15 Rails migrations as Ecto migrations in Ecto's ledger. Rejected: a second record of the same fact that can disagree with Rails' table.
- Ship Ruby in the image to run `rails db:migrate`. Rejected: the charter goal removes the Ruby runtime.
- Mirror port versions into Rails' table (ADR-000 wording option). Harmless but adds nothing. Rejected in favour of a clean split; reversible.

## Consequences

- The port owns DDL after cutover (ADR-000). Rails remains able to read the result.
- The oldest supported upgrade source must be decided (contracts Q4). The migrator covers all 15 versions back to `20231215043540`.

## Validation

- C-55 snapshot matrix: boot the port on DB snapshots from every released image tag, then boot the pinned Rails image on the result; it reports no pending migrations.
- A fresh-install DB diffed with `sqlite3 .schema` against the pinned image's fresh DB.
- A crash-injection test between two steps leaves a consistent ledger.

## Ledger IDs

M-57, R-03, C-01, C-55
