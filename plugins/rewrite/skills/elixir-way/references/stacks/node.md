# Node.js → Elixir

Covers Express, NestJS, Fastify, Next.js/Remix full-stack apps, Socket.io, BullMQ, Prisma/TypeORM/Sequelize/Drizzle and Mongoose.
Read it alongside the verdict vocabulary (MAP, REPLACE, KEEP, SHIM, DELETE, UNDECIDED) and the reason tags in the elixir-way SKILL.md.
Frontend choices (keep the React/Next UI, LiveView, Inertia) are covered in `../ui-strategy.md`. `[U]` marks a detail not re-verified on 2026-10-09.

## Probe: where mechanisms hide

| Look at | What it reveals | Contract or purpose to capture |
|---|---|---|
| `package.json` `scripts`, `ecosystem.config.js`, `pm2*.json`, `Procfile`, Dockerfile `CMD`, compose/k8s manifests | Process roles (api, worker, cron), PM2 `instances` and `exec_mode: cluster`, replica counts | Which state is per worker today (caches, timers, rate counters) and which schedules run N times |
| `app.use(`, `router.use(`, `express.json({ limit`, `app.set('trust proxy'`, `caseSensitive`, `strict` | Middleware order, body limits, proxy trust, routing flags | Order is behavior (auth before parsers?), 413 thresholds, case-insensitive and trailing-slash route matching |
| 4-arity handlers `(err, req, res, next)`, `setErrorHandler(`, `@Catch(`, `APP_FILTER`, `useGlobalFilters(` | Global error mapping | Exact error envelope, status codes, which internal messages leak to clients |
| `process.on('uncaughtException'`, `'unhandledRejection'`, `'SIGTERM'`, `server.close(`, `@nestjs/terminus`, `/healthz` | Crash and shutdown policy | Drain time, health paths the load balancer and k8s probe |
| `@Module(`, `providers:`, `useFactory`, `Scope.REQUEST`, `forRootAsync(`, Inversify/awilix containers | DI graph, request-scoped state, swappable implementations | Which providers hold real state and which only wire; test seams worth keeping as behaviours |
| `@UseGuards(`, `@UseInterceptors(`, `@UsePipes(`, `APP_GUARD`, `APP_INTERCEPTOR`, `@Roles(`, CASL `defineAbility` | Authorization, response wrapping, logging and caching interceptors | Permission matrix; response wrapper shape (`{ data, meta }`); excluded fields |
| `ValidationPipe({`, `whitelist`, `forbidNonWhitelisted`, `transform: true`, class-validator decorators, `z.object(`, `Joi.object(` | Validation and coercion rules | Unknown-field policy (strip or 400), string-to-number coercion, error text clients display |
| Fastify `schema: {` (`body`, `response`), `addSchema(`, `register(`, `fastify-plugin`, `addHook(`, `decorate(` | JSON Schemas, encapsulated hooks, serializer | Response schemas silently drop undeclared fields, so that absence is a contract; hook order per context |
| `app/**/page.tsx`, `route.ts`, `middleware.ts`, `"use server"`, `getServerSideProps`, `loader`/`action` exports, `revalidate` | Server data loading, mutations, edge logic | SEO routes, cache lifetimes, which API routes only the own UI calls |
| `next.config.*` (`redirects`, `rewrites`, `headers`), `vercel.json` `crons`, `netlify.toml`, `serverless.yml` | Redirect maps, platform schedules, function limits | Redirect status codes, cron expressions, constraints the design obeyed (cold starts, execution time caps) |
| `new EventEmitter`, `.emit(`, `@OnEvent(`, `EventBus`, `CommandBus`, `@Saga(` | In-app events and CQRS buses | Which listeners must run after commit, which must be durable, which are only indirection |
| `setInterval(`, `setTimeout(`, `node-cron`, `cron.schedule(`, `@Cron(`, `@Interval(`, `repeat:`, `upsertJobScheduler(` | Timers and recurring work | Expressions and timezones; whether duplicate runs across processes are tolerated or relied upon |
| `new Queue(`, `new Worker(`, `@Processor(`, `FlowProducer`, `attempts`, `backoff`, `jobId`, `limiter`, `concurrency`, `priority` | Job topology | Per-queue retries, dedupe keys, global rate limits, priorities, stalled-job handling, non-Node producers |
| `node:worker_threads`, `piscina`, `child_process`, `spawn(`, `execFile(` | CPU offload and external binaries | Which binaries are real dependencies (ffmpeg, Chromium) and which threads only protect the event loop |
| `io.on('connection'`, `socket.join(`, `.to(` + `.emit(`, `io.use(`, `createAdapter(`, `@WebSocketGateway(`, `connectionStateRecovery` | Realtime topology and protocol | Event names, room naming, ack payloads, handshake auth fields, client platforms and whether they can update |
| `schema.prisma`: `@map`, `@@map`, `@updatedAt`, `@default(cuid())`, implicit m-n relations; `$extends(`, `$use(` | Table and column mapping, client-side defaults, middleware | Values the DB does not generate (Ecto must), soft-delete or tenant middleware |
| TypeORM `@Entity`, `synchronize`, `@VersionColumn`, `@DeleteDateColumn`, subscribers; Sequelize `paranoid`, `underscored`, `hooks:`; `drizzle.config.*` | ORM implicit behavior | Soft-delete filters, version columns, naming strategy, who owns DDL |
| `mongoose.Schema(`, `.pre(`, `.post(`, `.virtual(`, `.populate(`, `discriminator(`, `toJSON` transforms, `versionKey` | Document shape, hooks, API serialization | `_id` exposure, embedded vs referenced data, whether the data is relational in practice |
| `$transaction(`, `QueryRunner`, `sequelize.transaction(`, `cls-hooked`, `AsyncLocalStorage` | Transaction boundaries and implicit context | Atomic units; values that ride implicitly (user, tenant, request id) |
| `ioredis`, `createClient(`, `redlock`, `NX`, `rate-limit-redis`, `connect-redis`, `cache-manager` | Every Redis use | One row per use (cache, session, lock, limiter, queue, pub/sub) and whether another service reads the keys |
| `p-retry`, `axios-retry`, `opossum`, `bottleneck`, `p-limit`, `Promise.all(`, `AbortSignal.timeout(` | Resilience and fan-out | Timeouts, retry counts, concurrency caps that protect a downstream quota |
| `jsonwebtoken`, `jwt.sign(`, `passport.use(`, `express-session`, `cookie-session`, `next-auth`, `@auth/`, `bcrypt`, `argon2` | Auth artifacts | Token algorithm, keys, claims, expiry; cookie names; hash formats that must keep verifying |
| `openapi.*`, `@nestjs/swagger`, `swagger-jsdoc`, `/v1/` prefixes, app-version headers | API contract | The spec mobile apps and partners code against; client-version telemetry |
| `dotenv`, `process.env.`, `ConfigModule.forRoot(`, `convict` | Config surface | Env var names that deploy manifests already set |

