# Infrastructure by Use

Most legacy infrastructure exists because the legacy runtime cannot share memory between requests, cannot
keep work running after a response, or cannot hold many sockets. The BEAM can do all three. Classify every
piece by the **role** it plays, not by its product name. One Redis instance often plays four roles, and
each role gets its own ledger row and its own verdict.

Each entry answers four questions: **purpose** → **BEAM-native replacement** → **DELETE when** →
**KEEP when**. KEEP and SHIM rows name the contract that forces them and the condition that retires them.

Versions: Phoenix 1.8.15, Phoenix.PubSub 2.4.1, Oban 2.24.1, Cachex 4.1.1, Nebulex 3.0.4, Hammer 7.5.0,
Redix 1.9.2, phoenix_pubsub_redis 3.1.1, Broadway 1.3.0, Bandit 1.12.5, Req 0.7.5, Finch 0.24.0.

## Find the Roles First

Search the legacy config before reading code. Every hit is a candidate role:

- Rails: `config/cable.yml` (`adapter: redis`), `config.cache_store`, `config.active_job.queue_adapter`,
  `config/sidekiq.yml`, `config/resque.yml`, `Rack::Attack.cache.store`, `Kredis`, `Redis.new`, `REDIS_URL`.
- Django: `CACHES` (django-redis), `CELERY_BROKER_URL`, `CHANNEL_LAYERS`, `SESSION_ENGINE`, django-ratelimit.
- Laravel: `CACHE_STORE`/`CACHE_DRIVER`, `QUEUE_CONNECTION`, `SESSION_DRIVER`, `BROADCAST_CONNECTION`, Horizon.
- Node, Go, JVM: ioredis/node-redis, BullMQ, `connect-redis`, go-redis, asynq, Lettuce/Redisson, `IDistributedCache`.
- Ops: `docker-compose.yml`, Procfile, Helm values, `bin/*` scripts. Read the persistence flags too
  (`--appendonly`, `--save`), because durability lives in config, not in the product name.

## Redis by Role

| Role | Legacy purpose | BEAM-native replacement | DELETE when | KEEP when |
|------|----------------|-------------------------|-------------|-----------|
| Cache | Processes share nothing, so a shared out-of-process cache is the only warm one | Fix the query first. Then ETS (`read_concurrency: true`) or Cachex 4.1.1 (`limit`, `ttl`, `fetch/3`). PubSub broadcasts cross-node invalidation. Nebulex 3.0.4 for multi-level | The cache is app-private | Non-BEAM services read the same keys, or the working set is larger than node RAM |
| Pub/sub | Each instance knows only its own sockets, so broadcasts need a bus | `Phoenix.PubSub` (PG adapter over distributed Erlang); cluster with dns_cluster 0.3.1 or libcluster 3.5.0 | Nodes can cluster | Nodes cannot cluster (Cloud Run, some PaaS): phoenix_pubsub_redis 3.1.1. Or legacy apps subscribe during coexistence |
| Job queue | Work must outlive the request and survive a crash | Oban 2.24.1 inserted in the same `Ecto.Multi` as the domain write. `Oban.Engines.Lite` on SQLite, `Dolphin` on MySQL | No non-Elixir producer remains and legacy queues are drained | Never as the Elixir queue. A SHIM bridge (exq 0.25.0) only while legacy producers exist, with a removal milestone |
| Locks | Mutual exclusion across stateless instances | The narrowest primitive every contender honors: a unique constraint, `SELECT ... FOR UPDATE`, `pg_advisory_xact_lock` in `Repo.transact/2`, one cluster-wide registered process (highlander_pg 1.0.8). Oban `unique` suppresses duplicate inserts only; it is no lock | The lock protects app-private state | Non-BEAM processes contend on the same lock. During coexistence prefer a DB lock both sides honor |
| Rate limit | Counters shared across instances | Hammer 7.5.0 (`use Hammer, backend: :ets`) in a plug, with the window algorithm chosen explicitly (fixed windows allow boundary bursts); `:atomics` for outbound quotas | Per-node limits × node count are acceptable | Exact global limits across unclustered nodes: `hammer_backend_redis` |
| Sessions | Stateless instances share server-side sessions | `Plug.Session` cookie store (signed by default; encrypted only when `encryption_salt` is set) plus a DB `users_tokens` table for revocation (phx.gen.auth) | Session handoff or forced re-login is done (data-compat.md) | Other apps read the same session store (SSO through Redis) |
| Counters, leaderboards | Cheap high-rate `INCR`, sorted sets, HyperLogLog | `:counters`, `:ets.update_counter/4` flushed to the DB by an Oban cron job. Rankings: an indexed score column + `rank() over (...)`, or an ETS `ordered_set` fed by PubSub | Counts fit the DB at the flush interval | Very high write rates, HLL at scale, or a board other services share |
| Streams | Durable log with consumer groups (`XADD`, `XREADGROUP`) | Oban for in-app work; Broadway + off_broadway_redis_stream when the stream is shared | Only this app produces and consumes | Other producers write the stream |
| Presence | Who is online, with TTL heartbeats | `Phoenix.Presence` (CRDT over PubSub, no central store) | Always; presence is ephemeral | Never |
| Idempotency keys | `SETNX` with a TTL | A unique-constrained `idempotency_keys` table pruned by Oban cron; Oban `unique` for duplicate job inserts | Always | The key space is shared with other services |
| Feature flags | Runtime toggles shared across instances | fun_with_flags 1.13.0 with Ecto persistence + PubSub cache busting | Flags are app-private | A flag SaaS or other services own the flags |

