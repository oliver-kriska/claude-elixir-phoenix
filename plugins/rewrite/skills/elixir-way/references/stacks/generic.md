# Generic method → Elixir (any stack without a pack)

Use this file when no pack in `stacks/` matches the source: Python scripts, plain PHP or WordPress, plain Ruby, Rust (axum, actix-web),
Kotlin/Ktor, Scala (Play, Akka, Pekko), Perl, C#/F# outside ASP.NET, ColdFusion, or Elixir/Erlang code that is itself not idiomatic.
It probes by concept, not by framework name, so it works in a language you have not seen before.
Classify the app first with `../app-shapes.md`: the shape decides whether Phoenix, Ecto or Oban apply at all.
Verdicts, reason tags and evidence levels are defined in the elixir-way SKILL.md.

## Probe: where mechanisms hide

Run one concept at a time. Tokens below are literal strings (`rg -F`), so no regex escaping is needed in any language.

```bash
X='!**/{node_modules,vendor,target,build,dist,_build,deps,.venv,venv,obj,.git}/**'
rg -n -F -g "$X" -e '@Transactional' -e 'transaction.atomic' -e 'beginTransaction(' -e 'txn_do' .
# Size the hit list before reading it; the denominator goes into the coverage report.
rg -c -F -g "$X" -e 'TOKEN' . | sort -t: -k2 -nr | head -20
# Deploy, config and SQL files hide mechanisms too; search them explicitly.
rg -n -F -g '*.{yml,yaml,toml,ini,conf,cfg,json,xml,properties,service,timer,sql,cfc}' -e 'TOKEN' .
```

