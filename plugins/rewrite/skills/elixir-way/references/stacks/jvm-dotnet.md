# JVM and .NET → Elixir

Covers Spring Boot (JPA/Hibernate, `@Scheduled`/Quartz, `@Async`, Kafka/Rabbit listeners, Spring Security) and ASP.NET Core (EF Core, SignalR, Hangfire, `IHostedService`).
Read it alongside the verdict vocabulary (MAP, REPLACE, KEEP, SHIM, DELETE, UNDECIDED) and the reason tags in the elixir-way SKILL.md. `[U]` marks a detail not re-verified on 2026-10-09.
Both stacks hide behavior in annotations, proxies and container defaults, so probe configuration before code.

## Probe: where mechanisms hide

| Look at | What it reveals | Contract or purpose to capture |
|---|---|---|
| `pom.xml`, `build.gradle*` starters; `*.csproj` `PackageReference` | Auto-configuration and libraries in play | Which framework defaults are active (security, JPA, Kafka, Hangfire, Polly) |
| `application*.yml`/`.properties`: `spring.jpa.open-in-view`, `ddl-auto`, `spring.jackson.*`, `server.servlet.session.*`, `spring.kafka.*` | Behavior set by config, not code | OSIV dependence, schema drift, JSON naming and dates, session timeout, consumer groups |
| `@Configuration`, `@Bean`, `@ConditionalOn*`, `@Profile`; `Program.cs`/`Startup.cs` `builder.Services.Add*` | Wiring, lifetimes, per-environment behavior | Real stateful singletons vs plain wiring |
| `app.Use*` order in `Program.cs`; `@Order`, `FilterRegistrationBean`, `OncePerRequestFilter`, `HandlerInterceptor` | Middleware and filter order | Ordering that changes behavior (auth vs CORS, exception handler position) |
| `@ControllerAdvice`, `@ExceptionHandler`, `ProblemDetail`; `UseExceptionHandler`, `AddProblemDetails`, `IExceptionFilter`, `[ApiController]` | Error envelopes | Exact bodies and status codes clients parse |
| `SecurityFilterChain`, `@EnableMethodSecurity`, `@PreAuthorize`, `@Secured`; `[Authorize(Policy`, `AddAuthorization`, `IAuthorizationHandler` | Authorization rules | The permission matrix, including method-level rules buried in services |
| `PasswordEncoder` beans, `{bcrypt}`, `UserDetailsService`; `AddIdentity`, `AspNetUsers`, `PasswordHasher`, `AddDataProtection` | Credential and cookie formats | Hash formats to verify, cookie names, `SecurityStamp` revocation, key rings |
| `oauth2ResourceServer`, `issuer-uri`, `jwk-set-uri`; `AddJwtBearer`, `TokenValidationParameters` | Token validation | Issuers, audiences, JWKS, clock skew, claim mapping |
| `@Transactional(` with `propagation`, `rollbackFor`, `readOnly`; `TransactionScope`, `BeginTransaction` | Transaction boundaries | Rollback rules, `REQUIRES_NEW` uses, self-invocation cases that were never transactional |
| `@Entity` with `@ManyToOne`, `fetch =`, `@Version`, `@Enumerated`, `@Inheritance`, `@GeneratedValue`, `allocationSize`, `@Where`, `@SQLDelete`, `@SoftDelete` | JPA mapping semantics | Ordinal enums, id ranges, discriminators, implicit filters, eager loads |
| `@PrePersist`, `@PreUpdate`, `@EntityListeners`, `@CreatedDate`, `@LastModifiedBy`, Hibernate `Interceptor` | Entity lifecycle side effects | Audit fields and side effects that must become explicit |
| `OnModelCreating`, `HasQueryFilter`, `OwnsOne`, `HasConversion`, `IsRowVersion`, `HasDiscriminator`, `SaveChangesInterceptor`, `UseLazyLoadingProxies` | EF Core implicit behavior | Global filters, owned-type column names, converters, concurrency tokens |
| `db/migration/V*__*.sql`, Liquibase `changelog*`, `Migrations/*.cs`, `flyway_schema_history`, `__EFMigrationsHistory` | DDL history and owner | Baseline point; who owns DDL during the overlap |
| `@Cacheable`, `@CacheEvict`, Hibernate second-level cache; `IMemoryCache`, `IDistributedCache`, `AddStackExchangeRedisCache` | Cache layers | Freshness requirements; keys shared with other services |
| `@Async`, `@EnableAsync`, `ThreadPoolTaskExecutor` beans, `CompletableFuture`; `Task.Run(`, discards like `_ = DoAsync()`, `Parallel.ForEachAsync(` | Async and fan-out | Work that must survive a restart; pool sizes that protect a downstream |
| `@Scheduled`, `@SchedulerLock`, `QRTZ_*` tables, `JobDetail`/`Trigger` beans, `quartz.properties`; Quartz.NET `IJob` | Schedules | Cron expressions (6–7 fields), timezones, misfire policy, cluster locks |
| `BackgroundJob.Enqueue(`, `RecurringJob.AddOrUpdate(`, `[AutomaticRetry`, `[DisableConcurrentExecution`, `ContinueJobWith(`, `HangFire.*` tables | Hangfire jobs | Retries, concurrency rules, continuations, timezones |
| `: BackgroundService`, `IHostedService`, `PeriodicTimer`, `stoppingToken`; `SmartLifecycle`, long loops in `@PostConstruct` | Daemons | What each loop owns, its interval, what happens when it throws |
| `@KafkaListener`, `@RabbitListener`, `concurrency =`, `AckMode`, `@RetryableTopic`, `@DltHandler`; Confluent `IConsumer<`, MassTransit `IConsumer<T>` | Broker consumers | Topics, group ids, ordering keys, retry and DLQ topology, outside producers and consumers |
| `KafkaTemplate`, `RabbitTemplate`, `IPublishEndpoint`, outbox tables, Debezium connectors | Publishing | Dual-write handling, message schemas and keys |
| `@EventListener`, `@TransactionalEventListener`, `ApplicationEventPublisher`; MediatR `INotificationHandler`, `IPipelineBehavior` | In-process events and request pipelines | After-commit semantics; behaviors wrapping every request (validation, logging, transactions) |
| `@Retryable`, `resilience4j.*`, `@CircuitBreaker`, `@Bulkhead`; `AddPolicyHandler`, `AddResilienceHandler`, `AddStandardResilienceHandler` | Resilience | Per-upstream timeouts and retry counts to keep; layers to collapse |
| `: Hub`, `MapHub<`, `IUserIdProvider`, `Groups.AddToGroupAsync`, `AddStackExchangeRedis`, `AddAzureSignalR`; `@MessageMapping`, `enableStompBrokerRelay` | Realtime | Hub methods, group naming, user identity mapping, client platforms and versions |
| `ConcurrentHashMap`, `synchronized`, `ThreadLocal`, MDC; `ConcurrentDictionary`, `lock (`, `SemaphoreSlim`, `AsyncLocal` | Shared state and implicit context | State that is truth vs cache; user and tenant carried implicitly |
| springdoc `@Operation`, Swashbuckle, NSwag, `openapi.json` | API contract | The golden spec for mobile apps and partners |

