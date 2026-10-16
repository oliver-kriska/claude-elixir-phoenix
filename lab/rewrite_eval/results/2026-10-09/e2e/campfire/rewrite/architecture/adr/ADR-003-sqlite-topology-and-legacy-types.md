# ADR-003: SQLite topology and legacy column types

**Status**: proposed (auto; needs approval). Corrects `kb/data-compat.md` and `kb/sqlite-on-beam.md` (`:text_datetime`).
**Date**: 2026-10-09 · **Bar**: ADR-000 (ASSUMED), Data section

## Context

- Same file in place: `/rails/storage/db/production.sqlite3`, WAL, `default_transaction_mode: immediate`, `timeout: 5000`, Rails `foreign_keys = ON` (C-01, M-54).
- C-02: datetimes are UTC text `YYYY-MM-DD HH:MM:SS[.ffffff]`, and pagination, refresh and unread compare them as text. ecto_sqlite3 0.25.0 `:iso8601` writes `T…Z`, and `:text_datetime` drops microseconds (ecto consult Q1; workspace correction in KB).
- Integer enums (C-03), string involvement (C-04), STI strings (C-05), polymorphic type strings (C-06), `has_json` settings (C-12).

## Decision

1. **Two Repos.** `Campfire.Repo` is the only writer (`pool_size: 1`, `default_transaction_mode: :immediate`, `journal_mode: :wal`, `synchronous: :normal`, `foreign_keys: :on`, `busy_timeout: 5_000` as an adapter option, never a PRAGMA, `migration_source: "ecto_schema_migrations"`). `Campfire.Repo.Read` is read-only (`read_only: true`, `mode: :readonly`, `pool_size: min(schedulers, 8)`). `Campfire.Repo.reader/0` returns the writer inside a transaction. Oban uses the writer.
2. **`Campfire.Types.RailsTime`**, a custom Ecto type, on every legacy datetime column. It dumps `%Y-%m-%d %H:%M:%S` and appends `.ffffff` only when usec > 0 (mirrors Rails `quoted_date`; probe on the pinned image). The global `datetime_type` stays `:iso8601` (Oban only).
3. **Enums and strings as stored**: `role` `[member: 0, administrator: 1, bot: 2]`; `status` `[active: 0, deactivated: 1, banned: 2]`; `involvement` atoms equal to the stored strings, nullable, and the SQL "visible" predicate is exactly `involvement != 'invisible'` (NULL excluded, as in Rails); `rooms.type` `Ecto.Enum` over `"Rooms::Open" | "Rooms::Closed" | "Rooms::Direct"`; polymorphic `record_type` as `Ecto.Enum` over the C-06 set, switching to `:string` if a probe finds other values.
4. **`accounts.settings` as `:map`** plus an accessor with defaults and lenient boolean reads. Unknown keys are preserved; no `embeds_one`.
5. **Query rules**: no `ago/2`, `from_now/2` or `datetime_add/3` on legacy columns (ecto_sqlite3 renders `%f000Z`). Cutoffs are computed in Elixir and pinned. `insert_all`/`update_all` always pass `created_at`/`updated_at`. One `now` per transaction.
6. **Short write transactions**: no HTTP, file IO, media processing, rendering or broadcasts inside a writer transaction.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| Single writer, `BEGIN IMMEDIATE`, 5 s busy budget against foreign processes (backup, sqlite3 CLI) | kept | everything |
| C-02 text format and ordering across Rails-written and port-written rows | kept | pagination, refresh, unread, Rails rollback |
| Durability of acknowledged writes: survives app crash; the last commits may be lost on power loss (`synchronous=NORMAL`) | kept (Rails 8 default, **verify** with `PRAGMA synchronous` on the pinned image) | all writers |
| C-03..C-06, C-12 encodings | kept | Rails rollback, every query |

## Alternatives

- `datetime_type: :text_datetime` (KB default). Rejected: loses microseconds and breaks ordering within one second.
- A pooled writer. Rejected: sqlite-on-beam rules 1-2.
- A hand-rolled connection owner with a statement cache. Not adopted. It needs a P2 profile showing Ecto's path is hot (performance-gates "When a Hand-Rolled Component Is Justified").

## Consequences

- Every legacy schema module sets `@timestamps_opts [type: Campfire.Types.RailsTime, inserted_at: :created_at, autogenerate: {Campfire.Types.RailsTime, :utc_now, []}]`.
- `foreign_key_constraint/3` cannot match on SQLite; contexts check existence and delete children first.
- Constraint names follow ecto_sqlite3 (`users_email_address_index`), not Rails index names.

## Validation

- Byte-compare probe: a port-written `created_at` vs a pinned-image row, for usec = 0 and usec > 0.
- A mixed Rails/port page boundary returns 40 contiguous messages (C-02 witness).
- Boot logs `sqlite_version()` and asserts FTS5 is compiled in.
- `PRAGMA` reads on the pinned image: `journal_mode`, `synchronous`, `foreign_keys`, `journal_size_limit`, `mmap_size`.
- Lint: no `ago/2`/`datetime_add/3` against legacy schemas.

## Ledger IDs

M-15, M-54, R-26, C-01, C-02, C-03, C-04, C-05, C-06, C-12, C-14, C-16