| Concept | Literal search tokens (several languages) | How to confirm | Record |
|---|---|---|---|
| Process roles and entry points | `__main__`, `fn main(`, `static void main`, `func main(`, `ENTRYPOINT`, `CMD [`, `command:`, `ExecStart=`, `[program:`, `kind: CronJob`, `kind: DaemonSet`, `Procfile` | Map every deploy unit (container, systemd unit, supervisord program, CronJob) to a binary, arguments and replica count. Read orchestration files, not only code | Roles (web, worker, scheduler, socket server, CLI, migrator) and replicas. A role split only because the runtime could not host it is a DELETE candidate |
| Lifecycle hooks, interceptors, decorators, annotations | `@PrePersist`, `@PostUpdate`, `@Aspect`, `@Around`, `IInterceptor`, `ActionFilterAttribute`, `__init_subclass__`, `functools.wraps`, `add_action(`, `add_filter(`, `#[ORM\`, `Layer<S>`, `before_save`, `around '` | Find the registration site and the trigger (persist, request, method call, plugin load). Read the ordering rule (priority number, chain position). Find a test that observes the side effect | Each implicit side effect: trigger, order, inside or outside the transaction |
| DI containers, service locators | `@Inject`, `@Autowired`, `@Singleton`, `bind(`, `AddScoped<`, `AddSingleton<`, `services.yaml`, `$container->get(`, `ServiceLocator`, `getInstance()`, `Depends(`, `Extension(`, `wire[` | For each binding: do two implementations exist (prod, test, tenant, region), or does it wire one class? Note the scope (singleton, request, transient) | Real seams become behaviours. Stateful singletons go to the state rows below. Wiring-only bindings are DELETE |
| Event buses, observers, signals | `EventEmitter`, `.emit(`, `.subscribe(`, `@EventListener`, `ApplicationEventPublisher`, `INotificationHandler`, `EventDispatcher`, `do_action(`, `blinker`, `post_save`, `Observer`, `broadcast::channel`, `eventStream` | List publishers and subscribers per event. Sync or async dispatch? Before or after commit? Does a listener failure abort the publisher? Does anything outside the process subscribe? | Each reaction tagged durable (Oban), live fan-out (PubSub) or plain indirection (direct call) |
| Background execution | `threading.Thread`, `ThreadPoolExecutor`, `multiprocessing`, `asyncio.create_task`, `ExecutorService`, `CompletableFuture`, `@Async`, `GlobalScope.launch`, `Task.Run(`, `BackgroundService`, `tokio::spawn`, `spawn_blocking`, `rayon`, `pcntl_fork(`, `fastcgi_finish_request(` | Must the work survive a crash or deploy? What happens to an exception inside it (logged, swallowed, retried)? Is the pool size a downstream quota or just core usage? | Durability need, error policy, concurrency caps that protect a downstream |
| Schedulers | `crontab`, `cron.d`, `OnCalendar=`, `@Scheduled`, `Quartz`, `scheduleAtFixedRate`, `APScheduler`, `schedule.every(`, `add_job(`, `wp_schedule_event(`, `RecurringMessage`, `tokio::time::interval`, `while True:`, `Thread.sleep(` | Expression and timezone. Overlap guard (lock file, `flock` in the crontab line). One run per replica or per cluster? What happens after a missed run? | Per job: cadence, timezone, overlap, uniqueness scope, failure alerting (often only cron `MAILTO`) |
| Global, static, thread-local state, request context | `static mut`, `lazy_static!`, `OnceCell`, `thread_local!`, `ThreadLocal`, `AsyncLocal<`, `contextvars`, `threading.local`, `flask.g`, `$GLOBALS`, `global $`, `static $`, `our $`, `local $`, `Thread.current`, `companion object`, `MDC.put` | Who writes it, who reads it, how long it lives (request, process, forever). A long-running runtime leaks it between requests; PHP-FPM and CGI reset it | Implicit values (user, tenant, locale, request id, open transaction) to make explicit; caches hiding in statics |
| ORM style | `.save()`, `::find(`, `objects.filter(`, `EntityManager`, `persist(`, `flush()`, `session.add(`, `session.commit()`, `SaveChanges(`, `@Entity`, `diesel::`, `sqlx::query`, `DBIx::Class`, `$wpdb->`, `PDO` | Active record (the object saves itself) or data mapper / unit of work (identity map, dirty tracking, writes at flush)? Check lazy loading, cascades, naming strategy, client-generated ids and timestamps | Writes that happen implicitly at flush or by cascade; defaults the database does not generate, which Ecto must |
| Transaction boundaries | `BEGIN`, `COMMIT`, `@Transactional`, `TransactionScope`, `transaction.atomic`, `session.begin(`, `beginTransaction(`, `txn_do`, `AutoCommit`, `FOR UPDATE`, `SERIALIZABLE`, `ATOMIC_REQUESTS` | Unit of atomicity (request, method, explicit block), propagation, isolation level. Which external effects (HTTP, mail, publish) run inside the transaction? | Atomic units, isolation-dependent invariants, side effects that must move after commit |
| Caches, memoization | `lru_cache`, `functools.cache`, `cached_property`, `@Cacheable`, `Caffeine`, `CacheBuilder`, `IMemoryCache`, `moka`, `#[cached`, `set_transient(`, `wp_cache_`, `apcu_`, `Memcache`, `Memoize`, `\|\|=` | Key composition (user, tenant, locale, permission?), TTL, invalidation trigger, whether errors are cached, whether another writer (legacy app, admin tool) changes the source | Freshness requirement and key completeness. A cache that only hides slow code needs a measurement before it is kept |
| Locks, mutexes | `Mutex`, `RwLock`, `synchronized`, `ReentrantLock`, `lock (`, `SemaphoreSlim`, `threading.Lock`, `flock(`, `lockf`, `.lock`, `pg_advisory_lock`, `GET_LOCK(`, `SETNX`, `NX PX`, `redlock`, `sem_acquire(` | Name the shared resource. In-memory (protects a heap) or cross-process (file, row, Redis key, external account)? Will the legacy app still contend for it during coexistence? | The invariant the lock protects and its scope (thread, process, host, cluster) |
| Retries, circuit breakers, timeouts | `retry`, `backoff`, `tenacity`, `@Retryable`, `Polly`, `Resilience4j`, `CircuitBreaker`, `Failsafe`, `tower::retry`, `max_attempts`, `timeout` | Which call is retried, is it idempotent, how many layers retry the same call (client, queue, mesh), what does the caller see after the last attempt? | One retry owner per call path, idempotency keys, timeout values to start from |
| Config loading | `os.environ`, `getenv(`, `System.getenv`, `GetEnvironmentVariable`, `std::env::var`, `dotenv`, `application.conf`, `appsettings`, `parse_ini_file(`, `wp-config.php`, `define(`, `ConfigFactory.load`, `BaseSettings`, `figment` | Required or defaulted keys, read at boot or per call, hot reload, secret source. Compare with the env that deploy manifests set | Env var names and files operators edit (operational contract); reload behavior ops scripts rely on |
| Feature flags | `isEnabled(`, `is_enabled(`, `feature_flag`, `LaunchDarkly`, `Unleash`, `Flagsmith`, `FeatureManager`, `Flipper`, `cfg(feature`, `ENABLE_`, `FEATURE_` | Kind (release, kill switch, entitlement, experiment), who flips it and where, current value per environment. Rust `cfg(feature)` is compile-time, not runtime | Live flags with owners; dead flags with their fixed value, which is the behavior to port |
| Reflection, metaprogramming, codegen | `getattr(`, `importlib`, `eval(`, `exec(`, `Class.forName(`, `getDeclaredMethod`, `Proxy.newProxyInstance`, `Activator.CreateInstance`, `call_user_func(`, `__call(`, `AUTOLOAD`, `no strict 'refs'`, `method_missing`, `define_method`, `macro_rules!`, `build.rs`, `.proto`, `generated` | Enumerate the runtime targets from the registry, config or directory that feeds them. Treat codegen inputs (proto, OpenAPI, XSD, schema files) as the real source | Dispatch that cannot be enumerated is a coverage gap and `UNDECIDED`; codegen inputs are wire contracts |
| IPC and subprocesses | `subprocess`, `Popen`, `os.system(`, `shell_exec(`, `proc_open(`, `ProcessBuilder`, `Runtime.getRuntime().exec`, `Process.Start(`, `std::process::Command`, `system(`, `IPC::Run`, `AF_UNIX`, `.sock`, `mkfifo`, `shm_open`, `zmq` | Binary and version, arguments, timeout, exit-code handling, output parsing, what happens to the child when the parent dies | External binaries and versions (operational contract); message formats on pipes and sockets |
| File-system state | `fopen(`, `file_put_contents(`, `Files.write`, `File.WriteAllText`, `std::fs::write`, `/tmp/`, `/var/lib/`, `uploads`, `storage/`, `.pid`, `.sqlite`, `pickle`, `shelve`, `Storable`, `serialize(`, `inotify`, `watchdog` | Who reads the file later (a process, a cron job, a human, a partner over SFTP)? Is the path shared between hosts (NFS, EFS)? Is the format documented? | Data contracts (exports, drops, reports) versus scratch; durable state living on local disk |
| Signals and shutdown hooks | `signal.signal(`, `SIGTERM`, `SIGHUP`, `SIGUSR1`, `atexit`, `addShutdownHook`, `@PreDestroy`, `IHostApplicationLifetime`, `tokio::signal`, `ctrlc`, `$SIG{`, `pcntl_signal(`, `register_shutdown_function(`, `CoordinatedShutdown` | What each signal does (drain, reload, reopen logs, dump state). Which ops scripts or logrotate configs send it? Drain time versus the orchestrator grace period | Signal contracts and drain semantics per role |
| Database-side logic | `CREATE TRIGGER`, `CREATE PROCEDURE`, `CREATE FUNCTION`, `CREATE EVENT`, `MATERIALIZED VIEW`, `NOTIFY`, `pg_cron`, `DBMS_SCHEDULER`, `EXEC sp_` | Ask the owner for a schema dump (`pg_dump --schema-only`, `mysqldump --no-data --routines --triggers --events`). Never connect to production yourself | Logic that runs for every writer, legacy and Elixir alike, while the database is shared |

