# SQLite on the BEAM

SQLite access was the top bottleneck in every Campfire PR. The idiomatic base is Ecto + ecto_sqlite3 0.25.0
(on Exqlite 0.42.0, which bundles SQLite 3.53.4). SQLite runs one active write transaction per database file,
however many connections may write. **Two Repos**, a single-connection writer and a read-only reader pool, is a
contention-control option, not a universal rule: measure it against the pinned driver, the real load and every
foreign writer (the legacy app during coexistence, backups, the `sqlite3` CLI). Every rule below gives a reason.
A hand-rolled replacement needs an ADR that cites a measurement on the target OS.

## Rules

1. **Start from one writer connection: `pool_size: 1` on the writer Repo.**
   - Why: write transactions serialize per file, so a second writer connection adds no write throughput. It
     moves the queue from DBConnection, which is fair and timeout-aware, into SQLite's busy handler.
   - Coexistence adds writable connections you do not own. Test the busy path, not only the in-BEAM queue.
2. **Measure dirty-IO starvation before pooling writers.**
   - Why: a writer waiting in Exqlite's busy handler sleeps on a dirty-IO scheduler. Once more writers wait
     than there are dirty-IO threads, the lock holder cannot get a thread to `COMMIT`, and everything stalls
     until `busy_timeout` (Campfire PR #3, B2/D19). Whether it happens depends on the workload, so load-test
     a pooled writer before adopting it.
3. **`BEGIN IMMEDIATE`: set `default_transaction_mode: :immediate` on the writer.**
   - Why: a `DEFERRED` transaction starts as a reader and upgrades on its first write. If another connection
     commits in between, the upgrade fails at once with `SQLITE_BUSY` (`SQLITE_BUSY_SNAPSHOT` in WAL), and
     `busy_timeout` cannot help. The Campfire Rails app configures immediate transactions with a 5,000 ms
     timeout. Match the legacy setting on purpose, never by accident.
4. **WAL journal mode (the adapter default).**
   - Why: readers do not block the writer, and the writer does not block readers.
   - WAL needs every process on the same host. Never put the file on a network filesystem to fake multi-node
     scaling.
   - WAL is written into the file header and persists. ecto_sqlite3 sets `journal_mode: :wal` unless told
     otherwise (exqlite alone defaults to `:delete`), so the first connect converts a legacy file in place:
     `-wal`/`-shm` files appear and a plain `cp` of the live file stops being a backup. Until a ledger
     decision approves WAL, set the legacy journal mode explicitly (Conduit handoff, 2026-10-09).
5. **A read-only reader Repo: Ecto `read_only: true` plus Exqlite `mode: :readonly`, `pool_size` ≤ online
   schedulers.**
   - Why: `read_only: true` removes the write functions at compile time, and `:readonly` makes a misrouted
     write fail at the driver. You get two layers of defense in depth.
   - Readers beyond the scheduler count only add dirty-scheduler hops.
6. **Route by Repo at the call site, never by parsing SQL.**
   - Why: prefix routing sent `WITH ... UPDATE` and writable PRAGMAs to readers in Campfire PR #2 (B6/D13).
   - The caller knows its intent. `Repo.Read.all(q)` vs `Repo.insert(cs)` is explicit and greppable.
7. **Reads inside a transaction stay on the writer.**
   - Why: the reader connection cannot see the transaction's uncommitted writes, so a read through
     `Repo.Read` inside `Repo.transact/2` returns stale data. Campfire D9 was latent because two APIs looked
     alike.
   - Make the wrong thing impossible: send every read through a helper that returns the writer while
     `Repo.in_transaction?()` is true.
8. **In tests, point the reader at the writer.**
   - Why: the SQL Sandbox wraps each test in a writer transaction, so the reader cannot see test data.
   - The ecto_sqlite3 sandbox cannot run DB tests `async: true` (SQLite allows one write transaction).
     Use sequential DB cases, or separate database files for real concurrency tests.
9. **Keep write transactions short.**
   - Why: SQLite serializes every write transaction, including Oban job state changes.
   - Never hold a write transaction during HTTP calls, media conversion, rendering or broadcast fan-out.
     Commit, then do the slow part in an Oban job.
10. **Statement lifetime: reset or release every statement.**
    - Why: an open statement pins its WAL snapshot. Pinned snapshots stop checkpoints, and the `-wal` file
      grows without bound.
    - A hand-rolled statement cache resets in `after` and releases on error and on eviction. Trapping exits
      permits orderly cleanup on supervisor shutdown, but `terminate/2` is not guaranteed: essential
      native-resource cleanup must also survive an owner kill and connection teardown.
    - Watch WAL size, checkpoint lag and long-running readers.
11. **Never touch `-wal` or `-shm` from app code.**
    - Why: POSIX `fcntl` locks are per process. Closing **any** descriptor on the file releases every lock the
      process holds on it, which risks WAL corruption when another process writes (Campfire PR #5, B9).
    - Detect foreign commits with `PRAGMA data_version`. Back up with `VACUUM INTO` or the SQLite backup API,
      never `cp` of a live database.
12. **One timeout budget: `busy_timeout` < DBConnection `:timeout` < request or job timeout.**
    - Why: with one writer connection, writers queue in DBConnection, so `busy_timeout` only fires against **foreign**
      processes: the legacy app during coexistence, backups, the `sqlite3` CLI.
    - The DBConnection `:timeout` (default 15,000 ms) bounds queries and transactions. `queue_target` and
      `queue_interval` decide when a single-writer queue starts dropping checkouts. Size them on purpose.
    - Diff every default against the legacy app: Campfire PR #3 silently cut the transaction budget from
      30 s to 15 s (D18).
13. **Never set `busy_timeout` with a `PRAGMA`.**
    - Why: `PRAGMA busy_timeout` replaces Exqlite's custom busy handler (its source says so), and reading the
      PRAGMA returns 0 under that handler. Use the adapter option, and never treat the PRAGMA read as a probe.
14. **Never pin callers to readers by `:erlang.phash2(self())`.**
    - Why: hash routing (the `PartitionSupervisor` default) puts two hot callers on one busy reader while
      others sit idle. A pool hands out any idle connection.
15. **`synchronous: :normal` vs `:full` is a durability decision. Write it down.**
    - Why: in WAL mode `:normal` survives an application crash but can lose the last commits on power loss.
      WAL alone is not a durability guarantee. State what an acknowledged write survives.
16. **Check the SQLite you actually run: `SELECT sqlite_version()` at boot, logged.**
    - Why: system-linked or custom Exqlite builds (`EXQLITE_USE_SYSTEM`) differ from the bundled 3.53.4.

## Config Example

```elixir
# config/runtime.exs
db = System.fetch_env!("DATABASE_PATH")

config :app, App.Repo,
  database: db,
  pool_size: 1,
  default_transaction_mode: :immediate,
  journal_mode: :wal,
  synchronous: :normal,
  busy_timeout: 5_000,
  timeout: 30_000,
  queue_target: 500,
  queue_interval: 2_000,
  migration_source: "ecto_schema_migrations"   # only when sharing a Rails schema

config :app, App.Repo.Read,
  database: db,
  mode: :readonly,
  pool_size: min(System.schedulers_online(), 8),
  busy_timeout: 5_000

# Rails-written datetime columns: a custom Ecto type with Rails' exact text (data-compat.md),
# never datetime_type: :text_datetime (drops microseconds) or :iso8601 (writes T and Z)

config :app, Oban,
  engine: Oban.Engines.Lite,
  repo: App.Repo,                                     # always the writer
  queues: [default: 5, mailers: 2],
  pruner: [max_age: {7, :days}],
  lifeline: [rescue_after: {30, :minutes}]            # above the longest legitimate run; derive N per app
```

```elixir
defmodule App.Repo.Read do
  use Ecto.Repo, otp_app: :app, adapter: Ecto.Adapters.SQLite3, read_only: true
end

defmodule App.Repo do
  use Ecto.Repo, otp_app: :app, adapter: Ecto.Adapters.SQLite3
  @reader Application.compile_env(:app, :reader_repo, App.Repo.Read)   # App.Repo in config/test.exs

  @doc "Repo for plain reads: the writer inside a transaction, the read pool otherwise."
  def reader, do: if(in_transaction?(), do: __MODULE__, else: @reader)
end
```

Start the writer, run the migrations, then start the reader pool. A read-only connection cannot create the
database or switch it into WAL mode. The `timeout`, `queue_*`, `busy_timeout` and `rescue_after` values here
are starting points, not measured optima. Tune them against P2 profiles (performance-gates.md).

## Measure the Adapter

"Measure the adapter" does not mean "avoid DBConnection". The library pool cost Campfire throughput, and
Ecto's version of the same path was never benchmarked.

| Measurement (Linux, 4 schedulers, matched runs) | Before | After |
|-------------------------------------------------|--------|-------|
| Sidebar c16 req/s, Exqlite DBConnection read pool vs single owner | 494 | 286 (−42%); −47.3% in the matched run (462 → 243.5) |
| Sidebar CPU per successful response | 6.665 ms | 12.523 ms |
| Sidebar dirty-IO CPU per response | 1.558 ms | 5.964 ms |
| Prepare NIF calls per response (sidebar / room) | 13 / 11 | 26 / 22 |
| Pool turned off (control) | — | 508 req/s, recovered |
| Owned readers + 64-entry LRU statement cache, warm prepares | 13 → 0 | sidebar c16 +28.0% / +22.6%; room c64 p99 got **worse** (341 → 357, 363 → 396 ms) |
| Dirty signal-handler calls per sidebar response, more owners on a CPU-bound box | 44 | 848 |

- **Cause.** Exqlite's `handle_execute/4` calls `prepare` unconditionally, even right after `handle_prepare/3`,
  and release is left to `handle_close` or GC. A pooled query prepared twice and reused nothing.
- **Ecto.** ecto_sql caches the prepared query and calls `execute` on later runs. From the source, Ecto should
  pay **one prepare per execution and no statement reuse**. That is an inference, never measured, so measure
  it before claiming that Ecto is fast enough or replacing it.
- **What to count.** For any adapter or driver, count prepares per query and dirty-IO CPU per request, and
  report p99 at the highest concurrency. A hand-rolled owner design won on throughput and lost on tail latency.
- **The shape that measured well.** Check the connection out into the caller (NimblePool style, checkout <1%
  of the profile in PR #5) with a per-connection statement cache. It is a measured exception that needs an ADR
  and one test per DBConnection semantic it re-provides: caller-side errors, rollback on raise, throw and
  exit, timeouts, overload queueing.
- **Before adding owners**, confirm the single owner is the bottleneck: a long queue while schedulers have
  headroom. Campfire's room route was CPU-bound at about 3.5 of 4 CPUs, so concurrency had little left to buy.

## Oban.Engines.Lite Caveats (Oban 2.24.1)

- **Defaults.** `prefix: false`, `Oban.Notifiers.PG` (Erlang process groups, **not** PostgreSQL) and
  `Oban.Peers.Isolated`.
- **No leader election.** The isolated peer does not coordinate overlapping deploys, so cron and pruning can
  run on both instances. Give cron workers `unique:` options and avoid overlap windows. The 2.24.1 engine
  tests skip concurrent-insert uniqueness on Lite, so witness one insert per tick with two instances running.
- **Orphans.** A job running when the node dies stays `executing` until `lifeline:` (opt-in) rescues it after
  `rescue_after`, or discards it once attempts are exhausted. Lite has no rescue of its own and falls back to
  the Basic engine's query; the 2.24.1 Lifeline tests cover Basic and Dolphin. Prove recovery with a
  kill/restart witness on the real file.
- **Migrations.** Use `Oban.Migration.up/1` and `down/1` in an Ecto migration. They are adapter-aware, and the
  SQLite path creates `oban_jobs` with no Postgres schemas, triggers or peer tables. Do not copy a Postgres
  recipe.
- **Writer contention.** Every job fetch, ack, retry and prune is a write transaction, serialized with web
  request writes. Keep queue concurrency modest, and measure busy waits and checkout queue time with jobs running.
- **Delivery is at least once.** Uniqueness is not exactly-once delivery. A webhook POST that succeeded right
  before a crash runs again once the orphan is rescued, so carry an idempotency key. 2.24.1 also stops a stale
  execution from overwriting a newer ack (all engines).
- **Same database file.** Keep `oban_jobs` in the same file as the domain data, or you lose the atomic
  enqueue in `Ecto.Multi`. A separate jobs file lowers contention but costs that guarantee.
- **Backups.** Backups now contain jobs, and a restore can replay work that was already sent. Recovery runbooks
  must say how duplicates are handled.
- **Repo.** Oban uses the writer Repo, never `Repo.Read`.

## ecto_sqlite3 Limitations to Plan For

- **`foreign_key_constraint/3` may not work.** SQLite reports no constraint name. Validate existence in the
  context, or rescue and map the error explicitly.
- **Check constraints exist only at the column level** (`add :x, :t, check: %{name: ..., expr: ...}`).
  `Ecto.Migration.constraint/3` cannot add one later.
- **Schemaless queries return raw storage classes.** Map the types yourself, or use schemas.
- **Equality is case-sensitive.** Use `collate: :nocase` (ASCII only) or normalize in the changeset.
  `LIKE` is case-insensitive unless `case_sensitive_like: :on`.
- **Type options are global.** `datetime_type`, `binary_id_type`, `uuid_type`, `map_type` and `array_type` are
  read from `config :ecto_sqlite3` app env in 0.25.0, so they apply to every Repo. Neither `datetime_type` value
  reproduces Rails' `YYYY-MM-DD HH:MM:SS.ffffff` text; legacy columns need a custom type (data-compat.md).
- **`ALTER TABLE` is limited.** Many schema changes need a table rebuild. Rehearse them on a copy.

## When to Move to Postgres

Move when one of these holds, and treat the move as its own project with its own data-compat plan:

- More than one node must write. SQLite's single file never spans hosts.
- Writer contention persists after the request-work fixes: sustained `busy` errors, checkout queue time
  growing with load, or job throughput limited by the writer.
- The design needs `LISTEN/NOTIFY` for non-BEAM consumers, row-level locks, `SELECT ... FOR UPDATE SKIP
  LOCKED`, read replicas, or Oban's Postgres peer for leader election.
- The working set or the write volume outgrows one disk, or backup windows no longer fit.

Stay on SQLite when it is the **product contract**: a single-node appliance whose operators back up one file
(Campfire, a Replacement cutover). Then the rules above are the architecture, and the Postgres move is a separate migration
with its own ADR.
