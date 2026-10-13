# App shapes: classify before choosing building blocks

Decide what the application *is* before mapping its mechanisms. The shape chooses the Elixir building blocks; a stack pack, or
`stacks/generic.md` when none matches, then maps mechanisms inside that shape. Iron Law 5 says "framework by default, where it applies".
This file says where it applies. A CLI, a TCP daemon or a data pipeline can be idiomatic Elixir without Phoenix, Ecto or Oban.
Package versions below were checked by the plugin author on hex.pm on 2026-10-09; re-check before pinning.

## Classify

Classify each deploy unit separately, then the whole app. Most real apps are one primary shape plus secondary ones (shape 13).
Four reads decide most cases:

- **What starts work:** an HTTP request, a broker message, a clock, a file arriving, a hardware event, a person at a terminal.
- **What it listens on:** an HTTP port, another TCP or UDP port, a broker subscription, nothing.
- **Who consumes the output:** browsers, an own SPA, mobile apps, partners, devices, operators, other services, files.
- **How it ships:** k8s `Deployment` with or without a `Service`, `CronJob`, `DaemonSet`, systemd unit or timer, a downloaded binary, a device image.

Record the shape and its evidence like any other decision. An unclear shape is `UNDECIDED` and blocks the architecture of that unit only.

## 1. Server-rendered web app

- **Recognize:** template trees (`*.jinja`, `*.twig`, `*.blade.php`, `*.cshtml`, `*.jsp`, `*.erb`, `*.ep`, `*.cfm`, Thymeleaf), handlers that return HTML,
  CSRF tokens in forms, session cookies, HTMX, Alpine or Turbo sprinkles instead of a separate frontend build, one HTTP deploy unit.
- **Elixir target:** Phoenix 1.8 controllers and HEEx function components for mostly static pages; LiveView 1.2 for interactive or live screens
  (`ui-strategy.md` decides keep, coexist or LiveView); Ecto contexts; `mix phx.gen.auth` sessions; Oban for mail and side effects;
  `reverse_proxy_plug` for page-by-page strangling.
- **Guarantees that matter most:** URL stability (indexed pages, bookmarks, redirects, trailing slash, case); session continuity at cutover; CSRF;
  authorization on every action and every LiveView event; the disconnected render is the crawler's HTML, so required content and metadata load
  there synchronously or from a cache (`assign_async` fills only the connected socket), without repeating that work on connect.
- **Not the obvious choice when:** content is mostly static and rarely edited: controllers and HEEx (or NimblePublisher) behind a CDN, no LiveView.
  Users on high-latency links with interaction-heavy screens: controllers plus small JS, LiveView only where push matters. Editors depend on an
  existing CMS admin: KEEP the admin and let Phoenix serve reads.
- **Ask:** Which URLs are indexed or linked from outside? Which screens need server push? Where are the users, and what is their p95 RTT?
  Who edits content, and in which tool?

## 2. SPA + JSON or GraphQL API

- **Recognize:** a frontend directory with its own `package.json` (React, Vue, Angular, Svelte); `fetch`, axios or Apollo calls; routes under `/api`;
  CORS config; bearer tokens in localStorage; an OpenAPI or GraphQL schema file; two deploy pipelines (CDN plus API).
- **Elixir target:** keep the SPA. Phoenix controllers with explicit `*JSON` modules and open_api_spex 3.22 golden tests, or Absinthe 1.12 with
  dataloader 2.0 for GraphQL (absinthe_phoenix 2.0 for subscriptions); Channels for push. LiveView or Inertia only with an approved UI redesign.
- **Guarantees that matter most:** the byte-level contract (key casing, null versus missing, number versus string, date format, pagination envelope,
  error body, status codes); token acceptance through cutover; exact CORS origins; the GraphQL SDL including nullability and deprecations.
- **Not the obvious choice when:** the API serves only your own SPA and the team wants to stop maintaining a frontend: LiveView or Inertia, decided in
  `ui-strategy.md`. GraphQL exists only as a one-client BFF: REST or LiveView may be simpler. Never rewrite the frontend inside the backend port.
- **Ask:** Who calls the API besides the SPA (mobile apps, scripts, partners)? Is there a spec to import as the golden contract? Is offline use required?

## 3. Public or partner API

- **Recognize:** versioned paths (`/v1/`), API keys or OAuth client credentials, rate-limit headers, outbound webhooks with signing secrets, SDKs in
  other repositories, developer docs, `Idempotency-Key` handling, usage metering.