- **A hit is a lead.** Its evidence is `inferred`. A test, log or reproduced behavior makes it `observed`; a comment, ADR or commit message makes it `documented`.
- **No hit is not absence.** Config-driven wiring, string dispatch, plugin directories, admin-panel settings (ColdFusion Administrator, WordPress options,
  Jenkins jobs) and DB-side code escape grep. List them as coverage gaps.
- **Sample by risk, not by directory.** Start with auth, money, tenancy, destructive operations, durable work and public integrations; record the denominator.

## Mechanism map

| Legacy concept | Typical forms (several languages) | Purpose to confirm | Elixir default | Verdict hint | Guarantees to check |
|---|---|---|---|---|---|
| Request middleware, filters | Plack middleware, Ktor `install(`, tower layers, Symfony kernel listeners, WSGI middleware, Play filters | Ordered cross-cutting rule (auth, tenant, CORS, body limit) or a runtime shim | Plug in endpoint and router pipelines; `on_mount` for LiveView; Bandit + Plug alone for a small API | MAP; DELETE runtime shims | Order, short-circuit status codes, body-size limits, error envelope |
| Persistence lifecycle hooks | JPA `@PrePersist`, Doctrine lifecycle callbacks, SQLAlchemy events, WordPress `save_post`, SeaORM `ActiveModelBehavior` | Derived fields, audit, cache bust, enqueue, notify | Changeset functions for derived data; `Ecto.Multi` steps; `Oban.insert` in the same transaction; PubSub after commit; Carbonite for audit | REPLACE | Effects visible only after commit; atomicity; runs on every write path including bulk updates |
| Decorators, AOP | Python `@login_required`, Spring AOP, PostSharp, Moose method modifiers, stacked Scala traits | Auth, timing, logging, caching or a transaction around a function | Explicit call or `with`; `:telemetry.span/3` for timing; plugs for request-level auth | REPLACE; DELETE logging-only aspects | Authorization still runs for every caller once the decorator is gone |
| DI container, service locator | Spring, Guice, Koin, Dagger, `IServiceCollection`, Symfony container, FastAPI `Depends`, PHP-DI | Swap implementations, or wiring only | Plain modules; behaviour + `Application.get_env/3` + Mox for real seams | DELETE container; MAP real seams | Test seams still work; no global registry process |
| Stateful singleton | Kotlin/Scala `object` with `var`, C# static class, Python module globals, `getInstance()` | Holds connections, caches, counters, registries | Supervised process only with a runtime reason; ETS for shared reads; `:persistent_term` for rarely-changing values; Repo pool for DB connections | REPLACE | State after a crash, read concurrency, single writer |
| In-process event bus | Guava EventBus, MediatR, Symfony EventDispatcher, blinker, WordPress `do_action`, Akka eventStream | Decoupling, sometimes a durable reaction | Direct context calls; `Phoenix.PubSub` after commit for live fan-out; Oban job for durable reactions | REPLACE or DELETE | Delivery (at-most or at-least once), order, listener failure isolation, after-commit visibility |
| Threads, executors, non-durable async | `ThreadPoolExecutor`, `ExecutorService`, `Task.Run`, `tokio::spawn`, Kotlin `launch`, Scala `Future` | Parallelism, latency hiding, fire-and-forget | Sequential code in the process; `Task.Supervisor.async_stream_nolink/4` with `max_concurrency` and `timeout`; `Task.Supervisor.start_child/2` | DELETE pool tuning; MAP real parallelism | Timeout and cancellation, error propagation, caps that protect a downstream |
| Durable work queue | Job tables polled by a daemon, Celery/RQ, Hangfire, Gearman/TheSchwartz, Symfony Messenger | Work that survives crash and deploy, with retries | Oban worker inserted in the same transaction as the write that causes it | REPLACE | Durability, at-least-once plus idempotency key, uniqueness window, backoff, priority, per-queue concurrency |
| Scheduler | crontab, systemd timers, Quartz, APScheduler, WP-Cron, Akka scheduler, Windows Task Scheduler | Periodic business work, or infra maintenance | Oban cron: top-level `cron: [crontab: [...]]` in 2.24 (`Oban.Cron`, formerly `Oban.Plugins.Cron`), per-entry `timezone:` | REPLACE; KEEP infra jobs that must run while the app is down | Once per cluster, timezone and DST, overlap, missed-run policy, alerting |
| Thread-local, request context | `ThreadLocal`, `AsyncLocal`, `contextvars`, Flask `g`, Perl `local`, MDC, coroutine context | Carry user, tenant, locale, request id implicitly | Explicit `%Scope{}` (Phoenix 1.8) or arguments; Logger metadata for request ids | REPLACE | Context reaches Tasks and Oban jobs explicitly (Iron Law 25); no process dictionary |
| Global mutable statics | `static mut`, `$GLOBALS`, module-level dicts, class variables | Shared counters, registries, config | ETS, `:counters`/`:atomics`, `:persistent_term`, one owner process | REPLACE | Who writes; per-node or cluster scope; is reset on restart acceptable? |
| Active-record ORM | Eloquent-style models, Django models, Peewee, ActiveJDBC, Yii AR | Persistence and behavior in one object | Ecto schema (shape) + changeset (validation) + context (behavior, queries) | MAP | ORM-generated defaults and timestamps, soft-delete filters, implicit validations |
| Data mapper, unit of work | Hibernate, Doctrine, SQLAlchemy session, EF Core, Exposed DAO, DBIx::Class | Identity map, dirty tracking, flush order, cascades | Explicit changesets + `Repo.transact/2` or `Ecto.Multi`; `optimistic_lock/3` on the same version column | MAP | Flush-time writes made explicit; cascades via FK `on_delete` or explicit steps; version column bumped by both writers |
| Transaction boundary | `@Transactional`, `TransactionScope`, `transaction.atomic`, per-request transaction middleware, `txn_do` | Atomic unit of a business change | `Repo.transact/2` or `Ecto.Multi` inside the context function that owns the change | MAP | Atomicity, isolation level (Postgres defaults to READ COMMITTED), effects outside the transaction |
| Memoization, in-process cache | `lru_cache`, Caffeine, `IMemoryCache`, moka, APCu, Perl `Memoize` | Latency, a slow dependency | ETS (`read_concurrency: true`), Cachex, `:persistent_term`; DELETE when a measured baseline shows no need | REPLACE or DELETE | Key includes user, tenant, locale, permission; errors never cached; invalidation on every writer |
| Shared external cache | Redis, memcached, Hazelcast | Share state across share-nothing processes | Per-node ETS/Cachex with PubSub invalidation | REPLACE; KEEP if other services read the keys | Staleness bound, cross-node invalidation, behavior when the cache is down |
| In-memory locks | `synchronized`, `Mutex`, `RwLock`, `lock`, `threading.Lock` | Protect a shared heap | Usually nothing (immutable data); one owner process; ETS `update_counter`/`insert_new` | DELETE | The protected invariant still holds with concurrent processes |
| Cross-process locks | `flock`, lock files, `pg_advisory_lock`, `GET_LOCK`, Redis `SET NX`, ZooKeeper | Single run or mutual exclusion across hosts | Unique constraint; `pg_advisory_xact_lock` in `Repo.transact/2`; a cluster-wide registered name; Oban `unique` only for duplicate enqueues | REPLACE; KEEP the same primitive during coexistence | Both systems contend on one primitive; released on crash; session locks break behind PgBouncer transaction mode |
| Retries, circuit breakers | tenacity, Polly, Resilience4j, Failsafe, tower retry, loops with `sleep` | Survive transient failure; protect a thread pool | Req `retry: :transient`; Oban `max_attempts` + `backoff/1`; supervisors; fuse only with evidence | REPLACE | Retried call is idempotent; one retry layer per path; final failure is visible |
| Config loading | YAML, INI, HOCON, `.env`, `appsettings.json`, `wp-config.php`, Spring profiles | Per-environment values and secrets | `config/runtime.exs` with `System.fetch_env!/1`; parse an operator-owned file at boot if it must stay | MAP | Same env var names; missing required values fail at boot; reload semantics |
| Feature flags | LaunchDarkly, Unleash, Flagsmith, Flipper, config booleans | Rollout, kill switch, entitlement | FunWithFlags with Ecto persistence, or KEEP the SaaS | MAP live flags; DELETE dead flags after fixing their value | Flag keys and per-actor evaluation preserved; default when the flag store is down |
| Reflection, dynamic dispatch | `getattr`, `Class.forName`, `call_user_func`, `AUTOLOAD`, `method_missing`, plugin registries loaded from a directory | Extensibility, plugin systems, routing by string | Explicit map of allowed modules; behaviours; protocols; pattern matching | REPLACE; UNDECIDED when targets cannot be enumerated | Closed target set; never `String.to_atom/1` on input (Iron Law 10) |
| Code generation | protobuf, OpenAPI generators, XSD/JAXB, Diesel schema, T4 templates, Scala macros | Typed contract with another system | Keep the input file; generate with `protobuf` or `open_api_spex` | MAP | Wire compatibility (field numbers, names, enum values) |
| Subprocesses | `subprocess`, `ProcessBuilder`, `Process.Start`, `std::process::Command`, `shell_exec`, backticks | Reuse a native tool | `System.cmd/3` for short calls; a Port; MuonTrap or erlexec when the child must die with its owner; long work inside an Oban job | MAP; KEEP the binary | Timeout, exit-code mapping, output parsing, child cleanup on crash, binary version pinned in the image |
| IPC between own components | Unix sockets, pipes, ZeroMQ, shared memory, D-Bus, localhost HTTP | Talk between processes of one app | Message passing when both ends move into the release; `:gen_tcp`/`:socket` or a Port when one end stays foreign | DELETE or REPLACE | Framing, backpressure, behavior on peer restart |
| File-system state | Spool directories, pid files, local SQLite, pickled or serialized blobs, uploads on local disk | Persist work or data between runs | Postgres tables and Oban for spools; object storage for uploads; `ecto_sqlite3` when single-node local state is the requirement | REPLACE; KEEP formats others read | Durability across deploys and hosts, atomic writes (temp file + rename), format compatibility |
| Signals, shutdown hooks | `atexit`, `addShutdownHook`, `@PreDestroy`, `pcntl_signal`, `$SIG{HUP}`, Akka `CoordinatedShutdown` | Drain, flush, reload, reopen logs | Supervisor stops children in reverse start order; `terminate/2` needs `trap_exit` and is still not guaranteed; Bandit, Oban and Broadway drain; `System.trap_signal/3` | MAP; SHIM signals ops send | SIGTERM drain fits the grace period; SIGUSR1 halts the BEAM by default |
| Database-side logic | Triggers, stored procedures, MySQL events, `pg_cron`, views | Invariants enforced for every writer | KEEP during coexistence; read trigger-set columns back with `read_after_writes: true`; move into contexts only with a parity test | KEEP | Runs for both writers; owner of each object recorded |