## Mechanism map

| Legacy mechanism | Usual purpose (why) | Reason tags | Default verdict → Elixir way | Literal-translation trap | Cutover / compat note |
|---|---|---|---|---|---|
| Express/Fastify middleware, Nest middleware, Fastify plugins and hooks | Cross-cutting request concerns in a fixed order | business | MAP → Plug in the `Endpoint`, router `pipeline`s and `scope`s, LiveView `on_mount` | Middleware as GenServers; a plug that `GenServer.call`s one global process per request; emulating Fastify encapsulation | Express matches routes case-insensitively by default and Phoenix does not: emulate it (or `X-Powered-By`, weak ETags, the HTML 404) only for a `contract` with a named consumer, otherwise record a divergence. Keep 413 limits via `Plug.Parsers` `length:` |
| Global error handlers (4-arity middleware, `setErrorHandler`, Nest exception filters) | Map errors to JSON while keeping the single process alive | contract | MAP → `action_fallback` FallbackController, `Plug.Exception` impls, `ErrorJSON` | `try/rescue` around every action; `rescue _ ->` swallowing bugs | Nest's default body is `{statusCode, message, error}` and `message` is a string array for validation errors |
| `uncaughtException`/`unhandledRejection` handlers, PM2 auto-restart | One thrown error can take down every in-flight request | platform | DELETE → each request is its own process; supervisors restart crashed children | A catch-all in the endpoint that turns crashes into 200s | Remove PM2 restart config; keep the health path |
| PM2 cluster mode, `node:cluster`, `instances: max` | Use all cores from a single-threaded loop | platform | DELETE → BEAM schedulers run on every core | Several BEAM nodes per host | Per-worker caches, counters and rooms become per node; find tests that assumed per-worker state |
| NestJS modules and providers, Inversify/awilix | Wiring and test seams | historical | REPLACE → plain context modules; behaviour + config + Mox 1.3 for swappable adapters | Every `@Injectable()` becomes a named GenServer (Iron Law 13); a "container" registry process | Internal only |
| Request-scoped providers, `AsyncLocalStorage`, `cls-hooked` | Carry user, tenant and request id through interleaved async code | platform | REPLACE → explicit `%Scope{}` (Phoenix 1.8), `conn.assigns`, Logger metadata | The process dictionary as ALS; it vanishes in Tasks and Oban jobs | Put user and tenant ids into job args explicitly (Iron Law 25 generalized) |
| Nest guards, `@Roles`, CASL abilities | Per-route and per-action authorization | business | MAP → router plugs plus context policy functions (Bodyguard 2.4, LetMe 3.0) that take `%Scope{}` | Authorization only in a router plug, so LiveView events bypass it (Iron Law 11) | Port the permission matrix as tests before the code |
| Interceptors: response wrapping, `ClassSerializerInterceptor` + `@Exclude`, timing | Shape responses, hide fields, cross-cutting logging | contract | MAP → explicit `*JSON` view functions; `:telemetry` handlers for timing | `@derive Jason.Encoder` on Ecto schemas, which leaks fields | Keep the wrapper shape and the excluded fields exactly |
| class-validator + `ValidationPipe`, zod, Joi | Boundary validation, coercion, unknown-field policy | business | REPLACE → schemaless or embedded changesets; open_api_spex 3.22 `CastAndValidate` when a spec exists | Porting every zod/Joi schema 1:1 next to changesets; validating in controller and context | `whitelist` behaves like `cast` dropping keys; `forbidNonWhitelisted` needs an explicit unknown-key 400; keep message text |
| Fastify JSON Schema (`schema.body`, `schema.response`) | Validation plus fast serialization | contract | MAP → reuse the schema files with ex_json_schema 0.11 in a plug, or import them into open_api_spex; explicit JSON views | Hand-translating schemas and losing `additionalProperties` and `coerceTypes` semantics | Response schemas drop undeclared properties, so a view that adds fields changes the contract |
| Next.js pages/RSC, `getServerSideProps`, server actions; Remix loaders and actions | Server-side data and mutations for SSR, SEO and forms | business | REPLACE → LiveView `mount`/`handle_params`/`handle_event` + changesets, or Inertia props (`../ui-strategy.md`) | Loading SEO content with `assign_async` (it runs only once connected); repeating the same query on both mounts (Iron Law 1); JSON endpoints only for your own LiveView | The disconnected render is the SEO HTML: load its content synchronously or from a cache; keep URLs and `<head>` metadata |
| Next.js route handlers, API routes, Remix resource routes | JSON for the SPA, mobile apps, partners | contract | MAP → controllers + `*JSON` views + open_api_spex golden tests | Keeping BFF routes that only the replaced UI used | Delete a route only after access logs show no other caller |
| `middleware.ts`, `next.config` redirects, rewrites, headers | Edge auth, i18n, redirects | business | MAP → endpoint and router plugs, `on_mount`; rewrites to other hosts → reverse_proxy_plug 3.0 | Re-creating edge-runtime semantics | Copy redirect maps verbatim; Next uses 308 for `permanent: true` and 307 otherwise |
| ISR, `revalidate`, `unstable_cache`, fetch cache | Cheap reads despite serverless cold starts | platform | REPLACE → `Cache-Control` + CDN; Cachex 4.1 for fragments; NimblePublisher 2.1 for content compiled into the release | An ISR emulator built from GenServers | Keep CDN cache keys and purge hooks |
| `next/image` optimizer, sharp | Responsive images | business | KEEP a CDN image service, or REPLACE → resize on upload in an Oban job with `image` 0.72 (libvips via Vix) | Resizing inside the request path | Keep image URLs stable |
| tRPC | End-to-end types for the own UI | historical | REPLACE → LiveView (no API at all) or REST/GraphQL with generated TS clients | Re-implementing the tRPC wire protocol | Hex has no tRPC server; a kept tRPC SPA must move to REST or GraphQL |
| Socket.io server: rooms, namespaces, acks, `io.use` auth | Bidirectional push to browsers and apps | business | REPLACE → Phoenix Channels (topic = room, `{:reply, ...}` = ack, `join/3` = handshake auth) or LiveView | A hand-written Engine.IO server; a "hub" GenServer holding every socket | Not wire-compatible and no maintained Hex server; SHIM only for clients that cannot update (below) |
| `@socket.io/redis-adapter`, Redis pub/sub backplane, sticky sessions | Each instance knows only its own sockets; polling transport state is per instance | platform | DELETE → Phoenix.PubSub 2.4 PG adapter + dns_cluster 0.3 or libcluster 3.5; Phoenix LongPoll routes through PubSub | Redis pub/sub between nodes that can cluster; keeping LB affinity "because Socket.io needed it" | phoenix_pubsub_redis 3.1 only where nodes cannot cluster; keep affinity while legacy still serves sockets |
| `connectionStateRecovery`, client replay buffers | Recover missed events after a reconnect | business | REPLACE → join params carry the last-seen id; `join/3` replays from the DB; PubSub delivers the live tail | Treating PubSub as durable | PubSub is at-most-once |
| BullMQ/Bee queues and workers | Durable off-request work that survives a restart | business | REPLACE → Oban 2.24 workers, queues with `limit`, Oban Web 2.13 | A Redis list queue via Redix (the once-campfire mistake); `Task.start` for durable work | BullMQ defaults to 1 attempt, Oban to 20: set `max_attempts` per worker. Drain, or dual-run idempotent jobs |
| BullMQ `jobId` dedupe, `removeOnComplete`, stalled-job detection | Exactly-once-ish enqueue, storage hygiene, recovery from crashed workers | business | MAP → Oban `unique: [keys: ..., period: ...]`, `pruner: [max_age: ...]`, `lifeline: [rescue_after: ...]` (2.24 service config) | Dedupe in ETS; heartbeat GenServers | Match the legacy dedupe window; set `rescue_after` above the longest job runtime |
| BullMQ `limiter`, group rate limits | Respect a third-party quota across all workers | business | REPLACE → per node: queue `limit` + Hammer 7.5 or an `:atomics` limiter; cluster-wide: Oban Pro global limits | A GenServer limiter with the cast/call ordering race | OSS Oban limits are per node, so the effective rate is limit × nodes |
| Repeatable jobs, `node-cron`, `@nestjs/schedule`, Vercel crons | Periodic work | business | REPLACE → Oban cron: top-level `cron: [crontab: [...]]` (module `Oban.Cron`, Oban 2.24+), per-entry `timezone:`; the old `Oban.Plugins.Cron` name is deprecated and delegates | node-cron under PM2 runs once per worker; `Process.send_after` loops on every node | Disable the legacy schedule when Oban's starts; check whether a duplicate run was masking a bug |
| BullMQ `FlowProducer` parent and child jobs | Fan-out and fan-in pipelines | business | REPLACE → `Ecto.Multi` when the steps are atomic; chained Oban jobs; Oban Pro Workflow for DAGs | A GenServer per flow holding progress in memory | Let in-flight flows finish on legacy |
| `worker_threads`, piscina, sandboxed processors | Keep CPU work off the event loop | platform | DELETE → preemptive schedulers; Rustler dirty NIFs or FLAME 0.5 only for native or burst work | A Port pool for code the BEAM runs fine | none |
| `child_process.spawn` of ffmpeg, Chromium, LibreOffice | Reuse native tools | business | MAP → `System.cmd/3` or a Port inside an Oban job; MuonTrap 2.0 when the child must die with its owner | Running external tools in the request process with no timeout | Pin binary versions in the image |
| EventEmitter, `@OnEvent`, Nest CQRS `EventBus`/`CommandBus` | Decouple modules inside one process | historical | REPLACE → direct context calls; `Phoenix.PubSub.broadcast` after commit; Oban inserted in the same `Ecto.Multi` for durable reactions | An EventBus GenServer; a mediator dispatching on struct type; broadcasting before commit | If other services listen, publish from an Oban outbox job |
| Un-awaited promises, `setImmediate`, `void doThing()` | Don't block the response | reliability, platform | REPLACE → `Task.Supervisor.start_child` (ephemeral) or Oban (durable) | Bare `spawn`/`Task.start` (Iron Law 14) | Capture locale and OTel context before spawning (Iron Law 25) |
| `Promise.all`, `Promise.allSettled` | Parallel I/O to cut latency | business | MAP → `Task.Supervisor.async_stream_nolink(sup, items, f, max_concurrency: n, timeout: ms, on_timeout: :kill_task)` | `Promise.all` → `Task.async_stream` with `timeout: :infinity`, linked to the request, `max_concurrency` above the Finch pool | Size `max_concurrency` to the downstream pool and quota |
| `async/await` on every I/O call | Non-blocking I/O on one thread | platform | DELETE → sequential code; the process blocks, the scheduler runs others | `Task.async(f) \|> Task.await()` one-liners | none |
| `setInterval` refresh of in-memory tokens, config, lookups | Keep process-local data fresh | reliability, platform | REPLACE → one supervised state owner with `Process.send_after`, or `:persistent_term` refreshed by an Oban cron job | Timers on every node for cluster-wide work | none |
| `lru-cache`, `node-cache`, `cache-manager` memory store | Latency; each PM2 worker holds its own copy | platform | REPLACE → ETS (`read_concurrency: true`) or Cachex 4.1 per node with PubSub invalidation; `Cachex.fetch/4` runs one fallback per key for concurrent misses | An Agent or GenServer map read by every request | While the DB is shared, invalidation must also see legacy writes (TTL or triggers) |
| Prisma schema and client | Typed data access | business | MAP → Ecto 3.14 schemas on the existing tables; composable `Ecto.Query` in contexts | A `UserRepository` module per model wrapping `Repo` | `@map`/`@@map` → `source:`; PascalCase tables need `schema "User"`; `@updatedAt`, `cuid()` and `uuid()` come from the Prisma client, so Ecto must generate them; implicit m-n tables `_AToB` have columns `A` and `B` |
| Prisma middleware/`$extends`, Sequelize hooks, TypeORM subscribers | Implicit soft delete, audit, tenant filters, timestamps | business | REPLACE → explicit changeset functions, `Ecto.Multi` steps, context query scopes; Carbonite 0.17 for trigger-based audit | Overriding Repo callbacks to re-create hooks; sending email inside the transaction | Sequelize `paranoid: true` adds `"deletedAt" IS NULL` to every query; inventory every hook and give each a home |
| TypeORM `synchronize`, `prisma db push`, `drizzle-kit push` | Dev-time schema sync | historical | DELETE → Ecto migrations baselined from `structure.sql` | Two migration toolchains writing one DB | One DDL owner during the strangler; `_prisma_migrations` and `schema_migrations` can coexist |
| `$transaction`, TypeORM `QueryRunner`, `sequelize.transaction` (CLS) | Atomic multi-statement writes | business | MAP → `Repo.transact/2` or `Ecto.Multi`; `Oban.insert(multi, :job, changeset)` is the outbox | CLS-managed transactions emulated with the process dictionary | Prisma interactive transactions time out (5 s default [U]); find long ones before porting |
| `include`, `populate`, TypeORM eager/lazy relations | Navigate the object graph | business | MAP → explicit `preload`: separate queries for has_many, join for belongs_to (Iron Law 6) | Load-on-access in templates (N+1 in render); preloading the whole graph | none |
| Mongoose models: subdocuments, `populate`, virtuals, `pre('save')`, discriminators | Flexible documents | business | REPLACE → Postgres + Ecto with `embeds_one`/`embeds_many` and `:map` (JSONB) when the data is relational in practice; KEEP Mongo via mongodb_driver 1.6 behind a context when others own it | mongodb_ecto (low adoption) as the default; one table per subdocument | `_id` is a 24-char hex ObjectId, so keep it as a string key; `toJSON` transforms define the API shape (`id`, `_id`, `__v`) |
| JS `number` money, `Date` serialization | Convenience | historical | REPLACE → `Decimal` 3.1 or integer cents (Iron Law 4); explicit datetime formatting in views | `:float` fields because JS used `number` | `toISOString()` emits 3-digit milliseconds + `Z`, `:utc_datetime_usec` emits 6; `JSON.stringify` drops `undefined` keys, so render missing vs `null` deliberately |
| express-session + connect-redis, cookie-session, Auth.js/NextAuth sessions | Browser sessions on stateless instances | business | REPLACE → `mix phx.gen.auth` (cookie session + `users_tokens`) | A session GenServer; sessions in ETS | `connect.sid` and Auth.js encrypted cookies are impractical to decode: session-exchange endpoint or forced re-login |
| Passport strategies, `jsonwebtoken` bearer tokens | Login and API auth | contract | REPLACE → phx.gen.auth + Assent 0.3 or Ueberauth 0.10 for OAuth; Joken 2.7 (+ joken_jwks 1.8 for an IdP) for existing tokens | Porting the Passport strategy abstraction; hand-parsing JWTs | Accept existing mobile tokens until expiry (same alg, keys, claims); bcrypt `$2b$` verifies with bcrypt_elixir, rehash on login |
| express-rate-limit + rate-limit-redis, `@nestjs/throttler` | Abuse protection | business | REPLACE → Hammer 7.5 in a plug with an ETS sliding window | A GenServer counter; Redis for a single node | Keep the 429 body and `Retry-After`/`RateLimit-*` headers |
| p-retry, axios-retry, opossum, bottleneck; axios/got clients | Survive transient upstream failures without supervision | reliability, platform | REPLACE → Req 0.7 behind a facade (Iron Law 20): `retry: :transient`, `receive_timeout`, a named Finch pool per upstream; Oban backoff; fuse 2.5 only with evidence | Porting opossum; stacking retries in Req, Oban and the caller | One retry layer per call path; start from the legacy timeouts |
| SSE via `res.write`, streaming responses | One-way push, LLM token streams | business | MAP → `send_chunked/2` + `chunk/2` in a controller subscribed to PubSub, or LiveView streams | A GenServer per SSE client (the conn process already is one) | Keep event names and `Last-Event-ID` resume semantics |
| nodemailer | Transactional email | business | REPLACE → Swoosh 1.29 delivered from an Oban job | Sending inside the DB transaction | Keep templates and sender addresses |