- **Elixir target:** Bandit 1.12 with `Plug.Router` for a handful of endpoints; the Phoenix router and controllers once pipelines, versions and docs
  grow (Phoenix without HTML is cheap). open_api_spex for the contract; Hammer 7.5 for limits; outbound webhooks as Oban jobs (signing, backoff,
  `unique` per event); an idempotency-key table with a unique constraint.
- **Guarantees that matter most:** the contract frozen per version with a written deprecation policy; 429 semantics (`Retry-After`, limit headers);
  idempotent writes; at-least-once webhook delivery with the same signature scheme and retry schedule; key format and hashing at rest; stable cursors.
- **Not the obvious choice when:** an API gateway (Kong, Apigee, AWS API Gateway) already owns auth, quotas and keys: KEEP it and serve behind it.
  Limits must be exact across nodes that cannot cluster: `hammer_backend_redis` or the gateway.
- **Ask:** Which versions are live, and who uses each (access logs)? What does a partner see on 429 and 5xx? Which webhook retry schedule do
  partners rely on? How are keys stored?

## 4. Realtime: chat, collaboration, presence

- **Recognize:** a WebSocket or SSE server (Socket.io, SignalR, Action Cable, Django Channels, ws, Pusher or Ably SDKs), a Redis pub/sub backplane,
  sticky sessions, presence heartbeats, CRDT or OT libraries (Yjs, Automerge, ShareDB), socket SDKs in mobile apps.
- **Elixir target:** Phoenix Channels for custom clients and LiveView for server-rendered UI; Phoenix.PubSub 2.4 over a cluster (dns_cluster 0.3 or
  libcluster 3.5); Phoenix.Presence; history in Postgres with replay on join from the last-seen id; Oban for push notifications to offline users.
  For CRDT editors, keep the CRDT on the clients and let Channels relay and persist updates.
- **Guarantees that matter most:** PubSub is at-most-once, so define how a reconnecting client recovers the gap; ordering scope (per room, per user);
  authorization on join and on every event; broadcast after commit; backpressure and size limits for slow clients; Presence converges after a netsplit.
- **Not the obvious choice when:** clients are pinned to a legacy protocol and cannot update: a SHIM gateway, migration-only with a removal
  milestone or a permanent supported adapter (`ui-strategy.md`). The platform cannot cluster
  (Cloud Run): phoenix_pubsub_redis 3.1. One-way fan-out to huge anonymous audiences: SSE behind a CDN may beat sockets, so measure.
- **Ask:** Which clients and protocols exist, and can each be updated? What does a client do after reconnecting? Is presence ephemeral, or billed
  and audited? What is the ordering scope?

## 5. Background worker or queue consumer

- **Recognize:** deploy units with no HTTP port (a k8s Deployment without a Service, a Procfile `worker:` line), broker clients (Kafka, AMQP, SQS, NATS,
  Pub/Sub), consumer group ids, ack and nack calls, dead-letter config, offset or checkpoint storage.
- **Elixir target:** Broadway 1.3 with broadway_kafka 0.7, broadway_rabbitmq 0.8 or broadway_sqs 1.0 (batchers, per-partition ordering, acks,
  graceful drain); Oban when the queue is private to this app (transactional enqueue). A release without Phoenix; Bandit and Plug only for health and metrics.
- **Guarantees that matter most:** at-least-once delivery with an idempotency key; per-partition or per-key ordering; ack only after the side effect
  commits; poison-message and DLQ handling; concurrency caps; the starting offset at cutover (committed offsets or a shadow consumer); drain on deploy.
- **Not the obvious choice when:** the broker only connects two components of this app: DELETE it and use Oban. High volume where most messages are
  filtered out: do not push each one through the job table (KB: Oban write amplification on a 2.59M/day webhook path). Kafka Streams stateful joins:
  Broadway has no equivalent, so KEEP them or redesign.
- **Ask:** Who else produces to or consumes from each topic? What is the ordering scope? What happens to a poison message today? From which exact
  offset does the new consumer start?

## 6. Data pipeline, ETL, batch

- **Recognize:** Airflow DAGs, Luigi, Spark or PySpark, dbt, SSIS packages, Spring Batch, pandas scripts, staging tables, `COPY` or bulk loads,
  S3 or SFTP drops, watermark or checkpoint tables.
- **Elixir target:** `Stream`, `Repo.stream/2` inside a transaction and `Task.async_stream/3` with `max_concurrency` and `timeout`; one Oban job per
  partition or file for resumability (`unique` on the partition key against duplicate inserts, `lifeline:` to rescue a run a crash left
  `executing`); Broadway for external sources; Explorer 0.13 for dataframe transforms;
  Postgres `COPY` through `Ecto.Adapters.SQL.stream/4`. Flow 1.2 has had no release since 2023: evaluate it before using it for in-memory aggregation.