## Disappears on the BEAM (DELETE candidates)

Each item disappears only under its condition. When the condition fails, the obligation moves to a named Elixir mechanism instead.

- **Thread-pool and worker-count sizing** (Gunicorn workers, executor sizes, tokio worker threads, PHP-FPM `pm.max_children`): the core-usage part
  disappears. A size that is really a downstream quota (DB connections, API rate, licence seats) stays as `max_concurrency`, a Finch pool size or an
  Oban queue limit. Durability of queued work never disappears.
- **async/await plumbing and future combinators**: disappears for non-blocking I/O, because a blocked process does not block others. Explicit
  parallelism, timeouts and cancellation remain.
- **In-memory mutexes**: disappear when the data is immutable or has one owner process. A lock on a cross-process resource (file, row, external
  account) remains.
- **Context-propagation libraries** (thread-locals, MDC copying, coroutine context): disappear once every consumer, including jobs, receives the
  value as an argument.
- **In-process watchdogs and restart wrappers** (catch-all loops that keep a worker alive, supervisord `autorestart` per worker, `forever`):
  disappear inside the release because supervisors restart children. One OS-level supervisor for the release itself stays, and so does error reporting.
- **Separate worker, scheduler and socket processes of one codebase**: merge into one release when resource profiles fit together (measure) and no
  isolation requirement (untrusted code, separate credentials, separate scaling) exists.
