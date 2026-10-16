# Go → Elixir

Covers `net/http` services, Gin/Echo/Fiber/chi, goroutines, channels and mutexes, sqlc/GORM/pgx, worker pools, asynq/River jobs and gRPC.
Read it alongside the verdict vocabulary (MAP, REPLACE, KEEP, SHIM, DELETE, UNDECIDED) and the reason tags in the elixir-way SKILL.md.
Go has real concurrency but no supervision, isolation or distribution. Most mechanisms below make up for those three gaps.

## Probe: where mechanisms hide

| Look at | What it reveals | Contract or purpose to capture |
|---|---|---|
| `cmd/*/main.go`, Dockerfiles, k8s Deployments and CronJobs, `Makefile` targets | Binaries and process roles (api, worker, scheduler, migrator), replica counts | Why each role is separate (isolation, scaling, deploy cadence) and which can share one release |
| `go.mod` `require` block | Router, ORM, queue, Redis, resilience and auth libraries in use | The mechanism inventory; mark each library with the row below that covers it |
| `http.Server{`, `ReadTimeout`, `WriteTimeout`, `IdleTimeout`, `MaxHeaderBytes`, `http.MaxBytesReader(` | Server limits | Timeout and body-size behavior clients observe (408, 413, dropped connections) |
| `.Use(`, `func(next http.Handler) http.Handler`, `r.Group(`, `r.Route(`, `gin.Default()`, `gin.New()` | Middleware order and implicit middleware | `gin.Default()` adds Logger and Recovery; auth, CORS and request-id order |
| `HTTPErrorHandler`, `AbortWithStatusJSON(`, Fiber `ErrorHandler:`, `errors.Is(`, `errors.As(`, sentinel `var Err` | Error mapping | Status codes and error bodies per error type |
| `Prefork:`, `fasthttp`, `c.Locals(` | Fiber runtime choices | Multi-process mode, request-local state |
| `ShouldBind`, `binding:"`, `validate:"`, `validator.New(` | Validation rules | Required fields, formats, the error format clients parse |
| `json:"` tags with `omitempty`, `,string`, `"-"`; nil slices returned from handlers; custom `MarshalJSON` | Wire shape | Missing vs `null` vs `[]`, ids as strings, time formats |
| `go func`, `errgroup.`, `sync.WaitGroup`, `SetLimit(`, `ctx.Done()`, `for {` + `select {` | Goroutine lifecycles | Who starts and stops each goroutine, what it owns, what happens when it panics |
| `context.WithTimeout(`, `WithDeadline(`, `WithCancel(`, `context.WithValue(`, `ctx.Value(` | Deadlines, cancellation, implicit values | Deadlines that are SLOs; user, tenant or request id passed implicitly |
| `sync.Mutex`, `RWMutex`, `sync.Map`, `atomic.`, `sync.Once`, `sync.Pool`, `singleflight`, `semaphore.NewWeighted(` | Shared state and coordination | Which guarded structures are the source of truth and which are caches of the DB |
| `make(chan`, buffered channel sizes, `time.NewTicker(`, `time.Tick(`, `time.AfterFunc(` | Pipelines, worker pools, timers | Work held only in memory (lost on crash today), intervals, backpressure bounds |
| `defer func()` + `recover()` | Panic shields | Where a panic would otherwise kill the whole binary |
| `sqlc.yaml`, `query.sql`, `-- name:` annotations | Hand-written query inventory | Every query the service runs, with result cardinality (`:one`, `:many`, `:exec`) |
| `gorm.Model`, `DeletedAt`, `AutoMigrate(`, `BeforeCreate`, `AfterSave`, `Preload(`, `TableName()` | GORM implicit behavior | Soft-delete filters, hook side effects, naming, whether production uses AutoMigrate |
| `migrations/*.sql`, goose, golang-migrate, `atlas.hcl` | DDL history and owner | Baseline point; the version table to leave alone during overlap |
| `pgxpool.`, `SetMaxOpenConns(`, `SetMaxIdleConns(`, `SetConnMaxLifetime(` | Connection pools | Total connection budget across legacy plus Elixir |
| `asynq.NewServer(`, `asynq.Unique(`, `MaxRetry(`, `ProcessIn(`, `Timeout(`, `Queues:`, `NewScheduler(`, `river.` | Job topology | Retries, uniqueness TTLs, priorities, timeouts, periodic tasks, producers outside Go |
| `redis.NewClient(`, `redsync`, `SetNX(`, `Publish(`, `Subscribe(`, NATS `nats.Connect(` | Redis and NATS uses | One row per use, and whether another service shares the keys or subjects |
| `gobreaker`, `backoff.Retry(`, `retry-go`, `retryablehttp`, `rate.NewLimiter(`, `http.Client{Timeout` | Resilience | Per-upstream timeouts, retry counts, rate limits; clients with no timeout |
| `*.proto`, `grpc.NewServer(`, `RegisterXServer(`, grpc-gateway annotations | Service contracts | Which peers are internal (merge) and which are external (KEEP) |
| `websocket.Upgrader`, `hub.go`, `register` / `unregister` / `broadcast` channels | Realtime hub | Message JSON, room naming, client platforms and update policy |
| `golang-jwt`, `jwt.Parse(`, `securecookie`, `scs.`, `bcrypt.` | Auth artifacts | Token algorithms, keys, claims, cookie names, hash formats |
| `viper.`, `envconfig`, `flag.`, `os.Getenv(` | Config surface | Env var names that manifests already set |
| `//go:embed`, `template.ParseFS(`, templ components | Embedded assets and templates | Files compiled into the binary |