- **Guarantees that matter most:** idempotent re-runs (upserts on natural keys, watermarks); exactly-once load per partition; resume after a crash
  mid-batch; the output schema as a consumer contract; a late-data policy; step dependencies.
- **Not the obvious choice when:** the logic is SQL in a warehouse (dbt, Snowflake, BigQuery): KEEP it, Elixir at most triggers it. Spark-scale data:
  KEEP Spark. A sequential loop over items: plain recursion and `Task.async_stream`, not GenStage (KB decision: OTP is not for sequential LLM batch loops).
  A data team schedules everything in Airflow: KEEP Airflow as the scheduler.
- **Ask:** What is the unit of re-run (day, file, partition)? What does a half-finished run leave behind today? Who consumes the outputs, and in
  what format? What volume and time window per run?

## 7. Scheduled jobs only

- **Recognize:** crontab, k8s CronJob, systemd timers, Windows Task Scheduler, Jenkins schedules, Lambda schedules; scripts that start, work and
  exit; lock files against overlap; no listening socket.
- **Elixir target:** with a database, a release running Oban cron (2.24 top-level `cron: [crontab: [...]]`, module `Oban.Cron`, formerly
  `Oban.Plugins.Cron`), so runs are durable, retried, unique and visible in Oban Web; no Phoenix unless someone needs a UI. Without a database, or
  for infra semantics, keep the OS scheduler and call `bin/app eval "MyApp.Jobs.nightly()"` or a Burrito binary.
- **Guarantees that matter most:** one run per tick across nodes; overlap policy; timezone and DST (per-entry `timezone:` since Oban 2.24);
  missed-run behavior (crontab does not backfill, and Oban cron does not by default [U]); failure alerting, which is often only cron `MAILTO`.
- **Not the obvious choice when:** the job must run while the app is down (backups, vacuum, certificate rotation): KEEP the infra scheduler.
  A small self-contained script already works: leave it out of the rewrite scope.
- **Ask:** What alerts on failure today? Can two runs overlap, and what breaks if they do? What should happen after missed ticks? Which timezone?

## 8. CLI, desktop, dev tool

- **Recognize:** argument parsers (argparse, click, clap, cobra, picocli, System.CommandLine, Thor, yargs), `bin/` entry points, man pages, shell
  completions, stdin and stdout piping, exit codes, config under `~/.config`; desktop: Electron, Tauri, Qt, WinForms, WPF, Swing.
- **Elixir target:** no Phoenix, Ecto or Oban by default. Burrito 1.6 ships one binary with ERTS bundled (KB verdict: use). An escript suits dev tools
  where Erlang is installed, but priv files and NIFs are awkward in it. Bakeware 0.2 has had no release since 2022. Parse arguments with `OptionParser`
  or Optimus 0.6; format terminal output with Owl 0.13. Desktop: a local Phoenix + LiveView opened in the browser, or ex_tauri 0.2 (Burrito inside a
  Tauri shell) for a native window; `desktop` 1.5 (wxWidgets) has had no release since 2024-03.
- **Guarantees that matter most:** flags, exit codes and stdout/stderr formats that scripts parse; stdin streaming; config file location and format;
  startup latency; offline operation; Ctrl-C handling; OS and CPU targets.
- **Not the obvious choice when:** the startup budget is tens of milliseconds (prompt hooks, per-keystroke git hooks): BEAM boot may miss it, so
  measure `time ./app --version` on the target first. A release boots its whole supervision tree, so start the Endpoint only for a `serve`
  subcommand (KB gotcha). Heavy native UI: keep it native, with Elixir only as a sidecar for server logic.
- **Ask:** Who invokes it (a person, a script, CI)? What parses its output? What is the startup budget? Which OS and architectures? Must it work offline?

## 9. Long-running daemon or network service

- **Recognize:** `listen(`, `bind(`, `accept(`, `SOCK_DGRAM`, Netty, asyncio or tokio servers, custom framing (length prefixes, delimiters),
  protocol RFCs in the docs, non-HTTP ports in deploy files, systemd `Type=notify`. Examples: SMTP, LDAP, RADIUS, SIP, game servers, MQTT brokers, proxies.
- **Elixir target:** an OTP application in a release. ThousandIsland 1.5 (pure Elixir, the socket layer under Bandit) or ranch 2.3 for TCP acceptor
  pools; `:gen_tcp`, `:gen_udp` or `:socket` for simple and UDP cases; one process per connection; `:gen_statem` for protocol state; binary pattern
  matching for framing (`<<len::32, body::binary-size(len), rest::binary>>`) or `{:packet, 4}` and `{:packet, :line}` socket options.
  Phoenix only for an admin or HTTP surface.