- **Pid files and single-instance lock files**: disappear when a cluster-wide registered name or a DB lock covers single-instance behavior and no ops script reads them.
- **DI containers and service locators**: disappear. A seam stays as a behaviour only where a second implementation exists.
- **In-process event buses and mediators**: disappear when all subscribers live in the release. Durable listeners become Oban jobs; they do not disappear.
- **A broker used only between components of this app** (RabbitMQ between its own web and worker): disappears when both ends are in the release and
  no outside consumer reads the queue. The durability moves to Oban.
- **Interpreter workarounds**: GIL workarounds (`multiprocessing` for CPU), Perl `fork`-per-connection servers, opcache or JIT warmers, per-request
  bootstrap caches. They disappear when the work is plain Elixir; native libraries stay behind a Port or NIF.
- **Memoization that hid N+1 queries or slow templates**: disappears only after a measured baseline (Iron Law 9) shows the target meets the goal without it.
- **Circuit breakers whose only job was protecting a thread pool**: disappear with bounded Finch pools and timeouts. A breaker that protects the
  upstream from a thundering herd stays.

## Keep or shim (with conditions)

- **The database and its schema**: KEEP during coexistence, with Ecto mapped onto existing names. Condition: one DDL owner at a time.
- **Triggers, stored procedures, DB events**: KEEP while both systems write. Move one into a context only with a parity test that runs both writers.
- **Native libraries with no Hex equivalent** (SciPy, a Rust crate, a JVM PDF library): KEEP via a Port or HTTP/gRPC sidecar, Pythonx, or a Rustler NIF.
  Record the owner and version pin. Pythonx embeds CPython with one GIL: calls from many Elixir processes do not run Python concurrently
  (native code and I/O release it), so keep Pythonx in one process or use `System.cmd/3` or Ports for parallel work.