Campfire kept Redis for durable Resque, a Cable bridge and fragments. Every other basecamp port with a native
framework (Django, Laravel, Express) dropped Redis for a SQLite-backed leased queue. Oban Lite is the
Elixir equivalent, and none of the 12 Campfire PRs proposed it.

## Brokers: Kafka, RabbitMQ, SQS

| Broker use | Purpose | Replacement | DELETE when | KEEP when |
|------------|---------|-------------|-------------|-----------|
| In-app domain events | Decouple modules inside one app | Direct context calls; `Phoenix.PubSub.broadcast/3` after commit; durable reactions as Oban jobs in the same Multi | Producer and consumers all move into this release | Never for in-app decoupling |
| Celery/Sidekiq broker | Transport for a job queue | Oban (this is a job queue, not an integration) | Legacy workers are drained | During drain only |
| Cross-team backbone (Kafka) | CDC, analytics, replay for other consumers | Consume with Broadway 1.3.0 + broadway_kafka 0.7.0. Produce with brod 4.7.0 from an Oban worker (outbox) | n/a | Any producer or consumer outside this app, retention or replay others rely on, or Kafka Streams jobs on the topics |
| RabbitMQ / SQS integration | Cross-language fan-out, managed queues | broadway_rabbitmq 0.8.2 / amqp 4.3.0; broadway_sqs 1.0.0 / ex_aws 2.7.0 | Both ends are this app | Other producers or consumers exist |

Cutover: start the Elixir consumer group from the legacy committed offsets, or shadow-consume and compare.
Keep message schemas and partition keys. Publish only from an Oban job inserted with the domain write, never
inside the DB transaction.

## Cron and Schedulers