- **Guarantees that matter most:** byte-for-byte wire compatibility (framing, endianness, keepalives, timeouts); connection limits and backpressure;
  TLS versions and ciphers; draining long-lived connections on deploy; per-connection crash isolation; p99 latency; UDP loss tolerance.
- **Not the obvious choice when:** packet rates need kernel bypass (DPDK class): KEEP native code, perhaps behind a NIF. A mature open-source
  server already speaks the protocol (Postfix, Mosquitto, HAProxy): KEEP it and integrate. The "daemon" is really a poller: use shape 5 or 7.
- **Ask:** Is there a protocol spec or conformance suite? What are peak concurrent connections and message rate? How do clients behave when the
  server restarts? Do operators expect hot code upgrades?

## 10. IoT and embedded

- **Recognize:** Yocto, Buildroot, PlatformIO or Arduino builds; GPIO, I2C, SPI or UART libraries (libgpiod, pyserial, RPi.GPIO); MQTT clients;
  OTA update scripts; device certificates and provisioning; systemd on a Raspberry Pi. Separate device code from the fleet backend.
- **Elixir target:** on Linux-capable boards, Nerves 1.15 with nerves_runtime 0.13, vintage_net 0.13 for networking, circuits_gpio 2.3,
  circuits_i2c 2.1 and circuits_uart 1.6, and OTA through NervesHub (nerves_hub_link 2.12). Microcontrollers without Linux keep C or Rust firmware
  (AtomVM targets them but is not evaluated here [U]). For the fleet: MQTT through tortoise311 0.12 or emqtt 1.16 to a KEPT broker, Broadway
  ingestion, LiveView dashboards, Oban for device commands.
- **Guarantees that matter most:** atomic OTA with rollback (A/B firmware slots); offline operation and store-and-forward; writes that survive power
  loss; timing that the BEAM's soft real-time cannot meet; device identity and certificates; the protocol of units that cannot be reflashed.
- **Not the obvious choice when:** control loops need hard real-time (microseconds) or the target is a microcontroller: stay native. Devices in the
  field cannot be updated: rewrite the backend only and freeze the device protocol as a contract.
- **Ask:** Which hardware (CPU class, RAM, storage)? Which devices can be reflashed, and how? Any hard timing requirements? How are updates
  delivered and rolled back today?

## 11. ML or inference service

- **Recognize:** model files (`.onnx`, `.pt`, `.safetensors`, `.pkl`, `.h5`); torch, tensorflow, transformers, scikit-learn or xgboost imports;
  FastAPI, TorchServe, Triton or BentoML servers; GPU node pools; batching config; notebooks; feature stores.
- **Elixir target, in order of evidence:** (a) Nx 1.0, EXLA 1.0 and Bumblebee 0.8 with `Nx.Serving` batching when Bumblebee supports the model
  architecture; (b) Ortex 0.1.10 for ONNX exports (no release since 2024-11, so evaluate it); (c) Pythonx 0.4 for library gaps, with Python calls kept
  in one process because of the GIL; (d) KEEP the Python service behind a Port, HTTP or gRPC. Option (d) is the default when training code, custom
  ops or GPU serving stacks (Triton, vLLM) exist. Elixir owns request handling, queuing, rate limits, streaming responses and FLAME 0.5 burst capacity.
- **Guarantees that matter most:** numerical parity within a tolerance on a golden eval set, not exact equality; preprocessing and tokenizer
  parity, where most bugs live; p95 latency including batching delay; GPU memory and concurrency limits; model version pinning and rollout.
- **Not the obvious choice when:** the service wraps a hosted model API: Req, Oban and streaming are enough, no Nx. Training pipelines: KEEP Python.
- **Ask:** Which models, formats and ops? Which tolerance and eval set prove parity? What is the latency budget and batch size? Who retrains, and
  how often do models change?

## 12. Multi-tenant SaaS

- **Recognize:** `tenant_id`, `account_id` or `org_id` on most tables; subdomain or path routing per tenant; schema-per-tenant (`search_path`,
  django-tenants, apartment); database-per-tenant connection switching; tenant middleware; per-tenant plans, flags and config; data residency rules.
- **Elixir target:** row-level by default: a Phoenix 1.8 Scope carrying the organization, `org_id` foreign keys, composite keys `(org_id, id)` so a
  row cannot reference another tenant's row, and `Repo.prepare_query/3` that raises when the tenant filter is missing (Ecto guide "Multi tenancy
  with foreign keys"). Schema-per-tenant: the query `prefix:` option, `put_query_prefix/2` and `mix ecto.migrate --prefix`; triplex 1.3 has had no
  release since 2019. Database-per-tenant: `Repo.put_dynamic_repo/1`. The tenant id goes into every Oban job's args.