## Disappears on the BEAM (DELETE candidates)

- PM2 cluster mode, `node:cluster`, several app processes per container: always. One release per host uses every core.
- `uncaughtException`/`unhandledRejection` handlers and PM2 restart policies: always. Keep only the reporting part (Logger, Sentry).
- `worker_threads`, piscina and sandboxed processors that exist to protect the event loop: when the work is plain Elixir.
  Keep a Port or NIF only for a native library.
- Socket.io Redis adapter, Redis pub/sub backplane, sticky sessions: when the nodes can run distributed Erlang and the
  legacy gateway no longer serves sockets.
- `AsyncLocalStorage`/cls-hooked plumbing: always. Explicit `%Scope{}` and Logger metadata replace it.
- In-process EventEmitter and CQRS buses between modules of one app: when no external service consumes the events.
- `async/await` plumbing and local promise utilities (`p-map`, `p-limit`): always. Keep each concurrency cap as `max_concurrency`.
- Per-worker memory caches, and a Redis cache only this app reads: when ETS or Cachex per node plus invalidation meets the
  freshness requirement.
- `redlock` and `SET NX` locks: when a unique constraint, `pg_advisory_xact_lock` or one cluster-wide registered process
  covers the case. Oban `unique` covers only a lock that merely stopped duplicate enqueues.