## Mechanism map

| Legacy mechanism | Usual purpose (why) | Reason tags | Default verdict → Elixir way | Literal-translation trap | Cutover / compat note |
|---|---|---|---|---|---|
| Several `cmd/` binaries (api, worker, scheduler) | Separate deployables because a crash or leak in one role must not take down the others | reliability, platform | REPLACE → one OTP release; roles as supervision subtrees enabled by config (`server: true` per endpoint, Oban queues per node) | One Elixir app per binary talking HTTP to each other | Keep separate deployments only for different load profiles; select the role with an env var |
| `http.Server` timeouts, `MaxBytesReader` | Bound slow clients and large bodies | business | MAP → Bandit `thousand_island_options: [read_timeout: ...]`, `Plug.Parsers` `length:` | Per-route timeout plugs | Keep 408 and 413 behavior |
| `ServeMux` (Go 1.22 `GET /items/{id}`), Gin/Echo/chi routers and groups | Routing | business | MAP → Phoenix router `scope`s, `~p` verified routes | Generating routes by reflection or by walking packages | A pattern ending in `/` matches the whole subtree, and `/x` 301-redirects to `/x/`: use explicit `"/*path"` globs and redirects |
| Middleware `func(http.Handler) http.Handler`, `.Use(` | Cross-cutting concerns in order | business | MAP → Plug pipeline in the endpoint and router | Middleware as GenServers | Preserve order; trust proxy headers (`RealIP`) explicitly |
| Gin Recovery, `defer recover()` in handlers and goroutines | A panic in any goroutine kills the whole program | platform | DELETE → a crash ends only its process; Plug renders a 500; supervisors restart children | `try/rescue` wrappers everywhere; rescuing inside every Task | Keep the 500 body shape |
| `AbortWithStatusJSON`, Echo `HTTPErrorHandler`, Fiber `ErrorHandler`, sentinel errors | Map errors to responses | contract | MAP → `{:error, reason}` + `with` + FallbackController; `Plug.Exception` for exceptions | Bare `{:error, "string"}` everywhere; one error struct per package | Keep status codes and the envelope byte-compatible |
| Fiber `Prefork: true` (SO_REUSEPORT processes) | Use cores with fasthttp | platform | DELETE → schedulers use every core | Several BEAM nodes per host | none |
| Fiber/fasthttp request reuse, `c.Locals` | Raw throughput, request-local state | platform | MAP → Bandit + Plug, `conn.assigns`; measure before tuning | Pooling request structs (fasthttp habit) | none |
| Struct tags + go-playground/validator, `ShouldBindJSON` | Boundary validation | business | REPLACE → schemaless or embedded changesets; open_api_spex when a spec exists | One struct + validator + mapper per endpoint | Gin binding errors have their own text; keep it if clients parse it |
| `encoding/json` tags (`omitempty`, `,string`, `-`) | Wire shape | contract | MAP → explicit JSON view functions | `@derive Jason.Encoder` on schemas | `omitempty` drops `0`, `""`, `false` and nil; nil slices encode as `null`, empty ones as `[]`; `time.Time` is RFC 3339 with a trimmed fraction; `<>&` become `<`-style escapes (mask in byte diffs) |
| `context.Context` cancellation and deadlines | Stop abandoned work, propagate deadlines | platform | REPLACE → map each deadline and cancellation path explicitly: owned cancellable tasks (`Task.Supervisor.async_nolink` + `Task.shutdown/2`), a cancellation message the worker checks, or driver timeouts whose server-side effect you verified (Req `receive_timeout`). A `GenServer.call` timeout stops the caller waiting, not the server's work; a monitor reports a death and cancels nothing; a normal exit does not stop linked processes | Threading a `ctx` map through every function; assuming a call timeout cancels | Client-visible deadlines (504 vs 503) and drain requirements are contract. Test cancellation while work is queued, executing and committing an effect |
| `context.WithValue` for user, tenant, request id | Implicit request context | platform | REPLACE → explicit `%Scope{}`, `conn.assigns`, Logger metadata | The process dictionary as a context store | Pass ids into Oban args explicitly |
| `go func(){}()` fire-and-forget | Don't block the response | reliability, platform | REPLACE → `Task.Supervisor.start_child` (ephemeral) or Oban (durable) | Bare `spawn`/`Task.start` (Iron Law 14) | Capture locale and OTel context first (Iron Law 25) |
| Long-lived goroutines (`for { select { case <-ticker.C: ...; case <-ctx.Done(): } }`) | Pollers, refreshers, consumers | reliability, platform | REPLACE → a supervised GenServer only when it owns state or a timer; external-queue pollers → Broadway; cluster-wide periodic work → Oban cron | One GenServer per goroutine regardless of need | Run only one poller across legacy and Elixir during overlap |
| `sync.WaitGroup`, `errgroup.WithContext`, `SetLimit(n)` | Bounded parallel fan-out, fail-fast | business | MAP → `Task.Supervisor.async_stream_nolink(sup, xs, f, max_concurrency: n, timeout: ms, on_timeout: :kill_task)`; linked `Task.async_stream` for errgroup fail-fast | `async_stream` with `timeout: :infinity` and no supervisor; `max_concurrency` above the Finch pool | Size the limit to the downstream pool and quota |
| Worker pool: N goroutines reading a jobs channel | Bound concurrency against a resource | reliability, platform | REPLACE → in a request: `async_stream` + `max_concurrency`; durable backlog: Oban queue `limit`; external stream: Broadway processor `concurrency` | A "pool manager" GenServer plus worker GenServers; poolboy | Work queued in a Go channel is lost on crash today: decide whether that was accepted or a bug |
| Channel pipelines between stages, `select` with `time.After` | Hand-off with backpressure, timeouts | reliability, platform | REPLACE → `Stream` pipelines; `receive ... after` for select-with-timeout; GenStage/Broadway only for demand-driven external sources | Modelling every channel as a GenServer; unbounded `cast` mailboxes as queues | none |
| `sync.Mutex`/`RWMutex` around maps and structs | Protect shared memory | platform | DELETE → immutable data needs no lock; for real contention use one state owner, ETS atomic ops (`insert_new`, `update_counter`) or DB locks | A GenServer as a mutex around pure functions | none |
| `sync.Map`, map + RWMutex caches | Shared read-mostly data | platform | REPLACE → ETS (`read_concurrency: true`), `:persistent_term` for rarely changing data, Cachex 4.1 for TTL and eviction | An Agent or GenServer map on the hot path | Invalidation must see legacy writes while the DB is shared |
| `sync/atomic`, `atomic.Int64` counters | Lock-free counters | platform | MAP → `:counters`, `:atomics`, `:ets.update_counter/3` | A GenServer counter | none |
| `sync.Once`, `init()` side effects | Compute once, register drivers | platform | REPLACE → Application start + supervised children; `:persistent_term`; module attributes with `@external_resource` (Iron Law 16) | A named GenServer holding a constant | none |
| `sync.Pool` | Cut GC pressure from short-lived allocations | platform | DELETE → per-process heaps and per-process GC | Object pools in ETS | none |
| `singleflight.Group` | Collapse concurrent identical calls | platform | REPLACE → `Cachex.fetch/4` (its Courier runs the fallback once per key for concurrent callers), or a Registry-keyed process | A global GenServer serializing every lookup | none |
| `semaphore.Weighted`, buffered-channel semaphores | Cap concurrent use of a resource | business | REPLACE → `max_concurrency`, Oban queue `limit`, NimblePool 1.1 for non-HTTP resources, a Finch pool per upstream | A semaphore GenServer with a call/cast race | none |
| `x/time/rate`, tollbooth, ulule/limiter | Rate limiting | business | REPLACE → Hammer 7.5 (ETS/Atomic, sliding window or token bucket) inbound; an `:atomics` limiter as a Req step outbound; Oban Pro for cluster-wide limits | A GenServer limiter on the hot path | Per-node limit × node count is the effective rate |
| gorilla/coder websocket "hub" (register/unregister/broadcast channels) | Fan-out to connected clients | business | REPLACE → Phoenix Channels + PubSub, Presence for who-is-online; WebSock 0.6 only to keep a mandated raw protocol | A Hub GenServer holding every connection | Keep message JSON; clients switch to phoenix.js or a Channels client unless shimmed |
| Redis pub/sub or NATS between replicas for fan-out | Cross-instance broadcast | platform | DELETE → Phoenix.PubSub PG adapter + dns_cluster or libcluster | Keeping Redis between nodes that can cluster | KEEP NATS (gnat 1.18) when other services publish on the subjects |
| sqlc `query.sql` + generated code | Type-safe hand-written SQL | business | MAP → Ecto queries in contexts; keep complex SQL as `Repo.query/3` or `fragment` | A `Queries` module with one function per sqlc query | The `.sql` files are a complete query inventory: use them as the porting checklist and for EXPLAIN baselines |
| GORM models, `gorm.Model`, `DeletedAt`, hooks, `Preload`, `AutoMigrate` | ORM convenience | business | MAP → Ecto schemas, explicit preloads, changeset functions instead of hooks | ActiveRecord-style `save/1`; emulating a global soft-delete scope | `gorm.DeletedAt` adds `deleted_at IS NULL` to every query: scope it in contexts. AutoMigrate in production means no DDL history: baseline from `pg_dump --schema-only` |
| golang-migrate, goose, atlas | Versioned DDL | business | MAP → Ecto migrations with a `structure.sql` baseline | Translating every historical migration | One DDL owner during the overlap |
| `database/sql`/pgxpool limits | Bound DB connections | reliability, platform | MAP → Repo `pool_size`, `queue_target` | A connection-manager GenServer; one Repo per context | Legacy pool + Elixir pool must stay within `max_connections` |
| `db.BeginTx`, GORM `Transaction(func)`, pgx `BeginFunc` | Atomic writes | business | MAP → `Repo.transact/2` or `Ecto.Multi`; `Oban.insert` in the Multi for outbox side effects | Passing `tx` handles through every function | PG isolation defaults stay READ COMMITTED |
| asynq server/client, `MaxRetry`, `Unique`, `ProcessIn`, `Timeout`, queue priorities | Durable Redis-backed jobs | business | REPLACE → Oban 2.24 workers: `max_attempts`, `unique`, `schedule_in`, `timeout/1`, queues with `limit` | A Redis list queue via Redix; `Task.start` | asynq retries 25 times by default, Oban 20. Weighted or strict queue priority has no direct OSS Oban equivalent: use separate queues with limits or job `priority` 0–9 |
| asynq Scheduler, robfig/cron, ticker loops on every replica, k8s CronJobs hitting an endpoint | Periodic jobs | business | REPLACE → Oban cron (`cron: [crontab: [...]]`, per-entry `timezone:`) | robfig/cron on every node; leader election for a ticker | `cron.WithSeconds()` six-field specs: Oban takes five. Sub-minute work needs a state-owner timer under highlander_pg, or a rethink |
| River (Postgres job queue) | Transactional enqueue in Postgres | business | MAP → Oban (same model: jobs table, insert in the caller's transaction) | Polling River's table from Elixir | Drain River queues, then switch producers; unique args map to `unique: [keys: ...]` |
| Lease and visibility timeouts (asynq lease, River rescuer) | Recover jobs from crashed workers | reliability, platform | REPLACE → Oban `lifeline: [rescue_after: ...]` | Heartbeat processes | Set `rescue_after` above the longest job runtime |
| cenkalti/backoff, retry-go, go-retryablehttp, sony/gobreaker | Survive transient failures | reliability, platform | REPLACE → Req 0.7 `retry: :transient`, a Finch pool per upstream, Oban backoff; fuse 2.5 only with evidence | Porting gobreaker; retry loops around Repo calls | `http.DefaultClient` has no timeout, so legacy may wait forever; Req's `receive_timeout` defaults to 15 s: decide explicitly |
| gRPC servers and clients, `.proto` | Service contracts | contract | MAP → merged services become function calls; external peers via grpc 1.0 + protobuf 0.17 | Keeping gRPC between contexts inside one release | Keep package names and field numbers |
| Viper, envconfig, flags | Config | business | MAP → `config/runtime.exs` | A config GenServer polled at runtime | Keep env var names |
| zap, zerolog, slog with context fields | Structured logs | business | MAP → Logger metadata, LoggerJSON 7.0, `Plug.RequestId` | Passing logger instances around | Keep field names the log pipeline parses |
| `//go:embed`, `html/template`, templ | Ship assets and templates inside the binary | business | MAP → `priv/static` + HEEx; compile-time file reads declare `@external_resource` (Iron Law 16) | Templates embedded as strings | none |
| client_golang `/metrics`, expvar, pprof | Metrics and profiling | business | MAP → Telemetry.Metrics + PromEx 1.12; LiveDashboard 0.9, recon, `:observer` | A metrics GenServer | Keep metric names that alerts reference |
| cgo bindings | Reuse a C library | business | MAP → Rustler 0.38 dirty NIF or a Port; keep the C library | Long-running non-dirty NIFs that block schedulers | none |
| golang-jwt, securecookie, scs sessions | Auth | contract | REPLACE → phx.gen.auth; Joken 2.7 + joken_jwks 1.8 for existing bearer tokens | Hand-parsed JWTs; sessions in ETS | securecookie/scs cookies won't decode: session exchange; `x/crypto/bcrypt` hashes verify with bcrypt_elixir |

## Disappears on the BEAM (DELETE candidates)

- `defer recover()` panic shields in handlers and goroutines: always. A crash ends one process and a supervisor decides what restarts.
- Mutexes, `RWMutex` and `sync.Map` around in-memory state: when the data is immutable or ownership moves to one process or ETS.
- `sync.Pool` and other allocation pools: always. Each process has its own heap and GC.
- Fiber `Prefork`, or several replicas per host only to use cores: always.
- `context.Context` plumbing: only once every deadline and cancellation path it carried has an explicit owner (the mechanism row above).
  Call timeouts and monitors are not cancellation.
- Shutdown bookkeeping (done channels, WaitGroups at exit): when drain is restated and tested. The supervision tree stops children in
  reverse start order, but that alone does not prove in-flight requests and jobs finish within each component's shutdown timeout.
- Separate `cmd/` binaries that exist only for fault isolation: when one release with role subtrees meets the scaling needs.
- Redis or NATS fan-out between replicas of this service: when nodes can cluster and no other service uses the channel.
- k8s Lease or etcd leader election for app jobs: when Oban cron, Oban queues or highlander_pg covers it.
- Internal gRPC or HTTP between services merged into one release: always after the merge.
- Hand-rolled connection managers and object pools: always. DBConnection and Finch own pooling.

## Keep or shim (with conditions)

- gRPC to external or other-team peers: KEEP with grpc 1.0.5 and the existing `.proto` files.
- NATS, Kafka or Redis shared with other services: KEEP. Use gnat 1.18, Broadway with broadway_kafka 0.7, or Redix 1.9.
- Go services owned by other teams: KEEP behind HTTP or gRPC. Never connect distributed Erlang across team boundaries.
- A CPU-heavy Go component with proven performance (media processing, crypto, parsers): KEEP as a sidecar, or port the hot
  loop to a Rustler dirty NIF. Measure first.
- asynq producers outside this app: SHIM during the overlap. Drain queues, then point producers at an endpoint that inserts
  Oban jobs.
- A raw WebSocket protocol used by clients that cannot update: SHIM with a WebSock 0.6 handler fed by Phoenix.PubSub, isolated
  in one module: migration-only with a removal milestone, or a permanent supported adapter with an owner, support policy and
  conformance tests.
- Edge proxy (Envoy, Traefik) or service mesh mandated by the platform: KEEP. Decide which single layer owns retries.

## Questions the architect must ask

1. Which `cmd/` binaries run where, at what replica counts, and why are they separate? Why: it decides one release with role
   subtrees or several releases.
2. For each long-lived goroutine: who starts and stops it, what does it own, and what happens when it panics? Why: this list
   becomes the supervision tree, and most entries become no process at all.
3. Which mutex-guarded structures are the source of truth, and which are caches of the DB? Why: caches become ETS or
   queries, while truth needs an owner process or the DB.
4. Which work lives only in channels or in-memory worker pools, and is losing it on a crash acceptable? Why: if not, it
   belongs in Oban, not in `async_stream`.
5. What does each pool or semaphore size protect (DB connections, an API quota, CPU)? Why: it picks `max_concurrency`, an
   Oban queue `limit`, a Finch pool, or nothing.
6. Which context deadlines are SLO commitments that clients see, and which cancellations must stop work rather than stop
   waiting? Why: the first become explicit timeouts and edge responses; the second need an owned cancellation path.
7. Which JSON details do clients depend on (`omitempty`, `null` slices, int64 as string, time format)? Why: Elixir encoders
   behave differently by default.
8. For asynq or River: retry counts, uniqueness TTLs, priorities, timeouts, periodic tasks, non-Go producers? Why: each maps
   to an Oban option, and priority semantics differ.
9. Which sqlc queries are hand-tuned and should stay raw SQL? Why: rewriting tuned SQL in the query DSL can change plans,
   so keep fragments and compare EXPLAIN output.
10. Does GORM `AutoMigrate` or soft delete run in production? Why: no migration history, and implicit filters Ecto will not add.
11. Which gRPC services are internal and which are external? Why: merge the internal ones and KEEP the external contracts.
12. What throughput and latency does the Go service reach, on which harness? Why: Go is fast per request, so set the Elixir
    target and an iteration budget before porting.
13. Can the platform run distributed Erlang? Why: it decides PubSub and Presence over Redis or NATS fan-out.

## Libraries (versions checked by the plugin author on hex.pm, 2026-10-09; re-check before pinning)

| Need | Package | Version | Notes |
|---|---|---|---|
| Web framework | phoenix | 1.8.15 | Router, controllers, Channels |
| HTTP server | bandit | 1.12.5 | Replaces `http.Server` tuning |
| Raw WebSocket (SHIM only) | websock_adapter | 0.6.0 | Keep a mandated legacy protocol |
| Data | ecto / ecto_sql / postgrex | 3.14.2 / 3.14.0 / 0.22.4 | Raw SQL via `Repo.query/3` stays available |
| Other databases | myxql / ecto_sqlite3 | 0.9.0 / 0.25.0 | MySQL and SQLite adapters |
| Jobs and cron | oban / oban_web | 2.24.1 / 2.13.1 | Replaces asynq and River; Pro adds global limits |
| External streams | broadway / broadway_kafka | 1.3.0 / 0.7.0 | Replaces consumer goroutines |
| Fan-out | phoenix_pubsub | 2.4.1 | PG adapter over distributed Erlang |
| Clustering | dns_cluster / libcluster | 0.3.1 / 3.5.0 | Only with more than one node |
| Cluster singleton | highlander_pg | 1.0.8 | Sub-minute singleton timers |
| HTTP client | req / finch | 0.7.5 / 0.24.0 | Separate Finch pools act as bulkheads |
| Resource pools | nimble_pool | 1.1.0 | Non-HTTP resources; prefer over poolboy |
| Rate limiting | hammer | 7.5.0 | ETS/Atomic token bucket or sliding window |
| Cache | cachex | 4.1.1 | `fetch/4` replaces singleflight |
| gRPC | grpc / protobuf | 1.0.5 / 0.17.1 | External peers only |
| NATS (KEEP only) | gnat | 1.18.1 | Shared subjects |
| Redis (KEEP only) | redix | 1.9.2 | Shared keys |
| Native code | rustler | 0.38.0 | Dirty NIFs for cgo-style hot loops |
| Metrics | prom_ex | 1.12.0 | Phoenix, Ecto, Oban and BEAM dashboards |
| Tracing | opentelemetry | 1.7.0 | Keep W3C `traceparent` across the strangler |
| Logs | logger_json | 7.0.4 | Structured JSON output |
| Auth tokens | joken / joken_jwks | 2.7.0 / 1.8.0 | Validate existing JWTs |
| Password hashes | bcrypt_elixir | 3.3.2 | `x/crypto/bcrypt` compatible |
| Circuit breaker | fuse | 2.5.0 | Dormant but mature; only with evidence |