## Mechanism map

| Legacy mechanism | Usual purpose (why) | Reason tags | Default verdict → Elixir way | Literal-translation trap | Cutover / compat note |
|---|---|---|---|---|---|
| Spring `@Service`/`@Component` singletons, ASP.NET DI `AddScoped`/`AddSingleton` | Wiring, lifecycle, test seams | historical | REPLACE → context modules; behaviour + config + Mox for swappable adapters | Every `@Service` or singleton becomes a named GenServer (Iron Law 13) | Internal only |
| Servlet filters, `HandlerInterceptor`; ASP.NET middleware and MVC filters | Ordered cross-cutting concerns | business | MAP → Plug pipelines; `on_mount` for LiveView | A filter chain of GenServers | Preserve order (`@Order`; `UseRouting` → `UseAuthentication` → `UseAuthorization`) |
| `@ControllerAdvice`/`@ExceptionHandler`, `UseExceptionHandler`, exception filters | Map exceptions to responses | contract | MAP → FallbackController + `Plug.Exception` | `catch (Exception e)` ported as `rescue _ ->` | Spring Boot's default body is `{timestamp, status, error, path}`; RFC 9457 ProblemDetails carry `type`, `title`, `status`, `traceId` |
| `[ApiController]` automatic 400, Bean Validation `@Valid`, FluentValidation | Boundary validation | business | REPLACE → changesets (schemaless for request params); open_api_spex for spec-driven casting | One DTO + validator class + mapper per endpoint | ASP.NET's `ValidationProblemDetails` keys `errors` by PascalCase property name by default; clients parse it |
| DTOs + MapStruct/AutoMapper, Jackson and System.Text.Json settings | Shape the wire format | contract | REPLACE → explicit `*JSON` view functions | `*Mapper` modules per entity; `@derive Jason.Encoder` on schemas | Jackson writes enums as names, System.Text.Json as integers unless `JsonStringEnumConverter`; `long` ids exceed JS precision; .NET `DateTime` with `Kind=Unspecified` has no offset |
| MediatR handlers, Spring `ApplicationEventPublisher` + `@EventListener`, Kafka or RabbitMQ between modules of one app | In-process decoupling, sometimes routed through a broker | historical | REPLACE → direct context calls; PubSub after commit for live processes; DELETE the in-app topic, Oban for durable reactions | A mediator dispatching on struct type; an EventBus GenServer; keeping a topic because "events are events" | DELETE a topic only when its producer and consumer both live in the new release |
| `@TransactionalEventListener(AFTER_COMMIT)`, EF domain events dispatched in `SaveChanges` | Side effects only after commit | business | REPLACE → `Oban.insert` in the same `Ecto.Multi` (durable), or broadcast after `Repo.transact/2` returns `{:ok, _}` | Broadcasting inside the transaction | none |
| `@Transactional` (proxy, propagation, rollback rules) | Declarative unit of work | business | MAP → `Repo.transact/2` or `Ecto.Multi` at the context-function boundary | Propagation emulated with the process dictionary; nested Multis | Spring rolls back on unchecked exceptions only; self-invocation skips the proxy. `REQUIRES_NEW` audit rows have no in-process equivalent: write after the transaction or from another process |
| EF Core `DbContext` change tracking and `SaveChanges` | Implicit dirty tracking and batched writes | historical | REPLACE → explicit changesets with `Repo.insert/update`; `insert_all`/`update_all` for bulk | Emulating change tracking in a process and flushing at the end | `ExecuteUpdate`/`ExecuteDelete` → `Repo.update_all`/`delete_all` |
| JPA `@Entity`, Spring Data repositories, EF entities | ORM | business | MAP → Ecto schemas on the existing tables; queries in contexts | A `*Repository` module per entity; derived-query functions (`find_by_email_and_status`) | Spring Boot maps camelCase to snake_case; check `@Table`/`@Column` overrides. SQL Server via tds 2.3, Oracle via jamdb_oracle 0.5 (low adoption) |
| `@Enumerated` (default `ORDINAL`), `AttributeConverter`, EF value converters | Enum and type mapping | contract | MAP → `Ecto.Enum, values: [a: 0, b: 1]` for ordinal columns; a custom `Ecto.Type` per converter | Storing atom strings in a column that holds ordinals | Ordinals shift when someone reorders the Java enum: freeze the mapping in Ecto |
| `@GeneratedValue(SEQUENCE)` + `allocationSize` 50, SQL Server identity, `uniqueidentifier` | Id generation | contract | MAP → DB-side defaults (identity, `nextval`) with `read_after_writes: true`, or `:binary_id` | Generating ids in Elixir that collide with Hibernate's ranges | Pooled optimizers tolerate outside `nextval` writers, legacy `hilo` does not [U, verify per app]. For `uniqueidentifier` use `:binary_id` or `Tds.Ecto.UUID`, never `Ecto.UUID` |
| Lazy associations, `@ManyToOne` (EAGER by default), Open-Session-in-View (on by default in Spring Boot), EF lazy proxies | Transparent graph navigation | historical | REPLACE → explicit `preload` (Iron Law 6) | Load-on-access in templates; "preload everything" | Each view that relied on OSIV needs explicit preloads |
| Hibernate `@Where`/`@SQLDelete`/`@SoftDelete`, EF `HasQueryFilter` | Global implicit filters (soft delete, tenant) | business | REPLACE → explicit context query scopes; `Repo.prepare_query/3` to assert a tenant filter, not to add one | Silently injecting filters in `prepare_query` | Reports that bypassed filters (`IgnoreQueryFilters`) need explicit unscoped queries |
| `@Inheritance` (SINGLE_TABLE `DTYPE`, JOINED), EF TPH `Discriminator` | Polymorphic entities | contract | MAP → one schema per type over the same table filtered by the discriminator, or one schema with an `Ecto.Enum` type field | Class hierarchies recreated with protocols over one schema | Keep discriminator values (JPA defaults to the entity name, EF to the CLR type name) |
| `@Embeddable`, EF owned types (`OwnsOne`) | Value objects stored in the owner's table | business | MAP → plain prefixed fields plus a struct built in the context; `embeds_one` only for JSON columns | `embeds_one` over relational columns (Ecto embeds need a JSON column) | EF names owned columns `Address_Street` by default |
| `@Version`, EF `[Timestamp]`/`IsRowVersion` | Optimistic locking | business | MAP → `Ecto.Changeset.optimistic_lock/3` on the same integer column | A lock GenServer per record | SQL Server `rowversion` is DB-generated: compare it in an `update_all` `where` and check the count, since `optimistic_lock/3` increments an integer |
| `@PrePersist`, `AuditingEntityListener` (`@CreatedDate`, `@LastModifiedBy`), EF `SaveChangesInterceptor` | Implicit audit fields and side effects | business | REPLACE → changeset functions that take `%Scope{}` for `*_by`; `timestamps/1`; Carbonite 0.17 for full audit | Overriding Repo functions to emulate listeners | Inventory every listener; DB triggers keep both sides consistent during the overlap |
| Flyway, Liquibase, EF migrations | Versioned DDL | business | MAP → Ecto migrations with a `structure.sql` baseline | Translating historical migrations; two toolchains writing DDL | One owner. `ddl-auto=update` in production means drift: dump the real schema |
| HikariCP, Npgsql pooling | Bound connections | reliability, platform | MAP → Repo `pool_size`, `queue_target` | A connection-manager GenServer | Both pools together must fit `max_connections` |
| Hibernate L2 cache, `@Cacheable` (Caffeine or Redis), `IMemoryCache`, `IDistributedCache` | Hide ORM chattiness; share cache across instances | platform | REPLACE → fix N+1 and indexes first; then ETS or Cachex 4.1 with PubSub invalidation; `:persistent_term` | A GenServer cache; caching to hide missing preloads | Invalidation must see legacy writes while the DB is shared |
| `@Async` + `TaskExecutor`, `CompletableFuture.runAsync`; `Task.Run`, `_ = DoAsync()` | Keep work off the request thread | reliability, platform | REPLACE → `Task.Supervisor.start_child` (ephemeral) or Oban (durable) | Bare `spawn`; durable work in a Task | Queued `@Async` work is lost on shutdown today; self-invoked `@Async` methods ran synchronously |
| `CompletableFuture.allOf`, `invokeAll`, Kotlin `coroutineScope`; `Task.WhenAll`, `Parallel.ForEachAsync` | Parallel fan-out | business | MAP → `Task.Supervisor.async_stream_nolink` with `max_concurrency`, `timeout`, `on_timeout: :kill_task` | Unbounded concurrency; `timeout: :infinity` | Keep the legacy degree of parallelism as the starting cap |
| Thread pools, virtual threads, WebFlux/Reactor, Kestrel thread pool tuning | Concurrency within thread limits | platform | DELETE → one process per request on Bandit | Porting `Mono`/`Flux` chains to GenStage | Size the Repo pool, not threads |
| `synchronized`, `ReentrantLock`, `ConcurrentHashMap`; `lock`, `SemaphoreSlim`, `ConcurrentDictionary`, `Interlocked` | Shared-memory safety | platform | DELETE → immutable data; ETS, `:counters`, or one state owner where contention is real | A GenServer mutex around pure functions | none |
| `ThreadLocal`, MDC, `SecurityContextHolder`; `AsyncLocal`, `HttpContext.Items` | Implicit request context | platform | REPLACE → explicit `%Scope{}`, `conn.assigns`, Logger metadata | The process dictionary as ThreadLocal | Pass ids into job args explicitly |
| `@Scheduled(cron/fixedRate)` + ShedLock | Periodic work; ShedLock stops duplicate runs across instances | business | REPLACE → Oban cron (`cron: [crontab: [...]]`, per-entry `timezone:`); DELETE ShedLock | `Process.send_after` loops on every node; Quantum plus a distributed lock | Spring cron has six fields (seconds first), Oban five. Sub-minute `fixedRate` work needs a state-owner timer under highlander_pg, or a rethink |
| Quartz and Quartz.NET (JDBC store `QRTZ_*`, misfire policies, clustering) | Persistent clustered scheduling | business | REPLACE → Oban cron for recurring, `scheduled_at` for one-off; DELETE `QRTZ_*` after cutover | Porting misfire instructions as custom code | Quartz cron adds seconds and `?`. OSS Oban cron skips runs missed while no leader runs; the Oban docs point to Pro Cron for scheduling guarantees |
| Spring Batch (`BATCH_JOB_*` repository, chunk steps, restart) | Restartable bulk processing | business | REPLACE → one Oban job per chunk, or a cursor in job args; `Repo.stream` inside a transaction; Broadway for external sources | A GenStage pipeline for a sequential loop | Persist the cursor; let in-flight runs finish on legacy |
| Hangfire `Enqueue`, `RecurringJob`, `[AutomaticRetry]`, `[DisableConcurrentExecution]`, `ContinueJobWith` | Durable jobs and schedules in SQL Server or Redis | business | REPLACE → Oban workers with string-keyed args; `unique` against duplicate inserts only. `[DisableConcurrentExecution]` exclusion needs a DB lock in `perform/1` or a verified global limit (a `limit: 1` queue is per node); chained jobs or Oban Pro Workflow for continuations; Oban cron for recurring | Serializing method names and arguments as payloads (Hangfire's expression model) | Hangfire retries 10 times by default, Oban 20. Windows timezone ids (`Central Standard Time`) need IANA names. Job ids don't carry over: drain or dual-run |
| `IHostedService`/`BackgroundService` loops (`PeriodicTimer`, `stoppingToken`), `SmartLifecycle` | Pollers, consumers, warmers, singletons | reliability, platform | REPLACE → per purpose: periodic → Oban cron; external queue → Broadway; owns state or a timer → supervised GenServer; startup work → Application start or a release task | One GenServer per hosted service | Since .NET 6 an unhandled `BackgroundService` exception stops the host; supervision restarts instead, so document the new failure behavior |
| `@KafkaListener` (concurrency, ack mode), Spring Cloud Stream, Confluent.Kafka consumers | Broker consumption with backpressure | business | REPLACE → Broadway 1.3 + broadway_kafka 0.7; `partition_by` on the message key keeps per-key ordering | A GenServer poll loop per topic; a Task per message; hand-managed offsets | Start the new consumer group from committed offsets, or shadow-consume and compare |
| `@RabbitListener`, MassTransit, NServiceBus consumers | Queue consumption, retries, DLQs | business | REPLACE → Broadway + broadway_rabbitmq 0.8 (or amqp 4.3); dead-letter exchanges for poison messages | Re-implementing MassTransit's retry and redelivery pipeline | Keep exchange, queue and routing-key names; MassTransit wraps payloads in its own JSON envelope (`messageType`, `message`) |
| Transactional outbox (Debezium, Spring Modulith, MassTransit outbox) | Publish reliably with a DB write | business | REPLACE → `Ecto.Multi` + `Oban.insert` of a publisher job (brod 4.7 or amqp) | A custom outbox table plus a poller GenServer | Keep message keys (partitioning) and schemas (Protobuf via protobuf 0.17) |
| Kafka Streams, ksqlDB stateful processing | Joins, windows, state stores over topics | business | KEEP when other teams own it; REPLACE with Postgres tables + Broadway/Oban when the state is app-local | Rebuilding state stores in ETS | Broadway has no stateful-join equivalent |
| Resilience4j, Hystrix, Spring Retry; Polly via `AddPolicyHandler`/`AddResilienceHandler`; Feign/RestTemplate/typed `HttpClient` | Retries, breakers, bulkheads and timeouts on every call | reliability, platform | REPLACE → Req 0.7 behind a facade per upstream (Iron Law 20): `retry: :transient`, `receive_timeout`, its own Finch pool (bulkhead); Oban backoff; fuse 2.5 when a breaker is justified | Porting Polly or Resilience4j pipelines; retries in mesh + Req + Oban | One retry layer per call path; start from legacy timeouts; keep W3C `traceparent` propagation |
| Spring Security `SecurityFilterChain`, `@PreAuthorize`; ASP.NET `[Authorize(Policy)]` | Authentication and authorization | business | MAP → plugs for authn; policy functions taking `%Scope{}` (Bodyguard 2.4, LetMe 3.0); authorize every `handle_event` (Iron Law 11) | Annotation emulation with macros; authorization only at the router | Port the permission matrix as tests first |
| Form login + `JSESSIONID`/Spring Session; ASP.NET Identity cookies | Browser sessions | business | REPLACE → `mix phx.gen.auth` | Sessions in Redis or a GenServer | Data Protection and Spring Session cookies won't decode: session-exchange endpoint or forced re-login. Angular clients send `X-XSRF-TOKEN`, Phoenix checks `x-csrf-token` |
| Spring `DelegatingPasswordEncoder` (`{bcrypt}$2a$...`), ASP.NET Identity V3 hashes | Verify existing passwords | contract | MAP → bcrypt_elixir after stripping `{bcrypt}`; ASP.NET V3: a small verifier on `:crypto.pbkdf2_hmac/5` that reads PRF, iterations and salt from the header | Forcing a mass password reset | Verify, then rehash on login; keep a `hash_algorithm` column. A `SecurityStamp` change must revoke phx.gen.auth tokens |
| JWT resource server, `AddJwtBearer`; Keycloak, Duende, OpenIddict IdPs | Validate or issue tokens for many clients | contract | MAP → Joken 2.7 + joken_jwks 1.8 (iss, aud, kid, alg); KEEP the IdP; Boruta 2.3 only if you must host OAuth2 in Elixir | Rewriting an IdP inside an app migration; hand-rolled parsing | Spring uses `scope`/`scp`; ASP.NET may map claims to long `ClaimTypes` URIs [U]; match clock-skew leeway |
| SignalR hubs (groups, `Clients.User`, streaming), STOMP over Spring WebSocket; Redis backplane, Azure SignalR, broker relay | Push to browsers and apps across instances | business | REPLACE → Phoenix Channels (`"user:#{id}"` topics for `Clients.User`, one topic per group) or LiveView; DELETE the backplane (PubSub PG) | A hand-written SignalR or STOMP server; a hub GenServer per group | Not wire-compatible and no Hex server. Multi-server SignalR needs sticky sessions unless WebSockets-only with skip-negotiation or Azure SignalR [U]. SHIM only for clients that cannot update |
| Akka, Akka.NET, Orleans grains, Dapr actors | The actor model retrofitted onto a shared-memory runtime | platform | DELETE the framework → GenServer/`:gen_statem`, Registry + DynamicSupervisor; Horde 0.10 or syn 3.4 only for cluster-unique hot state | A grain per CRUD entity writing through to the DB | Migrate grain and journal storage to Ecto tables |
| Blazor Server circuits, Vaadin | Server-held UI state over a socket | business | REPLACE → LiveView, the closest model (`../ui-strategy.md`) | Re-implementing the circuit protocol | Port page by page behind reverse_proxy_plug |
| Actuator, ASP.NET HealthChecks, Micrometer, OTel agents | Ops endpoints and metrics | business | MAP → a `/health` plug; Telemetry.Metrics + PromEx 1.12; opentelemetry 1.7 with Phoenix, Ecto and Oban instrumentation | Liveness probes that query the DB | Keep probe paths and the metric names alerts use |
| `application.yml` profiles, Spring Cloud Config; `appsettings.{Env}.json`, `IOptions`, Azure App Configuration | Config | business | MAP → `config/runtime.exs` from env or a secret manager | A config server polled by a GenServer | Keep env var names, including .NET `__` nesting |

## Disappears on the BEAM (DELETE candidates)

- ShedLock, Quartz cluster tables, Hangfire server coordination: once Oban owns the jobs and legacy schedules are off.
- Thread pools, executors, virtual-thread and Kestrel tuning, Reactor/WebFlux plumbing: always.
- `synchronized`, `lock` and concurrent collections around in-memory state: when ownership moves to ETS or one process.
- ThreadLocal, MDC, `AsyncLocal` and `SecurityContextHolder` propagation helpers: always. Explicit `%Scope{}` and Logger metadata replace them.
- Polly and Resilience4j stacks: always for calls that became function calls. Collapse the rest to Req + Oban + supervisors.
- MediatR and `ApplicationEventPublisher` used as in-app buses: when no external consumer exists.
- Kafka or RabbitMQ topics whose producer and consumer both move into the new release.
- Akka, Orleans and Dapr actor runtimes: always. OTP is the native model; migrate grain storage first.
- SignalR Redis backplane, Azure SignalR Service, STOMP broker relay: when the nodes cluster and clients have moved.
- Hibernate L2 cache: after N+1 and index fixes. Add ETS or Cachex only where a measurement still asks for it.
- Repository, UnitOfWork, AutoMapper and MapStruct layers: always. Ecto plus explicit views covers them.
- Eureka/Consul discovery and internal API gateways between services merged into one release.

## Keep or shim (with conditions)

- Kafka as a cross-team event backbone: KEEP. Consume with Broadway + broadway_kafka, publish from an Oban outbox job.
- RabbitMQ or Azure Service Bus with outside producers: KEEP. Service Bus has no Broadway producer on Hex, so it needs a
  custom producer or a bridge to a supported broker.
- SQL Server or Oracle shared during the strangler: KEEP with tds 2.3.8 (active) or jamdb_oracle 0.5.12 (low adoption,
  record the risk). One DDL owner.
- External IdP (Keycloak, Entra ID, Okta): KEEP. Log in with Assent or Ueberauth, validate tokens with Joken + joken_jwks.
- Temporal or Camunda workflows that span other teams' services: KEEP. Use the community temporalio SDK [U official status]
  or a thin HTTP/gRPC bridge.
- SignalR or STOMP clients that cannot update: SHIM. Keep the legacy hub as a relay fed by a broker the Elixir app publishes
  to: migration-only until a client-version threshold, or permanently with an owner, support policy and conformance tests.
  Do not implement the SignalR protocol in Elixir.
- Spring Batch or Hangfire runs already in flight: temporary KEEP until they finish on the legacy side.
- Service mesh mandated by the platform: KEEP. Allow or exclude distribution ports and pick one retry layer.
- JVM/.NET-only libraries (PDF or Office generation, vendor SDKs): KEEP as an HTTP sidecar until an Elixir option is proven.

## Questions the architect must ask

1. Which beans or services hold real mutable state? Why: only those are process candidates; the rest become modules.
2. Where are the `@Transactional`/`SaveChanges` boundaries, and which rely on rollback rules, `REQUIRES_NEW` or proxy
   self-invocation quirks? Why: Ecto makes boundaries explicit, so each quirk turns into a visible behavior change.
3. Which `@Async`, `Task.Run` and `IHostedService` work must survive a restart? Why: durable work goes to Oban, the rest to Task.Supervisor.
4. What is the full scheduler inventory: expressions, timezones, misfire policy, concurrency rules, retry counts? Why: Oban
   cron uses five fields and OSS cron does not backfill missed runs.
5. For every Kafka or RabbitMQ topic: who else produces or consumes, which key orders messages, where do poison messages go?
   Why: it decides KEEP or DELETE, and Broadway `partition_by`.
6. Which JPA/EF mapping quirks exist (ordinal enums, sequence allocation, discriminators, soft-delete filters, owned types,
   `rowversion`)? Why: they are data contracts on the shared database.
7. Which views depend on lazy loading or OSIV? Why: each one becomes an explicit preload.
8. Who are the SignalR or STOMP clients, on which platforms and versions, and can they be force-updated? Why: it sets how
   long a SHIM lives.
9. Which auth artifacts must survive (hash formats, Data Protection keys, JWT issuers, `SecurityStamp`)? Why: it sets the
   rehash, session-exchange and token-acceptance plan.
10. Which error and validation envelopes (ProblemDetails, Spring Boot's default error) do clients parse? Why: byte compatibility.
11. Which database engine is shared during the overlap? Why: adapter maturity differs (tds is active, jamdb_oracle has low
    adoption), and both connection pools count against one limit.
12. Does the platform mandate a service mesh, and can nodes run distributed Erlang? Why: retry ownership and PubSub topology.
13. Which actor-framework state is hot, and which is DB write-through? Why: most grains become Ecto rows, not processes.
14. What parity and performance bar applies (shadow traffic, golden vectors, harness, targets)? Why: agents meet the bar you set.

## Libraries (versions checked by the plugin author on hex.pm, 2026-10-09; re-check before pinning)

| Need | Package | Version | Notes |
|---|---|---|---|
| Web framework | phoenix | 1.8.15 | Scopes thread tenant and user through contexts |
| Server UI | phoenix_live_view | 1.2.12 | Replaces Thymeleaf, Razor Pages, Blazor Server |
| Data | ecto / ecto_sql / postgrex | 3.14.2 / 3.14.0 / 0.22.4 | `Repo.transact/2`, `prepare_query/3` |
| SQL Server | tds | 2.3.8 | Use `:binary_id` or `Tds.Ecto.UUID` for `uniqueidentifier` |
| MySQL / Oracle | myxql / jamdb_oracle | 0.9.0 / 0.5.12 | jamdb_oracle has low adoption |
| Jobs and cron | oban / oban_web | 2.24.1 / 2.13.1 | Replaces Quartz, Hangfire, ShedLock, `@Async` for durable work |
| Broker consumers | broadway / broadway_kafka / broadway_rabbitmq / broadway_sqs | 1.3.0 / 0.7.0 / 0.8.2 / 1.0.0 | `partition_by` for key ordering |
| Kafka and AMQP clients | brod / amqp | 4.7.0 / 4.3.0 | Producers from Oban outbox jobs |
| HTTP client | req / finch | 0.7.5 / 0.24.0 | One Finch pool per upstream as a bulkhead |
| Circuit breaker | fuse | 2.5.0 | Dormant but mature; only with evidence |
| Rate limiting | hammer | 7.5.0 | Replaces Bucket4j and the ASP.NET RateLimiter |
| Cache | cachex | 4.1.1 | Replaces `@Cacheable`/`IMemoryCache` where still needed |
| Auth tokens | joken / joken_jwks | 2.7.0 / 1.8.0 | Validate the existing IdP's tokens |
| OAuth login | assent / ueberauth | 0.3.1 / 0.10.8 | Keep redirect URIs and client ids |
| Password hashes | bcrypt_elixir / argon2_elixir; PBKDF2 on `:crypto` | 3.3.2 / 4.1.3 / OTP | ASP.NET V3 needs a custom verifier on `:crypto`; `pbkdf2_elixir` loops in Elixir and starves the schedulers |
| OAuth2 server (rare) | boruta | 2.3.8 | Only if the IdP must live in Elixir |
| Authorization | bodyguard / let_me | 2.4.3 / 3.0.4 | Replaces `@PreAuthorize` and policies |
| Audit | carbonite | 0.17.0 | Replaces entity listeners for audit trails |
| Field encryption | cloak_ecto | 1.3.0 | Re-encrypt legacy ciphertext with a backfill job |
| API contract | open_api_spex | 3.22.4 | Import the springdoc/Swashbuckle spec as the golden contract |
| GraphQL | absinthe / absinthe_phoenix | 1.12.0 / 2.0.5 | Replaces Spring for GraphQL, HotChocolate |
| Event sourcing (real need only) | commanded / eventstore | 1.4.11 / 1.4.10 | Not for "we had a command bus" |
| Distributed registry | horde / syn | 0.10.0 / 3.4.2 | Horde is eventually consistent |
| Cluster singleton | highlander_pg | 1.0.8 | Sub-minute scheduled singletons |
| gRPC and Protobuf | grpc / protobuf | 1.0.5 / 0.17.1 | Remaining non-BEAM peers |
| Metrics | prom_ex | 1.12.0 | Replaces Micrometer dashboards |
| Tracing | opentelemetry | 1.7.0 | Keep W3C trace context across the strangler |