- BFF API routes, tRPC routers, React Query/Redux layers for the own web UI: only after the UI moves to LiveView or Inertia
  and access logs show no other caller.
- ISR and `revalidate` machinery: when the app stops running serverless. CDN plus cache headers remain.
- TypeORM `synchronize` and `db push`: always, once Ecto migrations own DDL.

## Keep or shim (with conditions)

- React/Next frontend as an SPA over a JSON API: KEEP when `../ui-strategy.md` points there (offline, heavy client state,
  separate frontend team). Phoenix serves the same contract, proven by open_api_spex golden tests.
- Socket.io gateway: SHIM for clients that cannot update (shipped mobile builds, devices). Run a thin Node Socket.io process
  that relays from a channel the Elixir side publishes to (phoenix_pubsub_redis or Redix): migration-only with a
  client-version removal milestone, or a permanent supported adapter with an owner and support policy. Do not write an
  Engine.IO server in Elixir.
- Redis: KEEP when other services read the same keys or streams, or the nodes cannot cluster. Access it through Redix 1.9
  behind a context.
- MongoDB: KEEP when another team owns the collections or moving the data is out of scope for this phase. Use mongodb_driver
  1.6 behind a context facade and plan the Postgres move as its own phase.
- BullMQ producers outside this app: SHIM during the overlap. They call a Phoenix endpoint that inserts Oban jobs, or insert
  rows into `oban_jobs` directly [U: check column defaults for your Oban version]. Hex has no BullMQ-format consumer.