- **External binaries** (ffmpeg, ImageMagick, LibreOffice, wkhtmltopdf): KEEP, called through MuonTrap or erlexec inside Oban jobs, versions pinned in the image.
- **Brokers with outside producers or consumers**: KEEP. Consume with Broadway; publish from an Oban job inserted with the write (outbox).
- **Wire protocols whose clients cannot upgrade** (custom TCP framing, SOAP, XML-RPC, MQTT devices in the field): SHIM at the edge. One adapter module
  (a ThousandIsland handler or a Plug) translates to context calls; internals stay idiomatic. Record the owner and support policy (Iron Law 6).
- **Files and directories other systems read** (CSV drops, SFTP folders, generated reports): KEEP the path and byte format; produce them from Oban jobs.
- **CLI flags, exit codes and stdout formats that scripts parse**: KEEP, proven with golden-output tests.
- **Signals ops send** (SIGHUP reload, SIGUSR1 log reopen): SHIM with `System.trap_signal/3`. The BEAM halts on SIGUSR1 by default, so a logrotate
  `postrotate kill -USR1` line crashes the node until it is trapped or retired with the ops owner.
- **Config formats operators edit** (INI, YAML, HOCON, `wp-config.php`): KEEP by parsing the file at boot in `config/runtime.exs`, or convert with operator approval.
- **External IdP or SSO**: KEEP; validate its tokens.
- **The legacy app for one role during a phase** (session issuer, CMS admin, report generator): KEEP with an end condition written down.

## Questions the architect must ask

1. Which deploy units exist, how many replicas run, and which state differs per process? Why: per-process caches, counters and schedules look like
   contracts but are often accidents of topology.
2. For each probe hit, what present obligation fails if it disappears? Why: an accidental origin does not license removal when consumers rely on it.
3. Which areas could the probes not close (string dispatch, plugin directories, admin-panel settings, DB code, inaccessible services)? Why: they
   are coverage gaps and their mechanisms stay `UNDECIDED`.
4. Which background work must survive a crash or a deploy? Why: it decides Oban versus a supervised Task.
5. Which concurrency limits protect a downstream (database, API quota, licence, hardware)? Why: those caps survive; core-usage sizing does not.
6. Which schedules run once per replica today, and does anything rely on the duplicates or on catch-up after downtime? Why: Oban cron runs once per cluster.
7. What rides implicitly in thread-locals and globals, and which async boundaries must carry it? Why: each value becomes an explicit argument.
8. Which implicit ORM behaviors does the data depend on (flush order, cascades, client-generated ids and timestamps, soft delete)? Why: Ecto does
   none of them unless you write them.
9. Which locks protect resources the legacy app will still touch during coexistence? Why: both systems must contend on the same primitive.
10. Which libraries, binaries and runtimes have no Hex equivalent, and who owns each sidecar? Why: every KEEP needs an owner and a reason.
11. Which files, directories, signals, exit codes, flags and config formats do operators or other systems depend on? Why: operational contracts
    break silently because no test covers them.