| Legacy | Purpose | Replacement |
|--------|---------|-------------|
| whenever (crontab), sidekiq-cron, Solid Queue recurring | Periodic work outside the request | `Oban.Cron` (named `Oban.Plugins.Cron` before 2.24; the old name still delegates) |
| celery beat, django-celery-beat | Same, editable in the admin | `Oban.Cron` for static schedules; a small DB table plus one cron job for runtime-editable ones |
| Laravel `schedule:run`, `onOneServer`, `withoutOverlapping` | One run per tick across servers | `Oban.Cron` (the leader inserts). `unique: [period: :infinity, states: :incomplete]` skips inserting a tick while one is unfinished; jobs inserted another way still overlap, so hard exclusion needs a DB lock in `perform/1` |
| Quartz clustered JDBC store, ShedLock, Hangfire `RecurringJob` | Duplicate-run prevention across instances | `Oban.Cron`; DELETE the Quartz/ShedLock tables |
| node-cron, `time.Ticker`, `@Scheduled`, `setInterval` loops | In-process timers | `Oban.Cron` for business work; `Process.send_after/3` only inside the process that owns the state |
| k8s CronJob, ECS scheduled task | Run without a long-lived scheduler | `Oban.Cron` inside the release; `bin/app eval` for one-off ops |

```elixir
config :app, Oban,
  repo: App.Repo,
  queues: [default: 10, mailers: 5],
  cron: [crontab: [{"0 3 * * *", App.Nightly.Cleanup}, {"0 9 * * MON", App.Digest, timezone: "Europe/Bratislava"}]],
  pruner: [max_age: {7, :days}],
  lifeline: [rescue_after: {30, :minutes}]   # above the longest legitimate run; derive N per app
```

- **Why Oban cron:** each tick becomes a durable, retried, visible job, and only the leader enqueues.
- **Orphans:** a node killed mid-job leaves the row `executing`. `lifeline:` is opt-in: after `rescue_after` it
  moves the job back to `available`, or to `discarded` when attempts are exhausted. Rescue is time-based, so a
  too-short N runs a live job twice. Crash-recovery claims need a kill/restart witness.
- **DELETE when:** the legacy schedule is disabled in the **same deploy window** that enables the Oban entry.
  An overlap runs the job twice, and a gap skips it.
- **KEEP when:** the task must run while the app is down (backups, VACUUM, certificate rotation). Keep those as
  infra jobs.
- **Translate expressions:** Quartz has a seconds field and `?`, while Oban takes 5-field crontab plus
  `@daily`/`@reboot`. Non-UTC schedules need a timezone database (tz or tzdata).
- **Avoid** quantum 3.5.3 (no releases since 2024-02, in-memory, runs on every node) and per-node
  `send_after` loops for cluster-wide work.
- **SQLite caveat:** `Oban.Engines.Lite` defaults to `Oban.Peers.Isolated`, which elects no leader across
  overlapping deploys. Two instances can both enqueue a tick, so give cron workers `unique:` options and witness
  one insert per tick with two instances running (sqlite-on-beam.md).

## Reverse Proxies and Sidecars

| Legacy | Purpose | Replacement | DELETE when | KEEP when |
|--------|---------|-------------|-------------|-----------|
| Nginx / Apache in front of Puma, Gunicorn, FPM | Buffer slow clients so a few workers are not tied up; serve static files; TLS; gzip | Bandit 1.12.5: each connection is a cheap process, so slow clients cost nothing. `Plug.Static` with `gzip: true` + `mix phx.digest` precompressed files. `send_file` (sendfile syscall) replaces X-Sendfile/X-Accel-Redirect | It fronts only this app and does TLS/static/compression/buffering | Several apps share the host, ops owns ACME/TLS, or it is the platform ingress |
| Thruster (Rails 8) | TLS, HTTP/2, asset caching, X-Sendfile for Puma | Bandit terminates TLS and HTTP/2 itself; `Plug.SSL` / `force_ssl` for HSTS and redirects | The operator contract (ports, certs, env vars) is preserved | Removing it changes an install contract you must keep |
| CDN, WAF, edge rate limits | Security boundary, DDoS, global caching | Cache headers from Phoenix; Hammer stays app-level | Never because of the rewrite | Always; it is a platform decision |
| PM2, supervisord, Foreman for app workers | Restart crashed workers, run N copies | OTP supervision trees inside one release; systemd or k8s supervises the single OS process | Always | Never for worker counts |
| Service-mesh sidecar (Envoy, Linkerd) | mTLS, retries, traffic shift between services | Function calls inside the app; Req retries for real upstreams | The mesh only served intra-app calls | The platform mandates it; keep one retry layer, not mesh + Req + Oban |