- Kafka, RabbitMQ, SQS: KEEP when cross-team. Consume with Broadway 1.3, publish from an Oban outbox job.
- Node-only libraries (Puppeteer PDF rendering, vendor SDKs): KEEP as an HTTP sidecar or a `nodejs` 3.1.4 worker pool
  (3.1.4 fixes CVE-2026-33872). Revisit once an Elixir option is proven.
- External IdP (Auth0, Clerk, Cognito): KEEP. Validate its tokens with Joken + joken_jwks.
- CDN and edge (Vercel, Cloudflare): KEEP for caching and WAF. App logic moves into plugs.

## Questions the architect must ask

1. How many Node processes serve traffic (PM2 `instances`, replicas), and which in-memory state differs per process?
   Why: per-worker caches, timers and rate counters look like contracts but are accidents of the topology.
2. Which clients speak Socket.io, and can each one be force-updated? Why: this decides REPLACE with Channels, a migration-only SHIM or a permanent supported adapter.
3. Is the React/Next/Remix frontend staying? Why: it decides whether API routes are a contract or a deletable BFF.
4. For every BullMQ queue: is it durable, idempotent, deduped by `jobId`, rate-limited, prioritized, fed by non-Node producers?
   Why: each answer maps to an Oban option, and the defaults differ (1 attempt vs 20).