12. Which retry layers exist per call path, and which operations are idempotent? Why: stacked retries multiply load and duplicate side effects.
13. Which flags are live, who flips them, and which are dead with a fixed value? Why: a dead flag's value is behavior, its code is not.
14. Which app shape and compatibility bar (ADR-000) apply? Why: they decide whether Phoenix, Ecto, Oban or LiveView belong in the target at all.

## Quick notes for stacks without a pack

### Rust (axum, actix-web, tokio)

- tokio is cooperatively scheduled, so `spawn_blocking` and "never block the executor" rules exist; on the BEAM they are DELETE.
  `Arc<Mutex<T>>` shared state becomes one owner process or ETS.
- tower layers and axum extractors (`State`, `Extension`) map to plugs and `conn.assigns`. `thiserror` enums map to tagged tuples.
- serde attributes are the wire contract: `rename_all = "camelCase"`, `skip_serializing_if`, `untagged` enums. Reproduce them in explicit JSON views.
- sqlx compile-time-checked queries become Ecto queries, so the compile-time SQL check is lost; cover it with tests. Diesel/sqlx migrations become the Ecto baseline.
- A measured CPU-bound hot path can stay Rust as a Rustler NIF on a dirty scheduler. ADR-000 must state the performance goal before anyone ports it.

### Kotlin / Ktor

- Ktor plugins (`install(...)`) map to plugs; the routing DSL maps to the Phoenix router or `Plug.Router`.
- Structured concurrency (`coroutineScope`, `async`) maps to linked Tasks under a `Task.Supervisor`; `Dispatchers.IO` sizing is DELETE.
- Coroutine context elements (MDC, tenant) become explicit arguments. `Flow` maps to `Stream`, or to GenStage when demand matters.
- Exposed or Ktorm maps to Ecto. kotlinx.serialization `@SerialName` and default-value rules are wire contracts. Koin modules are DELETE.

### Scala (Play, Akka, Pekko)

- Actors to OTP is **not** 1:1. **Supervision:** Akka classic's `Resume` keeps actor state after a failure; OTP has no resume, a restart re-runs
  `init/1`. Handle that error inside the process, or move state to ETS or the DB. Typed actors stop on failure by default, so map each decider deliberately.
- **Mailboxes:** Akka offers bounded, priority and stash mailboxes and `ask` with timeouts. BEAM mailboxes are unbounded, with selective receive and
  per-sender ordering. Bounded mailboxes become `call` backpressure or GenStage demand; stash becomes selective receive or a queue in state.
- **Persistence:** Akka Persistence journals and snapshots are a data contract (Jackson or Protobuf serializers). Use Commanded + EventStore only for
  a real event-sourcing need; otherwise replay into Ecto tables once. Cluster Sharding maps to Registry + DynamicSupervisor, Horde or syn.
  Cluster Singleton maps to highlander_pg or Oban cron.
- Play maps to Phoenix (routes file to router, Twirl to HEEx). `Future` + `ExecutionContext` becomes sequential code; implicits and `given` become explicit arguments.

### Python scripts and cron

- Usually the "scheduled jobs only" or "batch" shape in `../app-shapes.md`. A crontab line plus a lock file becomes an Oban cron worker with `unique: [period: :infinity, states: :incomplete]`,
  which skips a tick while one is unfinished.
- argparse/click flags, exit codes and stdout are operational contracts. A 30-line script with no shared logic may not need rewriting at all.
- pandas maps to Explorer only when the transform fits; NumPy, SciPy and scikit-learn without an equivalent stay behind Pythonx or a Port.
- Scripts often assume "runs once a night". Oban retries, so writes must be idempotent: upserts on natural keys, watermarks.

### Plain PHP and WordPress

- Share-nothing per request: statics and `$GLOBALS` reset every request. Request-local caches are DELETE; anything that must persist was already in the DB or APCu.
- `add_action`/`add_filter` with priorities is the event bus. Inventory hook name, priority and owning plugin; the order is behavior.
- WP-Cron fires on page visits unless `DISABLE_WP_CRON` plus a system cron exists. Oban cron changes the timing: confirm nothing relies on visit-driven runs.
- `wp_posts`/`wp_postmeta` is EAV: map it read-only with Ecto during coexistence. Keeping the WordPress admin for editors while Phoenix serves reads is a valid KEEP.
- Symfony apps are covered by `laravel.md`. Legacy phpass `$P$` password hashes need a small custom verifier [U: no Hex package checked].

### Perl (CGI, mod_perl, PSGI, Mojolicious, Catalyst)