Campfire put Thruster in front of Bandit. PR #5 replaced it with an in-app front module. The idiomatic
target is Bandit with TLS configured in the endpoint, and the removal still needs a contract check and an
A/B measurement.

## Multi-Process App Servers

- **Legacy:** Puma workers × threads, Unicorn, Gunicorn/uWSGI workers, PHP-FPM `pm.max_children`, Node
  `cluster`/PM2, worker killers and `max_requests` recycling.
- **Purpose:** parallelism around a GIL, a single-threaded event loop or share-nothing processes; crash
  isolation; leak mitigation through recycling.
- **BEAM:** one OS process with one scheduler per core. Every request runs in its own process with its own
  heap and GC, so a crash or a leak stays inside that process. **DELETE** worker counts, `preload_app!`,
  `WEB_CONCURRENCY`, worker killers and request-count recycling.
- **Real concurrency budget:** the Ecto `pool_size` and the downstream Finch pools, not acceptor counts.
  During coexistence: legacy workers × their pool + Elixir `pool_size` ≤ `max_connections`.
- **Contract:** if operators set `WEB_CONCURRENCY` or `PUMA_*`, record the variable as an operational contract.
  Accept it and log that it is ignored, or document its removal.
- **KEEP:** never as a mechanism. Keep at least two nodes behind the load balancer for availability, and
  cluster them.

## Sticky Sessions

- **Purpose:** Socket.IO and SignalR long-polling keep transport state on one instance, PHP file sessions
  live on local disk, and in-memory sessions are per instance.
- **BEAM:** cookie sessions are stateless. Phoenix LongPoll routes through PubSub to the owning process on
  any clustered node, and LiveView and Channels reconnect to any node.
- **DELETE when:** nodes cluster, sessions are cookie- or DB-backed, and the legacy app no longer serves sockets.
- **KEEP when:** the legacy app still serves sockets during coexistence, or nodes cannot cluster and the
  LongPoll fallback is required.

## Microservices

- **Purpose:** team ownership, independent deploys, failure isolation, polyglot code, different resource
  profiles. Some services exist only for runtime reasons (GIL, memory, socket limits).
- **BEAM:** one Phoenix app with contexts as boundaries (check with `mix xref` or `/phx:boundaries`).
  Process isolation replaces service isolation, internal HTTP becomes function calls, Oban queues
  separate workloads, and FLAME covers burst compute.
- **Merge (DELETE the boundary) when:** one team owns both sides, they share a database, they call each other
  synchronously on one request path, or the split was a runtime workaround.
- **KEEP when:** other teams or languages own the service, regulation requires isolation, the resource
  profile is radically different (GPU, huge memory), or external clients call its API. Call it through Req
  0.7.5 with a named Finch pool per upstream, behind a project-owned module (Iron Law 20).
- **Strangler:** put Phoenix in front and forward unported paths with reverse_proxy_plug 3.0.4, or route at
  the load balancer. Port vertical slices: route, context, jobs.
- **Singletons and discovery:** use `Oban.Cron` or highlander_pg 1.0.8 for one global process, not Horde. Use
  dns_cluster or libcluster instead of Consul/Eureka for intra-app discovery.

## Other Infrastructure