5. Which ORM hooks, middleware and client-side defaults run implicitly (`@updatedAt`, `cuid()`, `paranoid`, tenant `$extends`)?
   Why: Ecto runs none of them unless you write them.
6. Is MongoDB app-private, and is the data relational in practice? Why: it decides a Postgres migration or a KEEP.
7. Which exact error and validation envelopes do clients parse? Why: Nest and Fastify defaults are contracts mobile apps code against.
8. Which auth artifacts must survive cutover (JWT keys and claims, cookie names, hash formats)? Why: it sets session exchange,
   token acceptance windows and rehash-on-login.
9. Which schedules run once per process today, and does anything rely on the duplicates? Why: Oban cron runs once per cluster.
10. Does the app run serverless, and does the target platform allow node-to-node networking? Why: serverless shaped caching
    and timeouts; clustering decides PubSub and Presence versus Redis.
11. Which npm packages have no Hex equivalent? Why: each becomes a sidecar, a Port or a rewrite, and each KEEP needs a reason.
12. Which JSON details are load-bearing (camelCase, `undefined` vs `null`, millisecond timestamps, 64-bit ids as strings)?
    Why: byte-level drift breaks typed clients silently.
13. What performance bar and harness apply? Why: agents meet the bar you set, so fix the target before porting.