- PSGI/Plack middleware maps to Plug. `local $` dynamic scope is request context. `AUTOLOAD`, string `eval` and glob assignment hide dispatch: coverage gaps.
- `fork`-per-request servers and `Parallel::ForkManager` are DELETE, but keep any worker cap that protects a downstream.
- DBI and DBIx::Class map to Ecto. Gearman and TheSchwartz queues map to Oban. `Storable` and `Data::Dumper` files are data contracts.
- Regex-heavy code ports to `Regex` (PCRE family via `:re`), but Perl-only features (`(?{ code })`, locale rules) differ: test against a real corpus.

### Legacy Elixir or Erlang

- Refactor in place; do not rewrite. The runtime is already right, so the value is in removing translationese: GenServers owning the DB, the process
  dictionary as globals, hand-rolled job loops, cross-context calls. Use `../translationese-checks.md`, `mix xref graph`, Boundary and Credo.
- Strangle module by module inside the same release and supervision tree; add Ecto, Oban or Phoenix only where a guarantee needs them.
- Hot code upgrades (appups, relups) and Mnesia (distribution, netsplit behavior) are operational and data contracts. Check who relies on them before dropping either.

### Other (C#/F# outside ASP.NET, ColdFusion, VB6, Delphi)

- Windows services (`ServiceBase`, `BackgroundService`) become a release run as a service; WinForms/WPF follow the desktop shape in `../app-shapes.md`.
- ColdFusion keeps mechanisms outside the repo: Administrator scheduled tasks, datasources and mappings. Export the server config, then probe
  `Application.cfc` (`onApplicationStart`, `onRequestStart`), `cflock`, `cfthread` and `cfquery`.

## Libraries (versions checked by the plugin author on hex.pm, 2026-10-09; re-check before pinning)

| Need | Package | Version | Notes |
|---|---|---|---|
| Web framework, server UI | phoenix / phoenix_live_view | 1.8.15 / 1.2.12 | Only when the shape has a web surface |
| HTTP server, small APIs | bandit / plug | 1.12.5 / 1.20.3 | Bandit + `Plug.Router` without Phoenix is fine for a few endpoints |
| Data | ecto / ecto_sql / postgrex | 3.14.2 / 3.14.0 / 0.22.4 | `Repo.transact/2` since 3.13 |
| Other databases | myxql / tds / ecto_sqlite3 | 0.9.0 / 2.3.8 / 0.25.0 | MySQL, SQL Server, SQLite |
| Jobs and cron | oban / oban_web | 2.24.1 / 2.13.1 | 2.24 renamed `Oban.Plugins.Cron` to `Oban.Cron`; the old name is deprecated and delegates |
| Broker consumers | broadway / gen_stage | 1.3.0 / 1.3.2 | Kafka, RabbitMQ, SQS producers available |
| Fan-out | phoenix_pubsub | 2.4.1 | PG adapter over distributed Erlang |
| Singletons, registries | highlander_pg / horde / syn | 1.0.8 / 0.10.0 / 3.4.2 | Horde is eventually consistent |
| Event sourcing (real need only) | commanded / eventstore | 1.4.11 / 1.4.10 | Akka Persistence replacement |
| HTTP client | req / finch | 0.7.5 / 0.24.0 | One Finch pool per upstream is the bulkhead |
| Cache | cachex / nebulex | 4.1.1 / 3.0.4 | Nebulex for distributed or multi-level caches |
| Rate limiting | hammer | 7.5.0 | ETS/Atomic backends are per node |
| Circuit breaker | fuse | 2.5.0 | Dormant since 2021 but mature; only with evidence |
| Feature flags | fun_with_flags | 1.13.0 | Boolean, actor, group and percentage gates |
| Test seams | mox | 1.3.2 | Replaces container-swapped test doubles |
| Subprocesses | muontrap / erlexec / ex_cmd | 2.0.1 / 2.5.0 / 0.18.0 | Child dies with its owner; streaming I/O |
| Native and Python interop | rustler / pythonx | 0.38.0 / 0.4.10 | The Python GIL limits Pythonx concurrency |
| Dataframes | explorer | 0.13.0 | pandas-style transforms (Polars engine) |
| Contracts | protobuf / grpc / open_api_spex | 0.17.1 / 1.0.5 / 3.22.4 | Keep the legacy codegen inputs |
| Audit trail | carbonite | 0.17.0 | Trigger-based; also captures legacy writes |
| File watching | file_system | 1.1.1 | inotify and FSEvents |
| Operator config formats | yaml_elixir / toml | 2.12.2 / 0.7.0 | toml has had no release since 2022 |
| CSV contracts | nimble_csv | 1.3.0 | Byte-exact exports |
| Time zones | tz / tzdata | 0.28.4 / 1.2.2 | IANA names for legacy zone strings |
| Local `.env` | dotenvy | 1.2.1 | Dev only; releases read the environment |
| Legacy Elixir cleanup | boundary / credo | 0.11.0 / 1.7.19 | Enforce context boundaries while refactoring in place |
| Structured logs | logger_json | 7.0.4 | Keep field names the log pipeline parses |
