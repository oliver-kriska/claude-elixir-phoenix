# ADR-004: Legacy schema mapping and DDL authority

**Status**: proposed · **Date**: 2026-10-09

## Context
ADR-000: keep the schema as-is; DDL authority moves to Ecto at cutover; separate migration ledger; no destructive DDL without a new ADR; framework
tables left in place. FKs were declared but never enforced (Django 1.10 on SQLite); CASCADE ran in Python (M-26). Consult ecto-schema-designer Q1, Q4, Q5.

## Decision
- One Ecto schema per legacy table with exact `schema` names (architecture.md section 3); join tables have schema modules; integer PKs.
- `migration_source: "ecto_schema_migrations"`; `django_migrations` is never written.
- Migration 1 replays the legacy DDL verbatim (`CREATE TABLE IF NOT EXISTS`, `CREATE [UNIQUE] INDEX IF NOT EXISTS`, Django index names) taken from
  `sqlite3 .schema` of a legacy-built copy (VO-06). `down/0` raises.
- Release preflight before migrate: `django_migrations` (if present) holds the 10 expected app migrations; `sqlite_master.sql` for the 8 tables equals
  the baseline; refuse on mismatch.
- Later migrations are additive only until the rollback window closes (OD-6).
- Framework tables (`django_session`, `django_admin_log`, `django_content_type`, `auth_permission`, `auth_group*`, `authentication_user_groups`,
  `authentication_user_user_permissions`) stay in place, unmapped, untouched (C-53, DV-15).
- FK enforcement is ON (ecto_sqlite3 default, VO-04): every parent delete removes children first in one transaction; parent existence is checked in contexts
  (no `foreign_key_constraint/3` on SQLite).

## Guarantees
- Kept: C-01, C-04, C-42.
- Changed: FK enforcement (strengthening, DV-21) — consumers: any write path that relied on orphan tolerance (none in the API); the pre-cutover orphan
  scan (ADR-013) is mandatory. Framework-table behaviour retired (DV-15).

## Alternatives
- Ecto `create table` / `create_if_not_exists`: different DDL and index names → duplicate indexes on the live file; rejected.
- Recording the baseline as applied by hand: two code paths (fresh vs imported); rejected.

## Consequences
Dev and test databases are byte-identical in DDL to production. A hand-edited legacy schema stops the release at preflight instead of drifting.

## Validation
VO-03, VO-06; startup against a legacy-built copy performs no DDL on the 8 tables (compare `sqlite_master` before/after).

## Ledger IDs
M-40, C-01, R-12, C-42, C-53, M-26, M-15