## Libraries (versions checked by the plugin author on hex.pm, 2026-10-09; re-check before pinning)

| Need | Package | Version | Notes |
|---|---|---|---|
| Web framework | phoenix | 1.8.15 | Scopes, phx.gen.auth with magic links |
| Server UI | phoenix_live_view | 1.2.12 | Replaces Next/Remix pages when the UI moves |
| HTTP server | bandit | 1.12.5 | Phoenix 1.8 default |
| Data | ecto / ecto_sql / postgrex | 3.14.2 / 3.14.0 / 0.22.4 | `Repo.transact/2` since 3.13 |
| SQLite (if the Node app used it) | ecto_sqlite3 | 0.25.0 | Pair with Oban's Lite engine |
| Jobs and cron | oban / oban_web | 2.24.1 / 2.13.1 | 2.24 moved cron, pruner and lifeline to top-level config |
| Broker consumers | broadway | 1.3.0 | Kafka, RabbitMQ, SQS producers |
| Fan-out | phoenix_pubsub | 2.4.1 | PG adapter over distributed Erlang |
| Clustering | dns_cluster / libcluster | 0.3.1 / 3.5.0 | Only with more than one node |
| PubSub without clustering | phoenix_pubsub_redis | 3.1.1 | Cloud Run-style platforms only |
| Redis (KEEP only) | redix | 1.9.2 | Shared keys or streams |
| HTTP client | req / finch | 0.7.5 / 0.24.0 | 0.8.0-rc adds SSE decoding |
| Rate limiting | hammer | 7.5.0 | ETS/Atomic backends; pick sliding window explicitly |
| Cache | cachex | 4.1.1 | `fetch/4` collapses concurrent misses per key |
| API contract | open_api_spex | 3.22.4 | Import the legacy spec as the golden contract |
| Reuse Fastify JSON Schemas | ex_json_schema | 0.11.5 | Validate request bodies against existing schema files |
| Test doubles | mox | 1.3.2 | Replaces DI-container swaps |
| Money | decimal | 3.1.1 | Never `:float` |
| Auth tokens | joken / joken_jwks / guardian | 2.7.0 / 1.8.0 / 2.5.0 | Validate existing JWTs |
| OAuth login | assent / ueberauth | 0.3.1 / 0.10.8 | Ueberauth releases slowly |
| Password hashes | bcrypt_elixir / argon2_elixir | 3.3.2 / 4.1.3 | Verify legacy hashes, rehash on login |
| MongoDB (KEEP only) | mongodb_driver | 1.6.4 | mongodb_ecto 2.1.1 exists but has low adoption |
| Audit trail | carbonite | 0.17.0 | Trigger-based, replaces audit hooks |
| Email | swoosh | 1.29.0 | Deliver from Oban jobs |
| Images | image | 0.72.0 | libvips via vix 0.42.0 |
| External processes | muontrap | 2.0.1 | Child dies with its owner |
| Node interop | nodejs | 3.1.4 | Pin at least 3.1.4 (CVE-2026-33872) |
| Strangler proxy | reverse_proxy_plug | 3.0.4 | HTTP only; WebSockets need reverse_proxy_plug_websocket 0.2.0 |
| Structured logs | logger_json | 7.0.4 | Keep field names the log pipeline parses |
| Circuit breaker | fuse | 2.5.0 | Dormant but mature; only with evidence |