| Legacy | Replacement | KEEP when |
|--------|-------------|-----------|
| memcached | Same as the Redis cache role | Shared with other apps |
| Elasticsearch/OpenSearch/Algolia for modest search | Postgres `tsvector` + GIN, `pg_trgm`; SQLite FTS5 via parameterized SQL. Index updates in an Oban job inserted with the write | Relevance, facets or scale that a shadow comparison proves Postgres cannot meet |
| S3 / object storage | Keep the bucket. ex_aws 2.7.0 + ex_aws_s3 2.5.9 behind an owned module; LiveView `allow_upload` with `external:` | Always keep the bucket and key layout (data-compat.md) |
| Action Cable server, AnyCable, Reverb, Soketi, Socket.IO gateway | Phoenix Channels or LiveView in the same release | Pinned native clients still speak the old protocol: a migration-only SHIM with a removal milestone, or a permanent supported adapter (ui-strategy.md) |
| SMTP relay / mail API | Swoosh, delivered from an Oban worker | The provider account itself stays |

## Durability Mapping

| Guarantee the legacy mechanism gave | Elixir mechanism | Never a substitute |
|-------------------------------------|------------------|--------------------|
| Durable, at-least-once, survives crash and deploy | Oban job inserted in the same `Ecto.Multi` / `Repo.transact/2` as the domain write, plus `lifeline:` orphan recovery proved by a kill/restart test | `Task.start`, a GenServer queue, PubSub, an ETS table, a Redis list without AOF |
| Ephemeral fan-out to connected clients | `Phoenix.PubSub.broadcast/3` after commit; clients re-read history on reconnect | An Oban job per message, unless delivery itself must be durable |
| Per-node cache | ETS or Cachex, invalidated over PubSub; never the source of truth | A GenServer holding a map read by every request |
| Run at time T, or periodically | Oban `scheduled_at`; `Oban.Cron` | `Process.send_after` on every node |
| No duplicate enqueue of the same work | Oban `unique:` with explicit `keys`, `period` and `states` | ETS dedupe across nodes |
| At most one concurrent run per key | A DB lock every contender honors (`pg_advisory_xact_lock`, `SELECT ... FOR UPDATE`), or a verified global limit (Oban Pro `global_limit`) | Oban `unique:`; a `limit: 1` queue running on several nodes (limits are per node) |
| Per-key order | Broadway `partition_by` for streams; for jobs, a version or sequence column the worker checks | Oban `unique:` or job `priority`; a retried job falls behind later ones |
| Effect happens exactly once | Nothing provides this. Use an idempotency key + unique constraint, and design the effect to be retried | "Exactly once" claims about Oban or a broker |

```elixir
Ecto.Multi.new()
|> Ecto.Multi.insert(:message, Message.changeset(%Message{}, attrs))
|> Oban.insert(:push, fn %{message: m} -> PushWorker.new(%{"message_id" => m.id}) end)
|> Repo.transact()
|> tap(fn
  {:ok, %{message: m}} -> Phoenix.PubSub.broadcast(App.PubSub, "room:#{m.room_id}", {:created, m.id})
  _ -> :ok
end)
```

Rules:

- **Never silently downgrade a durable queue to an in-memory one.** José Valim's PR #10 replaced Resque with
  bounded per-class in-process queues (1,024 entries, overflow dropped), so queued pushes and webhooks are lost
  on a crash. PR #1 did the same and was closed for removing "the durable Redis/Resque job path". A downgrade
  needs an ADR that names the lost guarantee and has user sign-off.
- **Measure durability from config, not from the product name.** Campfire's Redis ran with
  `--save '' --appendonly no`, so its "durable" Resque queue already died with the container. Record that as
  the real legacy guarantee, then decide whether to restore it. Oban restores it.
- **Close the post-commit gap.** Rails `after_commit { Job.perform_later }` loses the job if the process dies
  between commit and enqueue. An Oban insert in the Multi closes that gap. Log it in `divergences.md` as an
  improvement.
- **Broadcast after commit, never inside the transaction.** A rollback must not leave clients holding an event
  for a row that does not exist.
- **Jobs live in the same database as the data** when the enqueue must be atomic. A separate jobs database
  lowers contention, but you lose the single-transaction enqueue.