- **Guarantees that matter most:** isolation on every channel (queries, caches, PubSub topics, file paths, search indexes, logs); tenant-scoped
  unique indexes; noisy-neighbor fairness (per-tenant limits and queues); per-tenant export, deletion and restore; data residency; migration time across N schemas.
- **Not the obvious choice when:** tenants number in the tens of thousands: schema-per-tenant migrations take hours, so prefer row-level. Regulation
  demands physical isolation: database-per-tenant. A process per tenant needs hot in-memory state as its runtime reason (Iron Law 13).
- **Ask:** What are the tenant count and size distribution? Which isolation model do contracts or regulators require? Do tenants need self-service
  export and deletion? Are cache keys and topics tenant-scoped today?

## 13. Monolith mixing several shapes

- **Recognize:** one repository with several deploy units (web, worker, scheduler, socket server, CLI) that share models and one database;
  a Procfile or compose file with four or more process types.
- **Elixir target:** one release whose supervision tree hosts several shapes (Endpoint, Oban queues, Broadway pipelines, a ThousandIsland listener),
  with contexts as boundaries checked by `mix xref`. Split node roles by config (Oban queues on some nodes only) only on measured contention
  (KB: colocated Oban did not starve the web tier). Classify each deploy unit with its own shape and migrate one shape slice at a time.
- **Guarantees that matter most:** resource isolation between shapes (schedulers are preemptive, but the Repo pool is shared, so use separate pools
  or queue limits); web latency under batch load; independent deploys where owners differ; the blast radius of one part's failure.
- **Not the obvious choice when:** parts have radically different resource profiles (GPU inference, heavy batch) or different owning teams:
  separate releases. A part works and is out of scope: KEEP it.
- **Ask:** Which deploy units share code, and which share only the database? Which shapes compete for DB connections? What must keep running
  while another part deploys?

## Shape → first vertical slice

| Shape | First slice | What it proves | Exit evidence |
|---|---|---|---|
| Server-rendered web | Login plus one page that reads, writes and triggers a background effect (record saved, then email via Oban), routed through the strangler proxy | Session handoff, routing coexistence, Ecto on the legacy schema, transactional enqueue | Parity tests pass on that route; revoking a session stops access on both sides |
| SPA + API | One read and one write endpoint the SPA calls, served at the same URL | Byte-level contract, token acceptance, CORS | Recorded production requests replayed against both systems with zero diffs |
| Public or partner API | One versioned endpoint with auth, rate limit and idempotency, plus one outbound webhook | Key format, 429 semantics, webhook signature and retry | A partner sandbox or the partner SDK accepts responses and verifies signatures |
| Realtime | One room: join with auth, send, broadcast after commit, reconnect replay, presence | Delivery and ordering across reconnects | Soak test with N clients and forced disconnects shows no gaps after replay |
| Worker or consumer | One topic or queue consumed in shadow mode (new consumer group, side effects into a shadow table) | Ordering, idempotency, offset handling | Output diff is zero over an agreed window; a deploy drains without loss |
| Data pipeline, ETL | One partition or day end to end, run twice, and once killed midway | Idempotency and resumability | Identical output after re-run; the resumed run completes without duplicates |
| Scheduled jobs | The job with the worst failure mode (money, email, deletion), with uniqueness and alerting | One run per tick; visible failure | Two nodes produce one run per tick; an induced failure raises the alert |
| CLI, desktop | One real command with its flags, exit codes and output, packaged for the hardest target OS | Packaging, startup time, output contract | Golden output diff is empty; startup time meets the budget on target hardware |
| Network service | Handshake, one request type and graceful drain | Framing, wire compatibility, connection scale | Captured traffic replays against both servers; N concurrent connections held |
| IoT, embedded | Fleet: ingest one device class through the existing broker and send one command back. Device: one Nerves image with OTA rollback | Device protocol contract, OTA atomicity | Field devices unchanged; an induced bad update rolls back |
| ML, inference | One model behind the existing endpoint, with batching | Numerical parity and latency | Eval-set tolerance met; p95 under load within budget |
| Multi-tenant SaaS | One tenant-scoped resource across HTTP, socket, job, cache and export paths | Isolation | Negative tests prove tenant A cannot read or write tenant B on every path |
| Mixed monolith | A web write that enqueues a job, which a worker consumes and pushes live to users | Several shapes in one release; DB pool contention | Web p95 under worker load stays within the ADR-000 goal |
