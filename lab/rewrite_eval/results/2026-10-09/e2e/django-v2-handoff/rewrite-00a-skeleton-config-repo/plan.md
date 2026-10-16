# Plan: Rewrite slice 00a — Skeleton, config, Repo

**Status**: READY
**Date**: 2026-10-09
**Depth**: standard
**Source**: `.claude/plans/rewrite-00a-skeleton-config-repo/interview.md` (rewrite seed, Status COMPLETE)
**Exit gate**: `/rewrite:verify 00a`
**Next slice**: 00b (legacy data layer)

## Summary

Generate a Phoenix 1.8.15 JSON-only app `conduit` in this workspace and strip the generator
defaults that ADR-001 rules out. Configure it from fail-closed runtime env, and open the SQLite
file through one writer Repo with legacy durability. Add a synchronous boot check that fences
foreign writers and logs the PRAGMAs. Put Corsica in the Endpoint and secure headers on the
`:api` pipeline. No routes and no domain code yet.

## Research notes (verified against hex source, 2026-10-09)

The interview's research came from the rewrite artifacts. I checked the dependency versions and
defaults against the published package source. No agents were spawned; the seed already holds the
design research. Full notes: `.claude/research/2026-10-09-00a-dependency-defaults.md`.

| Finding | Source | Effect on the plan |
|---------|--------|--------------------|
| hex.pm latest: phoenix 1.8.15, bandit 1.12.5, ecto_sql 3.14.0, ecto_sqlite3 0.25.0, jason 1.4.5, corsica 2.1.3 (exqlite 0.42.0 transitive) | hex.pm API | ADR-001 versions are current; pin them |
| **ecto_sqlite3 0.25 sets `journal_mode: :wal` by default** (`Keyword.put_new` in `Connection.default_opts/1`). WAL is stored in the file, so one connect converts the legacy file | `ecto_sqlite3/lib/ecto/adapters/sqlite3/connection.ex:23` | Set `journal_mode: :delete` explicitly until DV-22 is approved (see Decision P-1) |
| exqlite defaults: `synchronous: :normal`, `busy_timeout: 2000`, `foreign_keys: :on`, transaction mode `deferred` | `exqlite/lib/exqlite/connection.ex`, `pragma.ex` | Set `:full`, `5_000` and `:immediate` explicitly; set `foreign_keys: :on` explicitly too (resolves VO-04: the default is ON) |
| `busy_timeout` is applied through the NIF, not PRAGMA (a PRAGMA would remove exqlite's busy handler) | `exqlite connection.ex:540` | Matches ADR-003 "never set busy_timeout by PRAGMA". Reading `PRAGMA busy_timeout` is still fine |
| phx_new 1.8.15 sqlite template adds `{Ecto.Migrator, skip: skip_migrations?()}`, which **runs migrations at release boot**; it also adds `DNSCluster` and `Phoenix.PubSub` | `phx_new templates/phx_single/lib/app_name/application.ex.eex` | Remove all three (C-42, ADR-001) |
| The phx_new sqlite prod config reads `POOL_SIZE` (default 5) | `phx_new lib/phx_new/generator.ex:445` | Replace it with a fixed `pool_size: 1` |
| Endpoint template keeps `Plug.Session` even with `--no-html` | `phx_new templates/phx_web/endpoint.ex.eex:53` | Remove it (M-32: no sessions/CSRF) |
| Corsica plug options are compiled in; origins accept `{mod, fun, args}`, called as `fun(conn, origin, ...args)` | `corsica/lib/corsica.ex:288` | Runtime origins via an MFA that reads app env |
| Phoenix 1.8.15 `put_secure_browser_headers` sends `referrer-policy`, `content-security-policy: base-uri 'self'; frame-ancestors 'self';`, `x-content-type-options`, `x-permitted-cross-domain-policies`. **No `x-frame-options`** | `phoenix/lib/phoenix/controller.ex:1410` | Tests assert these four headers. DV-13's wording ("includes x-frame-options") is stale (see Open Questions) |
| Router pipelines compile to public `def api(conn, _)` | `phoenix/lib/phoenix/router.ex:968` | The secure-header test can call `ConduitWeb.Router.api/2` without adding a non-C-17 route |
| Local toolchain: Elixir 1.20.4 / OTP 29; phx_new archive **1.8.0**; hex archive built for OTP 28 | `elixir --version`, `~/.mix/archives` | Phase 0 upgrades both |

## Plan decisions (made while planning; flagged for the user)

- **P-1: Ship the legacy rollback journal (`journal_mode: :delete`) in 00a.** DV-22 (WAL) is
  pending. ecto_sqlite3 would silently switch the file to WAL, and that change persists in the file
  and alters the operator backup procedure. This keeps the R-10 guarantee as-is. Flipping to WAL
  after DV-22 is approved is a one-line config change, made in the slice that approves it.
  This answers the interview's open question "should 00a ship WAL or the legacy rollback journal?"
- **P-2: `Conduit.Boot` runs synchronously as a child `start` function and returns `:ignore`.**
  The architecture describes "a one-shot Task (restart: :temporary)", but a crashed temporary Task
  does not stop the application. That breaks the §10 fencing rule ("boot refuses to start").
  `start: {Conduit.Boot, :run, [[]]}` with `restart: :temporary` runs the check before the
  Endpoint starts. Success leaves no process behind (`:ignore`). Failure returns `{:error, reason}`,
  so the supervisor and the release fail to start.
- **P-3: CORS allow-headers use the legacy django-cors-middleware 1.x default list**, not only
  `authorization` and `content-type`: `x-requested-with, content-type, accept, origin, authorization,
  x-csrftoken, user-agent, accept-encoding`. Also `max_age: 86_400` (legacy default). ADR-011 says
  the list must "include" the two headers, so a superset satisfies it, and C-31 is a "keep"
  contract. A narrower list could break a RealWorld frontend that sends `x-requested-with`.
  Verify the list against the legacy pinned version during work. Fall back to ADR-011's two headers
  if the user prefers.
- **P-4: Extra fail-closed rules beyond the seed.** `JWT_SECRET_PREVIOUS`, when set, must be ≥32
  bytes. `JWT_SECRET` must differ from `SECRET_KEY_BASE` (ADR-011 "separate"). `PORT` must parse
  as an integer between 1 and 65535. Each `CORS_ORIGINS` entry must be a full `http`/`https`
  origin with no path.
- **P-5: Durability options live in `config/config.exs`**, so dev, test and prod open the database
  the same way. Only `database` (and the sandbox pool in test) differs per env. This lets the
  PRAGMA test in `mix test` stand as evidence for prod.

## Phase 0: Toolchain [setup]

- [ ] Install the matching generator: `mix archive.install hex phx_new 1.8.15 --force` (local is 1.8.0)
- [ ] `mix local.hex --force` (the installed hex archive targets OTP 28; the runtime is OTP 29)

## Phase 1: Skeleton [phoenix]

- [ ] Generate into a scratch dir, then copy into the workspace root without touching `.git/` or `.claude/`:
  `mix phx.new /tmp/conduit-gen --app conduit --module Conduit --no-html --no-assets --no-live --no-mailer --no-dashboard --no-gettext --database sqlite3 --no-install`,
  then `rsync -a /tmp/conduit-gen/ ./` (check first that no target file exists outside `.claude/`)
- [ ] `mix.exs` deps: pin `phoenix ~> 1.8.15`, `bandit ~> 1.12.5`, `ecto_sql ~> 3.14.0`, `ecto_sqlite3 ~> 0.25.0`,
  `jason ~> 1.4.5`; add `{:corsica, "~> 2.1.3"}`; **remove `:dns_cluster`**. Keep `phoenix_ecto`,
  `telemetry_metrics` and `telemetry_poller` as generated. Do not add Joken or pbkdf2 (02a/02b)
- [ ] `lib/conduit/application.ex`: delete the `Ecto.Migrator` child and `skip_migrations?/0`, `DNSCluster`,
  `Phoenix.PubSub` and the worker comment. Final children: `ConduitWeb.Telemetry`, `Conduit.Repo`,
  `Conduit.Boot`, `ConduitWeb.Endpoint`
- [ ] `config/config.exs`: remove `pubsub_server: Conduit.PubSub` from the Endpoint config
- [ ] `lib/conduit_web/endpoint.ex`: remove `@session_options`, `Plug.Session` and the commented
  LiveView socket. Keep `Plug.RequestId`, `Plug.Telemetry`, `Plug.Parsers` (json), `Plug.MethodOverride`,
  `Plug.Head` and the router
- [ ] `mix deps.get` and commit `mix.lock`. `mix compile --warnings-as-errors` is clean
- [ ] Ledger deletes R-02 (wsgi), M-03 (signal registration), M-35 (django_extensions), M-37
  (`ProfileDoesNotExist`) and R-13 (LocMemCache): **nothing is ported**. Grep the new tree for
  `wsgi|signal|extensions|ProfileDoesNotExist|Cachex|:ets` → no hits

## Phase 2: Runtime config, fail-closed [config]

- [ ] `config/config.exs` — shared, non-secret:
  ```elixir
  config :conduit, ecto_repos: [Conduit.Repo]

  config :conduit, Conduit.Repo,
    pool_size: 1,
    default_transaction_mode: :immediate,
    busy_timeout: 5_000,
    timeout: 15_000,
    synchronous: :full,
    foreign_keys: :on,
    # DV-22 pending: ecto_sqlite3 defaults to :wal, which persists in the file.
    journal_mode: :delete

  config :conduit, :cors_origins,
    ~w(http://localhost:4000 https://localhost:4000 http://0.0.0.0:4000 https://0.0.0.0:4000)
  ```
  Leave `queue_target`/`queue_interval` at their defaults. Slice 01 sizes them alongside VO-12
- [ ] `config/dev.exs`: `database: Path.expand("../priv/repo/dev.db", __DIR__)`, `debug_errors: true`
  (dev only). Use an obviously fake `secret_key_base` (`"dev-only-not-secret-" <> String.duplicate("x", 44)`)
  and `config :conduit, :jwt, secret: "dev-only-not-secret-jwt-key-000000"`. Delete the generated
  random `secret_key_base`
- [ ] `config/test.exs`: sandbox pool (`pool: Ecto.Adapters.SQL.Sandbox`, `pool_size: 1` inherited),
  `database: Path.expand("../priv/repo/test.db", __DIR__)`, fake secrets as in dev, `debug_errors: false`,
  `server: false`
- [ ] `config/prod.exs`: no secrets, no `debug_errors`. Keep the generator's `force_ssl`/logger lines only
  if they do not reference unset env
- [ ] `config/runtime.exs`, inside `if config_env() == :prod`:
  - `System.fetch_env!/1` for `JWT_SECRET`, `SECRET_KEY_BASE`, `DATABASE_PATH`, `PHX_HOST`, `PORT`. The
    `raise` message names the variable and the rule, never the value
  - `JWT_SECRET` ≥32 bytes, `SECRET_KEY_BASE` ≥64 bytes (`byte_size/1`), `JWT_SECRET != SECRET_KEY_BASE`,
    optional `JWT_SECRET_PREVIOUS` ≥32 bytes when set (P-4)
  - `DATABASE_PATH` must be absolute (`Path.type/1 == :absolute`; ADR-011 "no relative default")
  - `PORT` → `Integer.parse/1`, 1..65535
  - `CORS_ORIGINS` (optional): split on `,`, trim, reject any `*`, require `URI.parse` scheme `http`/`https`,
    a host, and no path/query; unset → keep the config.exs defaults
  - Set `Conduit.Repo` `database:`; Endpoint `url: [host: PHX_HOST, port: 443, scheme: "https"]`,
    `http: [ip: {0, 0, 0, 0, 0, 0, 0, 0}, port: PORT]`, `secret_key_base:`; set
    `config :conduit, :jwt, secret: ..., previous: ...` (stored for 02a; nothing reads it yet)
  - Keep `PHX_SERVER` handling as generated. Delete `POOL_SIZE` and `DNS_CLUSTER_QUERY`
- [ ] Check that no secret goes through `Application.compile_env`: `rg -n compile_env lib config` → no secret keys
- [ ] `test/conduit/runtime_config_test.exs` (`async: false`): evaluate the real file with
  `Config.Reader.read!("config/runtime.exs", env: :prod)` against a valid baseline env set by
  `System.put_env/1`, restored in `on_exit`. One test per witness, each asserting that the
  `RuntimeError`/`ArgumentError` message names the variable:
  - missing `JWT_SECRET`; `JWT_SECRET` of 31 bytes; missing `SECRET_KEY_BASE`; `SECRET_KEY_BASE` of 63 bytes
  - missing `DATABASE_PATH`; relative `DATABASE_PATH`; missing `PHX_HOST`; missing `PORT`; `PORT=abc`
  - `CORS_ORIGINS=*`; `CORS_ORIGINS=http://a.test,*`; `CORS_ORIGINS=localhost:4000` (no scheme)
  - `JWT_SECRET_PREVIOUS` of 10 bytes; `JWT_SECRET == SECRET_KEY_BASE`
  - happy path: every value lands in the returned config; `CORS_ORIGINS` unset → key absent (defaults stay);
    `CORS_ORIGINS` set → list replaced
- [ ] `test/conduit/debug_config_test.exs`: `ConduitWeb.Endpoint.config(:debug_errors)` is falsy in test, and
  `Config.Reader.read!("config/config.exs", env: :prod)` yields no `debug_errors: true` for the Endpoint (D-06, C-34)

## Phase 3: Writer Repo and boot check [ecto]

- [ ] `lib/conduit/repo.ex`: generator default (`use Ecto.Repo, otp_app: :conduit, adapter: Ecto.Adapters.SQLite3`).
  No GenServer wrapper, no reader Repo (OD-4 → slice 01)
- [ ] `lib/conduit/boot.ex` (P-2):
  ```elixir
  def child_spec(opts),
    do: %{id: __MODULE__, start: {__MODULE__, :run, [opts]}, restart: :temporary}

  # Runs synchronously before the Endpoint. :ignore on success leaves no process.
  def run(opts \\ []) do
    repo = Keyword.get(opts, :repo, Conduit.Repo)
    Conduit.Repo.put_dynamic_repo(repo)

    with :ok <- fence(),
         {:ok, info} <- pragmas() do
      Logger.info("sqlite boot: version=#{info.version} journal_mode=#{info.journal_mode} foreign_keys=#{info.foreign_keys}")
      :ignore
    end
  end
  ```
  - `fence/0`: `Conduit.Repo.transact(fn -> {:ok, :fenced} end)`. With `default_transaction_mode: :immediate`
    this issues `BEGIN IMMEDIATE`, which takes the RESERVED lock and waits `busy_timeout`. Rescue **only**
    `Exqlite.Error` whose message is `database is locked` / `busy` → `{:error, {:database_locked, path}}`.
    Let every other error propagate
  - `pragmas/0`: `SELECT sqlite_version()`, `PRAGMA journal_mode`, `PRAGMA foreign_keys` via `Repo.query!/1`
  - No DDL and no migration. It only reads
- [ ] `test/conduit/repo_test.exs` (`async: false`), through the sandbox connection:
  - `Conduit.Repo.config()[:pool_size] == 1` and `[:default_transaction_mode] == :immediate`
  - `PRAGMA busy_timeout` → `5000`; `PRAGMA synchronous` → `2`; `PRAGMA foreign_keys` → `1`; `PRAGMA journal_mode` → `"delete"`
- [ ] `test/conduit/boot_test.exs` (`async: false`), on a temp file (`System.tmp_dir!/0` + unique name) with a
  dynamic repo `Conduit.Repo.start_link(name: nil, database: tmp, pool: DBConnection.ConnectionPool, busy_timeout: 200)`:
  - unlocked: `Conduit.Boot.run(repo: pid)` → `:ignore`; `capture_log` contains `version=`, `journal_mode=delete`, `foreign_keys=1`
  - fenced: a raw `Exqlite.Sqlite3.open(tmp)` connection runs `BEGIN IMMEDIATE` first → `run/1` returns
    `{:error, {:database_locked, _}}` within ~200 ms. Release the lock in `on_exit`
  - no migration: after `run/1`, `sqlite_master` has no `schema_migrations` and no `ecto_schema_migrations` table
- [ ] `test/conduit/application_test.exs`: `Supervisor.which_children(Conduit.Supervisor)` ids are exactly
  `ConduitWeb.Endpoint`, `Conduit.Repo` and `ConduitWeb.Telemetry` (Boot returned `:ignore`). No `Ecto.Migrator`,
  `Phoenix.PubSub`, `DNSCluster`, `Agent`, cache or user GenServer

## Phase 4: Web edge — CORS and `:api` pipeline [phoenix]

- [ ] `lib/conduit_web/cors.ex`: `def allowed_origin?(_conn, origin), do: origin in Application.fetch_env!(:conduit, :cors_origins)`
- [ ] `lib/conduit_web/endpoint.ex`, after `Plug.Telemetry` and before `Plug.Parsers`:
  ```elixir
  plug Corsica,
    origins: {ConduitWeb.CORS, :allowed_origin?, []},
    allow_headers: ~w(x-requested-with content-type accept origin authorization x-csrftoken user-agent accept-encoding),
    allow_methods: ~w(GET POST PUT PATCH DELETE OPTIONS),
    allow_credentials: false,
    max_age: 86_400
  ```
  (P-3: verify the header list against the legacy pinned `django-cors-middleware` before finalising)
- [ ] `lib/conduit_web/router.ex`:
  ```elixir
  pipeline :api do
    plug :accepts, ["json"]
    plug :put_secure_browser_headers
  end

  scope "/api", ConduitWeb do
    pipe_through :api
  end
  ```
  No routes (00c owns the router table). No CSRF, session or fetch_flash plugs
- [ ] `test/conduit_web/cors_test.exs` (`async: false` where `Application.put_env` is used), via `ConnCase`:
  - for each of the four default origins: `OPTIONS /api/articles` with `origin`,
    `access-control-request-method: POST` and `access-control-request-headers: authorization` → 200,
    `access-control-allow-origin` = origin, allow-headers contains `authorization`,
    **no** `access-control-allow-credentials` header, and no token required (C-31, VO-09)
  - `origin: http://evil.test` → no `access-control-allow-origin`
  - `origin: http://localhost:4001` → refused (port is part of the origin)
  - runtime override: `Application.put_env(:conduit, :cors_origins, ["https://app.test"])` → that origin
    is allowed and `http://localhost:4000` is refused; restore in `on_exit`
- [ ] `test/conduit_web/router_test.exs`:
  - `ConduitWeb.Router.api(build_conn(), [])` sets `content-security-policy`, `x-content-type-options: nosniff`,
    `referrer-policy` and `x-permitted-cross-domain-policies` (DV-13)
  - `Phoenix.Router.routes(ConduitWeb.Router) == []`: no HTML, LiveView or dashboard routes

## Phase 5: Verification [verify]

- [ ] `mix format --check-formatted`
- [ ] `mix compile --warnings-as-errors` (after `rm -rf _build` to simulate a fresh checkout)
- [ ] `mix test` (all DB tests are sequential; ADR-003)
- [ ] `mix phx.routes` → no routes listed
- [ ] Secret scan: `rg -n "SECRET_KEY\s*=|secret_key_base:\s*\"[A-Za-z0-9+/]{40,}" config lib` → only the
  obviously fake dev/test values; the legacy committed key never appears (X-04)
- [ ] Translationese probes (`.claude/rewrite/kb/translationese-checks.md`): no `GenServer`/`Agent` around Repo,
  no `Process.put`, no mirrored `apps/*` tree
- [ ] Release smoke (manual, scratch file only, **never the real legacy `db.sqlite3`**):
  - `sqlite3 /tmp/conduit-smoke.db "create table t(x);"` then `MIX_ENV=prod mix release`
  - start with a full env → the log shows `sqlite boot: version=… journal_mode=delete foreign_keys=1`;
    `curl -i -X OPTIONS localhost:$PORT/api/articles -H 'origin: http://localhost:4000' -H 'access-control-request-method: GET' -H 'access-control-request-headers: authorization'` → ACAO set
  - unset `JWT_SECRET` → the release exits non-zero and the error names `JWT_SECRET`
  - hold `BEGIN IMMEDIATE` in a `sqlite3` shell on the file → the release refuses to start after ~5 s (fencing)
  - after the smoke run, `sqlite3 /tmp/conduit-smoke.db .tables` shows only `t` (no migration at boot)

## Acceptance criteria → evidence map

| Criterion (interview) | Evidence |
|-----------------------|----------|
| compile `--warnings-as-errors` + `mix test` on a fresh checkout | Phase 5 |
| boots with the full env; no HTML/LiveView/dashboard routes | release smoke; `router_test` routes == [] |
| each missing/invalid var → message names it | `runtime_config_test` |
| pool_size 1, busy_timeout 5000, synchronous 2, BEGIN IMMEDIATE | `repo_test`; fencing in `boot_test` |
| boot logs sqlite_version, journal_mode, foreign_keys | `boot_test` capture_log; smoke log |
| preflight allowed from :4000, refused for evil.test, no credentials | `cors_test` |
| `/api` responses carry the secure headers | `router_test` (pipeline) |
| no migration at boot | `boot_test` table check; `application_test` (no Migrator); smoke `.tables` |
| no GenServer/Agent/cache beyond framework defaults | `application_test` |
| C-44 witnesses (one test per var) | `runtime_config_test` |
| C-42 (00a part) | no-migration checks above |

## Risks

- **WAL deferred (P-1).** Readers block the writer during commits on the rollback journal. At the
  legacy load this is acceptable, and VO-12 measures it in slice 01. If DV-22 is approved, flip
  `journal_mode` in `config.exs` and add the WAL/backup rehearsal (slice 09).
- **The CORS header list (P-3) is unverified** against the exact legacy package version. A wrong list
  shows up as failed preflights from a frontend, not as a test failure.
- **Sandbox with `pool_size: 1`.** Tests that spawn processes need `Sandbox.allow/3` or shared mode.
  The generator's `ConnCase`/`DataCase` already use shared mode for non-async tests.
- **The test DB is a fresh file, not the legacy schema.** PRAGMA evidence is per connection, so this
  is valid for prod. Schema compatibility belongs to 00b.

## Open questions (carried; none block 00a work)

- Approve or redirect **P-1** (rollback journal now, WAL after DV-22) and **P-3** (legacy header list).
- **DV-13 wording is stale:** Phoenix 1.8.15 sends no `x-frame-options`. `content-security-policy:
  frame-ancestors 'self'` covers the legacy `SAMEORIGIN`. Update DV-13 during `/rewrite:verify 00a`.
- **OD-7:** production CORS origins are unknown; the :4000 defaults are dev-only.
- ADR-000 / ADR-001 / ADR-003 / ADR-011 are still ASSUMED or proposed. `/rewrite:verify` does not count ASSUMED.
- Boot no longer needs a VO-04 check: exqlite 0.42 defaults `foreign_keys` to ON, and 00a sets it explicitly.
  DV-21 (pre-cutover orphan scan) still stands.
