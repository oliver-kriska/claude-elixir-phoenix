# ADR-003: Map the Prisma schema unchanged; no DDL during the observation window

**Status**: ASSUMED (`--auto`; schema ownership and rollback depend on it)
**Date**: 2026-10-09 · **Depends on**: ADR-000 A1 (Replacement), A2 (keep schema as-is)

## Context

Prisma 4.16.1 owns the schema. It has PascalCase tables, camelCase columns, SERIAL int4 PKs, `TIMESTAMP(3)` columns
without time zone, implicit m-n tables with `A`/`B` columns, renamed unique indexes (`User_email_key`,
`User_username_key`, `Article_slug_key`, `Tag_name_key`), FKs with `ON DELETE CASCADE`, a DB default for
`User.image`, and the `_prisma_migrations` history (C-01..C-10, M-16, M-17, M-18, M-25). ADR-000 makes rollback a
redeploy of the Node image against the same database. That works only if Phoenix changes no DDL and writes rows Prisma
can read. Source: ecto-schema-designer consult Q1-Q5.

## Decision

1. **Mapping.**
   - `schema "User" | "Article" | "Comment" | "Tag"`. Fields are snake_case with `source: :camelCase`.
   - Default `:id` PKs over the existing sequences. Ids are never computed.
   - Timestamps use `:utc_datetime_usec` with `autogenerate: {Realworld.Compat.Time, :now_ms, []}`, which floors to
     the millisecond at precision 6. `User` has no timestamps.
   - `User.image` is `read_after_writes: true` with no Ecto default. `demo` defaults to false and is never cast.
2. **Join tables.** Writes are schemaless `insert_all(..., on_conflict: :nothing, conflict_target: [:A, :B])` and
   `delete_all`. Reads use `many_to_many ... join_keys: [{:A, :id}, {:B, :id}]` or `EXISTS`/`count` subqueries.
   For `_UserFollows`, A = followed and B = follower, **pending V-1**.
3. **Constraints.**
   - `unique_constraint` and `foreign_key_constraint` always carry an explicit `name:`.
   - Associations use `on_delete: :nothing`, because the DB cascades (C-09).
   - Orphaned `Tag` rows stay, as they do in legacy.
4. **Repo config.** `parameters: [timezone: "UTC"]` and `migration_source: "ecto_schema_migrations"`.
5. **DDL authority during the observation window: nobody.**
   - `priv/repo/migrations/` stays empty, and there is no `Ecto.Migrator` child.
   - `Realworld.Release.migrate/0` refuses unless `ECTO_DDL_OWNER=true`.
   - `_prisma_migrations` is untouched.
   - Tests load a committed `priv/repo/structure.sql`, dumped from the four Prisma migrations applied to a
     scratch DB. A CI drift check guards it.
6. **After rollback retires:** Ecto takes ownership with a single **assert-don't-create** baseline migration.
   - On an existing DB it checks the tables, indexes and constraint names and raises on drift.
   - On a fresh DB it loads `baseline.sql`.
   - It is irreversible. `_prisma_migrations` stays until the Prisma CLI is retired for good.
   - Renaming to snake_case is a later, separate expand → contract decision.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|-----------|----------------|-----------|
| Row compatibility in both directions (Prisma reads Phoenix rows, Phoenix reads Prisma rows) | kept | Node rollback, clients |
| `TIMESTAMP(3)` UTC, same instant to the ms | kept (needs V-2 to confirm the session timezone) | clients via JSON dates |
| Sequences shared, no id collisions after rollback | kept | rollback |
| `prisma migrate status` clean after the window | kept | operators, rollback |
| Duplicate on the happy path → the legacy 422 message | kept. The race loser changes 500 → 422 (DV-02, ADR-008) | clients |
| Who may run DDL | **changed at the baseline milestone** from Prisma to Ecto (DV-14) | operators |

## Alternatives

- **Rename to snake_case during the rewrite.** Rejected: it breaks Node rollback and violates A2.
- **Let Ecto create `schema_migrations` at boot.** Rejected: a migration-less `Ecto.Migrator.run` is still DDL.
- **`:naive_datetime_usec`.** Rejected: it matches the column literally, but it invites timezone bugs at every call
  site and gives nothing back.
- **Keep Prisma as the DDL owner forever.** Rejected: it keeps a Node toolchain in operations after Node is gone.

## Consequences

- Schema changes are impossible until the window closes. Any feature that needs DDL (Oban, revocation columns)
  waits for the baseline.
- The baseline run is the **last reversible point** (architecture.md section 9).
- Legacy table names leak into Ecto code as `source:` mappings. Domain code stays snake_case.

## Validation

- Rollback rehearsal (S9): the pinned Node build runs against a DB that Phoenix has written to. `prisma migrate status`
  reports up to date, and every read endpoint returns the same JSON as for Node-written rows.
- V-1 follow-direction fixture, V-2 `SHOW timezone`, V-3 `\d "Comment"` FK names.
- Golden test: `PUT {article:{}}` bumps `updatedAt` and keeps `createdAt` (M-33).

## Ledger IDs

M-16, M-17, M-18, M-25, M-33, R-04, R-10, R-11, R-12, R-13, C-01, C-03, C-04, C-05, C-06, C-07, C-08, C-09, C-10