- **Restoring a backup replays jobs.** Workers must tolerate effects that were already sent before the backup.

## Coexistence Period

ADR-000 names the cutover mode first. The transition contract in the architect skill's compatibility-bar.md
applies whenever both runtimes read or write live data, which a staged cutover does as well.

| Cutover mode | Live overlap | Bridges needed |
|--------------|--------------|----------------|
| Replacement | None: one maintenance window, rollback by restore | Data and crypto readers (data-compat.md), or an import plus validation when the data decision is a new schema |
| Staged cutover | Weeks, one domain or route at a time | The bridges below for each overlapping aggregate, each with a removal milestone |
| Sustained coexistence | Long-term, one owner per invariant | The bridges below; long-lived ones are permanent supported adapters |

Overlap rules (staged cutover and sustained coexistence):

- **Jobs:** choose the producer path per engine in the transition contract: legacy producers insert Oban rows,
  an outbox the Elixir side drains, or a bridge. On Postgres, direct `oban_jobs` inserts follow the pinned
  producer contract in compatibility-bar.md (Oban's guide "Migrating from Other Languages" shows a Rails model
  writing rows; Oban for Python 0.6.6 shares the schema). Direct inserts are unproven on `Oban.Engines.Lite`.
  Elixir does not adopt Sidekiq, Resque or Celery payloads as its queue format. Drain the legacy queues,
  re-insert scheduled or ETA jobs with `scheduled_at`, and quarantine and report unsupported jobs, never drop
  them. exq 0.25.0 is a temporary drain bridge at most.
- **Database:** one shared database with one DDL owner (data-compat.md). Ecto writes do not fire legacy
  callbacks (FTS updates, `touch`, cache busting, broadcasts), so name one write authority per operation.
- **Events:** PubSub does not reach the legacy app. Bridge committed events with an Oban worker that publishes
  to the legacy bus, or with LISTEN/NOTIFY on a direct, non-pooled connection. Polling the same rows is not
  equivalent.
- **Caches:** writes from either app must invalidate both apps' caches, or the cache is bypassed. Campfire
  response caches in PRs #2, #5 and #7 were blocked on exactly this foreign-writer hole.
- **Cron:** exactly one side owns each schedule. Switch ownership in the same deploy window.
- **Sockets:** web clients move to phoenix.js or LiveView. Pinned native clients keep the legacy socket server,
  fed from Elixir through a bridge: migration-only, or a permanent supported adapter when ADR-000 keeps the
  protocol for clients that cannot update.

Every migration-only bridge is a SHIM row with all of the following:

- **A flag, default off,** read in `config/runtime.exs`, with its state logged at boot.
- **A removal milestone** in the ledger: a date, a client version or a drained-queue count.
- **Tests for both flag states.**
- **No domain logic.** The bridge translates committed events and nothing else.

A permanent supported adapter records instead an owner, a version and security support policy, conformance
tests and the conditions that reopen it. It needs no sunset date and no forced client update.

Campfire's `CableRedisBridge` sat behind `CAMPFIRE_CABLE_REDIS_BRIDGE=1`. The flag was right. The missing
piece was a ledger milestone for deleting it.

```elixir
# config/runtime.exs
config :app, :legacy_bridge, System.get_env("APP_LEGACY_BRIDGE") == "1"

# lib/app/application.ex
children = [App.Repo, {Phoenix.PubSub, name: App.PubSub}, {Oban, Application.fetch_env!(:app, Oban)}] ++
  if(Application.fetch_env!(:app, :legacy_bridge), do: [App.Compat.LegacyBridge], else: []) ++
  [AppWeb.Endpoint]
```

Rollback needs a time boundary. Restoring a pre-cutover snapshot discards later writes unless you have a
replay plan. If Rails must read what Elixir wrote, rehearse that path (data-compat.md).
