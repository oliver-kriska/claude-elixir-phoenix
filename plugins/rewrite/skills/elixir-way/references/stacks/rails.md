# Rails → Elixir

Rails 6.0–8.x: ActiveRecord on Postgres, MySQL or SQLite, Hotwire, and ActiveJob over Sidekiq, Resque or Solid Queue. Cookie facts were checked against
Rails `main` source, and Campfire pins 8.2.0.alpha. Read this alongside the verdict vocabulary and reason tags in the elixir-way SKILL.md.
`[U]` marks a framework detail that was not re-verified on 2026-10-09. Confirm it in the pinned gem source before you rely on it.

## Probe: where mechanisms hide

| Look at | What it reveals | Contract or purpose to capture |
|---|---|---|
| `app/models/**/*.rb` → `before_(validation\|save\|create\|update\|destroy)\|after_\w+\|around_\w+` | Persistence callbacks: derived columns, jobs, cache busts, broadcasts | Each side effect, its order, and whether it must commit atomically with the write. An Ecto write runs none of them |
| `app/{models,controllers}/concerns/**` → `extend ActiveSupport::Concern\|included do\|class_methods do` | Behavior injected into many classes, often callbacks and scopes | For each including class: the hooks, scopes and validations it gains |
| `default_scope\|scope :\|acts_as_paranoid\|include Discard\|acts_as_tenant` | Hidden query filters | Which reads filter implicitly (soft delete, tenancy, ordering). Every ported query must state these filters |
| `app/models/current.rb` → `CurrentAttributes\|Current\.\w+ =\|RequestStore\|Thread.current` | Per-request globals | The fields the Phoenix `Scope` needs, and which jobs and mailers read them implicitly |
| `config/application.rb`, `config/initializers/{session_store,cookies_serializer,new_framework_defaults*}.rb` → `load_defaults\|cookies_serializer\|key_generator_hash_digest_class\|use_authenticated_cookie_encryption` | The cookie crypto and serializer actually in force | Cipher, digest, salt, serializer (JSON, hybrid or Marshal), cookie name and expiry. The Rails version alone does not determine them |
| `cookies\.(signed\|encrypted)\|signed_id\|find_signed\|generates_token_for\|to_sgid\|MessageVerifier\|message_verifier\(` | Signed capabilities already issued | Purpose, expiry, and where each one is persisted (emails, rich text, bookmarks). This decides how long a SHIM lives |
| `broadcasts_to\|broadcasts_refreshes\|broadcast_\w+_to\|turbo_stream_from` | Realtime pushed from models after commit | Recipients per event, the payload partial, stream-name signing, and authorization beyond the signature |
| `app/channels/**`, `config/cable.yml` → `identified_by\|stream_from\|stream_for\|reject\|periodically` | Socket auth, subscriptions, adapter | Connect auth, per-subscription authorization, revocation and reconnect (Campfire added membership-aware room streams) |
| `has_(one\|many)_attached\|variant\(\|preview\(\|config/storage.yml\|active_storage_variant_records` | Storage layout and variant identity | Service names, key layout, checksums, the variation digest (a Ruby Marshal of the transformations), signed URL purpose and expiry |
| `has_rich_text\|action_text_rich_texts\|ActionText::\|sanitize\(` | Bodies stored in another table; the sanitizer allow-list | Allowed tags and attributes, embedded attachment sgids, edit round trips |
| `config/locales/**/*.yml`, `config.i18n.(fallbacks\|default_locale\|available_locales)`, keys ending `_html` | Lookup chain and HTML-safe keys | Fallback chain, pluralization rules (rails-i18n), lazy `t(".x")` keys, which keys skip escaping |
| `bin/rails middleware` output, `config.middleware.(use\|insert_before\|insert_after\|delete\|swap)` | The effective Rack order | Behavior-bearing middleware (Rack::Attack, host authorization, CORS, request id) versus runtime shims |
| `config/initializers/*.rb` → `inflect\|Rack::Attack\|filter_parameters\|on_load\|config.hosts\|time_zone\|to_prepare` | Global switches | Inflections change table and constant names. Also log redaction and the app time zone |
| `lib/**/*.rb`, `lib/*_ext/**` → `class (String\|Hash\|Array\|Time\|ActiveRecord::Base)\b\|prepend\|refine\|class_eval` | Monkeypatches | Behavior the app silently depends on (Campfire's `lib/rails_ext/` patches Action Text embeds and attachables) |
| `Gemfile.lock` + `config/initializers/{devise,kaminari,pagy,paper_trail,sidekiq}.rb` | Gem defaults that count as behavior | Devise `pepper`, `stretches` and lockable settings, page sizes, version metadata, Sidekiq middleware |
| `app/{jobs,workers}/**`, `config/{sidekiq,queue}.yml` → `retry_on\|discard_on\|sidekiq_options\|queue_as\|limits_concurrency` | Retry, ordering and concurrency semantics | For each job: attempts, backoff, uniqueness, idempotency, backlog. ActiveJob declares no retries, the Sidekiq adapter adds 25, Resque has none |
| `config/schedule.rb`, `config/recurring.yml`, `:scheduler:` in `config/sidekiq.yml` | Cron | Schedule time zone, overlap policy, which node runs each entry |
| `config/routes.rb` + `bin/rails routes` → `constraints\|mount\|direct\|resolve\|format:\|defaults:\|scope module:` | URL contract and order | First-match order and shadowing, `.json` suffixes, mounted engines' URLs |
| `app/controllers/**` → `before_action\|skip_before_action\|rescue_from\|protect_from_forgery\|rate_limit\|fresh_when\|stale\?` | Filter chain, early returns, conditional GET | The status, flash and session effects of early returns. ETag and Last-Modified contracts |
| `db/structure.sql`, `db/schema.rb` → `CREATE TRIGGER\|CHECK \|fts5\|USING gin`; models → `dependent:\|touch:\|counter_cache:` | What the DB enforces versus what Ruby enforces | Cascades and counters that exist only in Ruby. Triggers that are behavior |
| `enum \|inheritance_column\|polymorphic: true\|serialize \|store_accessor\|encrypts\|normalizes` | Persisted encodings | Integer enum values, STI class strings, YAML/JSON columns, AR-encrypted columns, input normalization |
| `ActiveSupport::Notifications.subscribe\|after_initialize\|Rails.application.reloader` | Hidden hooks | Instrumentation consumers and side effects wired at boot |
| `Procfile*`, `config/puma.rb`, `config/deploy.yml`, `bin/*`, container entrypoints | Process topology and infra flags | Why each process exists, and its ops settings (Campfire's Redis ran `--save '' --appendonly no`, so its "durable" jobs were not) |

## Mechanism map

| Legacy mechanism | Usual purpose (why) | Reason tags | Default verdict → Elixir way | Literal-translation trap | Cutover / compat note |
|---|---|---|---|---|---|
| `routes.rb` resources + `*_path` helpers | Map URLs to actions without hard-coded paths | contract | MAP → `Phoenix.Router` (`resources`, `live`, pipelines) + verified routes `~p` | A route-recognition module generated from `rails routes` (Campfire: a 2,235-line `generated/routes.ex`) | Route parity is a test table, not a runtime emulator. Send unported paths to Rails with `reverse_proxy_plug`. Keep `.json` URLs as explicit routes |
| Rack middleware stack | Cross-cutting request work | business (some platform) | MAP → Endpoint plugs + router pipelines. DELETE runtime shims (Rack::Lock, Rack::Runtime) | Re-creating the middleware order one-to-one | Port only the middleware that changes responses: CORS, host checks, request id, Rack::Attack |
| `before_action`, `around_action`, `rescue_from` | Reusable pre-action logic and error mapping | business | MAP → function plugs (`plug :load_room when action in [...]`) and `action_fallback`. `Ecto.NoResultsError` already maps to 404 like `RecordNotFound` (phoenix_ecto) | Base-controller inheritance through `use` macros that inject hidden plugs | Filter order and the status/flash/session effects of early returns are contracts. Test the unauthorized and missing-record paths |
| Strong params `permit` | Mass-assignment safety | business | MAP → a `cast/3` allow-list in each operation's changeset | `cast(params, __schema__(:fields))` | Ecto `cast` turns `""` and whitespace into `nil` by default (`empty_values`), where Rails stored `""`. Pass `empty_values: []` when NOT NULL columns or queries depend on `""` |
| `respond_to`, format negotiation | One action, several representations | contract | MAP → `PostHTML`/`PostJSON` modules + the `accepts` plug | Branching on format inside every action | `/posts/1.json` needs explicit routes or a format plug. The Turbo Stream MIME type (`text/vnd.turbo-stream.html`) stays a contract while Turbo stays |
| ERB/Haml partials, helpers, ViewComponent | Compose HTML and reuse fragments | business | MAP → HEEx function components (`attr`/`slot`), `core_components.ex`, `<Layouts.app>` | `EEx.function_from_file` with manual escaping (Campfire built its CSRF input by unescaped interpolation) | Audit `html_safe`, `raw` and `_html` i18n keys against Iron Law 12 |
| Fragment and Russian-doll caching, `touch: true` chains | Template rendering is slow per request | platform | DELETE → compiled HEEx, LiveView diffs and streams. Cache data, not HTML | Porting the cache keys: Campfire's shared fragments leaked the CSRF token and request Host across users | If a measured cache stays, key it on every input (user, host, locale, permissions), never cache fallbacks, and evict with a bounded LRU |
| Turbo Drive/Frames/Streams + Stimulus | SPA-like UX from server HTML | business | REPLACE → LiveView (`<.link navigate>`, LiveComponents, `stream/4`, `JS` commands, colocated hooks) when a frontend change is accepted. Otherwise KEEP the Turbo JS | Serving LiveView to Turbo clients, or porting every Stimulus controller as a hook | Treat the frontend migration as its own milestone. Old tabs and Hotwire Native shells still speak Turbo |
| Model broadcasts (`broadcasts_to`, `after_create_commit -> broadcast_*`) | Push DOM updates after commit | business | MAP → the context function broadcasts with `Phoenix.PubSub` after `Repo.transact/2` returns `{:ok, _}` | Broadcasting inside the transaction or from the schema module | Authorize recipients per subscription, not by a signed stream name alone. A shared DB fires no Rails broadcasts for Ecto writes |
| Action Cable channels + server | Authenticated persistent sockets | platform (contract while old clients exist) | REPLACE → `Phoenix.Channel` or LiveView over `Phoenix.PubSub`, with `Phoenix.Presence` for presence. SHIM → a Cable protocol adapter on `websock_adapter` | A hand-rolled Cable server as the target architecture | Cable (`actioncable-v1-json`) and Phoenix Channels are different protocols. LiveView cannot take over `/cable` |
| Cable Redis adapter, Solid Cable, AnyCable | Fan out between Puma processes; hold sockets outside Ruby | platform | DELETE → `Phoenix.PubSub` (`:pg`, cluster-native), with sockets in the same release | One Redis subscription per socket, with a blocking 5 s `receive` in `init` (Campfire before the fix) | Running Rails and Elixir together needs a deliberate bridge (see Keep or shim) |
| ActiveRecord models | Data, behavior and persistence in one class | business | MAP → Ecto schema + changesets + a context module | `Post.find/save` wrappers. Raw SQL returning string-keyed maps (Campfire had no Ecto at all) | Map onto the existing tables. A context is a plain module, never a GenServer around a DB handle |
| Table conventions: `created_at`, `timestamp(6)`, bigint ids | Rails naming and precision defaults | contract | MAP → `@timestamps_opts [type: :utc_datetime_usec, inserted_at: :created_at]`, `field ..., source: :legacy_name`, `@schema_prefix` for a non-default schema | Generators that add an `inserted_at` column | Rails writes UTC into `timestamp without time zone`. Map `config.time_zone` names ("Eastern Time (US & Canada)") to IANA with `tz`. On SQLite, Rails stores `YYYY-MM-DD HH:MM:SS.ffffff` text that no ecto_sqlite3 `datetime_type` reproduces: use a custom Ecto type (`../data-compat.md`) |
| `schema_migrations` + `ar_internal_metadata` | Versioned DDL | contract | KEEP both tables. MAP new DDL to Ecto with `migration_source: "ecto_schema_migrations"`, set before the first `ecto.migrate` | Rewriting the historical migrations in Ecto. Letting Ecto use Rails' `schema_migrations` (different shape) | One DDL owner at a time. Take the baseline from `structure.sql` |
| Callbacks (`before_save`, `after_commit`) | Hook side effects into persistence | business (often historical) | MAP → an explicit pipeline: changeset → `Ecto.Multi`/`Repo.transact` → `Oban.insert` in the same transaction → PubSub after commit. Use `prepare_changes/2` only for derived writes inside the transaction | A callback-registry GenServer, or `prepare_changes` for everything | Classify each callback as derived data, side effect or cache bust, and give it a named home |
| `dependent: :destroy`, `touch: true`, `counter_cache` | Ruby-level cascades and counters | business | MAP → DB `ON DELETE` after cutover, or explicit `Ecto.Multi` deletes. Counters via `prepare_changes` + `update_all(inc:)` | Loading children to delete them one at a time | Often the DB has no FK action, so an Ecto delete either orphans rows or fails. Both writers must maintain counters during coexistence |
| Concerns | Share behavior across models | historical | MAP → plain modules of query and changeset functions | `use Taggable` injecting fields, callbacks and functions | — |
| `default_scope`, paranoia/discard, acts_as_tenant | Implicit filtering | business | MAP → composable query functions. Enforce tenancy and soft delete with a `Repo.prepare_query/3` that raises when the filter is missing | Silently adding hidden filters | Phoenix 1.8 `Scope` is the caller context, not a Rails `scope` |
| `validates`, `uniqueness: true` | Input integrity | business | MAP → changeset validations. Uniqueness via a DB index + `unique_constraint/3` | Matching error strings (Campfire signup: `inspect(error)` contains `"UNIQUE constraint failed"`) | Rails checks uniqueness in the app. Dedupe and add the index before you rely on the constraint |
| `enum` (integer), `normalizes` | Named states, canonical input | contract | MAP → `Ecto.Enum, values: [draft: 0, published: 1]`, with normalization in the changeset | Storing atom names as strings | Keep the integer values. Some apps use string-backed enums instead |
| STI `type` column | A class hierarchy in one table | contract | MAP → one schema with `Ecto.Enum` over the stored class strings (`"Rooms::Direct"`), or several schemas that filter on `type` | Emulating module inheritance. `String.to_atom` on `type` (Iron Law 10) | Keep the strings. Renaming them breaks rollback |
| Polymorphic `*_type`/`*_id` | One FK pointing at many tables | contract | MAP → `field :commentable_type, Ecto.Enum, values: [post: "Post"]` plus a plain `*_id`. Ecto has no polymorphic `belongs_to` | A runtime `Module.concat` resolver | Normalize into per-parent FKs or join tables after cutover |
| `serialize`/`store` (YAML/JSON), `encrypts` | Typed or secret columns | contract | MAP → `:map`/`embeds_*`. REPLACE AR encryption with `cloak_ecto` through a backfill | A permanent port of the AR-encryption cipher | Read YAML history (paper_trail `object`) with `yaml_elixir`, read-only. Re-encrypt in a one-off job |
| Action Text `has_rich_text` | Rich bodies with embedded attachments | business | MAP → an explicit schema over `action_text_rich_texts`. Sanitize with `html_sanitize_ex` or a LazyHTML allow-list | A native HTML parser pinned to Nokogiri's version (Campfire `native/html.c`, which later failed OOM tests) | The body is not on the model's table. Embedded sgids are signed capabilities (see Keep or shim) |
| `CurrentAttributes` | Implicit request context | platform | MAP → `current_scope` in conn and socket assigns, passed as the first context argument | The process dictionary as a thread-local (it breaks in Tasks, LiveView and Oban) | Jobs receive IDs and context explicitly (Iron Law 25 for the locale) |
| ActiveJob over Sidekiq, Resque or Solid Queue | Work beyond the request, on a separate fleet | reliability, platform | MAP → an Oban worker (Postgres; `Oban.Engines.Lite` on SQLite; Dolphin on MySQL 8.4+), enqueued in the same `Repo.transact`/`Ecto.Multi` with string-keyed ID args | A Resque-compatible worker on Redix with `gid://` args (Campfire `jobs.ex`/`worker.ex`: `LPOP` loses a claimed job on crash). An in-memory GenServer queue | Drain the legacy queues one job class at a time. During coexistence, Rails can insert into `oban_jobs` directly |
| `retry_on`, `discard_on`, Sidekiq `retry: 25` | Recover from transient failure | business | MAP → `max_attempts`, `backoff/1`, `{:cancel, reason}` and `unique:` per worker | Copying 25 retries everywhere, or having none (Campfire's worker had no retries) | Oban defaults to 20 attempts. Decide per job from its idempotency (Iron Law 7) |
| `after_commit` enqueue, `deliver_later` | The queue lived outside the DB transaction | reliability, platform | DELETE → `Oban.insert` inside the transaction is the outbox | Commit, then enqueue to Redis (Campfire: with Redis absent, the message saved and then the request returned 500) | On SQLite, keep jobs in the same database when atomic enqueue matters |
| whenever, sidekiq-cron, `config/recurring.yml` | A scheduler outside the app | reliability, platform | MAP → Oban cron (top-level `cron:` key, `Oban.Cron`, Oban 2.24+) | A `Process.send_after` GenServer. A crontab calling `bin/app rpc` | Switch off the legacy entry in the same deploy. The Lite engine uses isolated peers, so ensure only one instance is active |
| Rake tasks | Ops and one-off scripts | business | MAP → release functions run with `bin/app eval`. Long backfills become Oban jobs | Mix tasks, which do not exist in a release | Iron Law 23 for dev-only Mix tasks |
| `Rails.cache` (Redis, memcached, Solid Cache) | Share computed data between processes that share no memory | platform | REPLACE → ETS or `Cachex`, with `Phoenix.PubSub` for cross-node invalidation | Re-implementing the ActiveSupport cache-entry byte format (Campfire `rails/cache.ex`). One GenServer as the cache. A public ETS table wiped at 4,096 entries | Never read Rails' cache entries. While Rails also writes, invalidate on its writes or bypass the cache |
| Kredis, ad-hoc Redis structures | Counters, sets and flags shared across processes | reliability, platform (sometimes business) | REPLACE → a DB table if durable, ETS if node-local and ephemeral, Presence if per connection | Redix calls scattered through the domain (Iron Law 20) | Classify every Redis call site: cache, pubsub, rate limit, jobs, lock or data |
| Rack::Attack, `rate_limit` (7.2+) | Abuse protection in a shared store | platform | MAP → `Hammer` (ETS backend) or `PlugAttack`. Key on the real client IP behind proxies | A GenServer limiter that fails open on Redis errors and sweeps all keys on every hit (Campfire, before and after its fix) | ETS limits are per node. Multi-node needs a shared backend or limits scaled by node count |
| CookieStore `_app_session` | Per-user state across share-nothing requests | platform | REPLACE → `phx.gen.auth` session tokens. SHIM → a one-way legacy cookie reader | A Ruby Marshal codec, with Phoenix writing Rails session cookies forever (Campfire `marshal.ex`, `sessions.ex`) | Prefer a handoff endpoint. Otherwise read the cookie once and mint a Phoenix session. Switch `cookies_serializer` to `:hybrid` weeks before cutover |
| Signed ids, sgid, `generates_token_for`, MessageVerifier | Capabilities with a purpose and expiry | contract | SHIM → a narrow per-purpose verifier (`Plug.Crypto.KeyGenerator` + `:crypto`) for values already issued. New capabilities use `Phoenix.Token` | One general signature parser that accepts any purpose | Test valid, expired, wrong-purpose, tampered and rotated-key vectors minted by the pinned Rails |
| Devise, `has_secure_password` | Login, reset, confirm, remember-me | business | REPLACE → `mix phx.gen.auth` over the existing users table. Verify `$2a$` hashes with `Bcrypt.verify_pass` (append the Devise pepper), then rehash on login | Porting Devise modules one by one | Outstanding reset and confirm tokens: honor them or expire them deliberately |
| Pundit, CanCanCan, Action Policy | Authorization and `policy_scope` | business | MAP → context functions that take `%Scope{}`. `Bodyguard` is the closest Pundit analog; `LetMe` for a declarative DSL | A reflective `Ability` class. Authorizing only in `mount` (Iron Law 11) | Build a permission-parity matrix from the legacy policies |
| ActiveStorage | Attach files, signed delivery, variants | business + contract | KEEP the blob and attachment tables, the bucket and the keys (read-only schemas). MAP uploads to LiveView `allow_upload` + `ExAws.S3`, and variants to `image` on `vix` in Oban | Re-implementing ActiveStorage's polymorphic tables and URL scheme wholesale | Old signed blob and variant URLs live inside content. Keep a verifier, or redirect |
| ActionMailer + `deliver_later`; ActionMailbox | Email off the request path; replies as input | business | MAP → `Swoosh` + an Oban worker that builds the email from IDs. Inbound: webhook controller → Oban → the `mail` parser | A provider SDK next to Swoosh. A port of the ActionMailbox framework | Dedupe by idempotency key while both mailers run |
| Web Push (`web-push` gem) | Reach users outside the page | business | MAP → `web_push_elixir` in an Oban worker (a candidate: verify crypto vectors and real browser receipt) | Copying status-code branches without their goal (Campfire dropped dead subscriptions on 410 but not on 404) | Keep the subscriptions and VAPID keys, or users must re-enroll |
| I18n YAML | Translate the UI | business | MAP → `Gettext` `.po` files + `ex_cldr` formatting, with an explicit fallback chain in the locale plug | A YAML key-lookup layer on top of Gettext. Kanta (KB verdict: skip) | `%{name}` interpolation already matches Gettext. `one`/`other` keys become `ngettext`. Lazy `t(".x")` keys need explicit names |
| `credentials.yml.enc`, `config/environments/*` | Per-environment config and secrets | business | MAP → `config/runtime.exs` + environment variables | Decrypting Rails credentials from Elixir | Export only `SECRET_KEY_BASE` and the other secrets the handoff needs. Remove them after cutover |
| Puma, bootsnap, Spring, Thruster | Runtime concurrency, boot cost, edge HTTP | platform | DELETE → one `mix release` on Bandit (TLS, HTTP/2) with `Plug.Static` serving gzip | Shipping Rails' Go proxy in front of Bandit (Campfire kept Thruster) | Keep an edge proxy only for operator-facing needs |
| paper_trail, Flipper, aasm | Audit, feature flags, state machines | business | MAP → `carbonite` (it also captures legacy writes) or audit rows in the Multi; `FunWithFlags`; `Ecto.Enum` + pattern-matched transition functions | A GenServer per record that holds its state (Iron Law 13) | Freeze `versions` as read-only history. Script `flipper_*` rows into `fun_with_flags_toggles` |

## Disappears on the BEAM (DELETE candidates)

- **Redis as Cable adapter, Solid Cable DB polling.** Delete when every node joins one Erlang cluster (`dns_cluster`, `libcluster`) and no Rails
  process still publishes. If Rails and Elixir run together, keep a bridge until Rails stops publishing.
- **The Action Cable server process, AnyCable.** Delete when no client is pinned to the Cable protocol, or when the Cable SHIM runs inside the Phoenix release.
- **Sidekiq, Resque and Solid Queue worker processes and their Procfile entries.** Delete once each job class is drained and its producers are switched
  off or write to `oban_jobs`.
- **Redis as job broker.** Delete when nothing else consumes the Redis queues and no rollback window needs Resque interchange. Campfire kept Redis for this role alone.
- **`after_commit` enqueue timing and `deliver_later` plumbing.** Always delete once the enqueue moves inside the transaction. On SQLite, budget for the single writer.
- **whenever, the crontab, sidekiq-cron, `recurring.yml`.** Delete once Oban Cron runs the entries. On Postgres the leader is elected. On the Lite
  engine (isolated peers), guarantee one active instance and no overlapping deploys.
- **memcached or Redis as a cache server.** Delete on a single node (ETS or Cachex) or a cluster (per-node cache + PubSub invalidation). Do not delete
  while Rails still writes the cached tables unless its writes invalidate too. Campfire PR #2 served stale authorization that way.
- **Russian-doll and fragment caching, `touch` chains.** Delete once measurement shows HEEx rendering fits the latency budget. Keep a counter column if queries read it.
- **Puma threads and workers, bootsnap, Spring, `preload_app!`.** Always delete. `POOL_SIZE` for Ecto is the only remaining knob.
- **`CurrentAttributes`, RequestStore.** Delete once every context function takes the scope and every job receives its context in args.
- **bullet and `strict_loading`.** Always delete: an unloaded association raises. N+1 queries still happen from Repo calls in loops (Campfire push and render paths).
- **Rack::Lock, Rack::Runtime, Thruster.** Delete when Bandit covers TLS, HTTP/2 and compression, and edge features such as X-Accel-Redirect
  or response caching have been moved to the CDN or a plug.
- **Redlock and Kredis locks.** Replace with Postgres advisory or row locks, or `:global` on a cluster. Oban `unique:` fits only where
  the lock merely stopped duplicate enqueues. While both runtimes write, use a DB lock that both respect.
- **`ActiveSupport::Notifications` and lograge.** Always delete in favor of `:telemetry` handlers and `logger_json`.

## Keep or shim (with conditions)

- **Action Cable protocol adapter (SHIM).** Use it while the Turbo JS, Hotwire Native shells or old tabs stay. Build it on `websock_adapter` over
  `Phoenix.PubSub`. It must handle welcome, ping, confirm, reject, identifier serialization and reconnect, and it authorizes every subscription
  through a context function, never by signature alone. Sunset it after the frontend moves to LiveView or Channels and the maximum tab lifetime has
  passed. Campfire's `cable.ex` is justified as this shim, not as the architecture.
- **Turbo Stream responses (KEEP).** While Turbo stays, `text/vnd.turbo-stream.html` bodies and DOM ids are a client contract. Render them with HEEx.
- **Rails ↔ Elixir realtime bridge (SHIM, coexistence only).** A narrow, supervised publisher to the Rails Cable Redis channel names, behind a flag,
  on private authenticated Redis (Campfire B9: anyone who can `PUBLISH` can force disconnects). Never block in `init` (Campfire C8). Use
  `phoenix_pubsub_redis` only when BEAM nodes cannot cluster: it does not speak the Action Cable format.
- **Resque and Sidekiq interop.** Elixir never consumes the legacy job formats. Keep Redix only to drain the backlog and quarantine unsupported
  payloads. Sunset gate: the backlog is zero and the producers are off. Unsupported jobs are reported, never dropped.
- **Legacy cookie reader (SHIM).** One way: decrypt with `Plug.Crypto.KeyGenerator` and AES-256-GCM, then mint a `phx.gen.auth` session. Keep
  `SECRET_KEY_BASE`. Sunset after the remember-me lifetime. Write Rails cookies from Elixir only when a tested rollback window requires Rails to
  read them, and then test both directions. Treat leftover Marshal sessions as logged out.
- **Persisted capabilities (KEEP narrow verifiers).** Signed ids, sgids in Action Text and ActiveStorage redirect URLs embedded in messages or
  emails may never expire [U: blob signed ids carry no expiry unless `urls_expire_in` is set]. Keep one verifier per purpose for as long as such
  content exists. Issue new links with `Phoenix.Token`.
- **ActiveStorage variation digest (SHIM).** Keep a Marshal encoder for the transformation hash only (Campfire `marshal.ex`, justified), never a
  general decoder. Alternatively regenerate variants under new keys and redirect old URLs.
- **`schema_migrations` and `ar_internal_metadata` (KEEP).** Leave them untouched while Rails rollback is possible. Ecto uses its own `migration_source`.
- **ActiveAdmin and Avo (KEEP on Rails).** Port the admin last. Until then it runs against the shared DB, under the per-table write-ownership rules.
- **Redis shared with other services (KEEP as an integration).** If other apps use the same Redis, keep it behind an owned module (Iron Law 20), but
  give this app's cache, pubsub and jobs BEAM-native homes.
- **Hotwire Native apps.** Keep Turbo-served pages for them, or give them a JSON API. A LiveView page is not a Turbo visit.

## Questions the architect must ask

1. Which cutover mode applies (Replacement, Staged cutover or Sustained coexistence), and does the data stay on the same DB, files and sessions
   or move by import? It decides SHIM versus REPLACE for Cable, cookies and Resque.
2. What do `config.load_defaults`, `cookies_serializer` and the key-generator digest say? JSON allows a one-way read. Marshal needs `:hybrid` weeks
   before cutover.
3. Which clients speak Action Cable or Turbo Streams and cannot update in lockstep (Hotwire Native, old tabs, third parties)? They require the Cable adapter.
4. For each callback and broadcast, what is the side effect and its order (touch, unread, search indexing, jobs)? Ecto writes run none of them,
   and a shared DB needs bridged events.
5. Which signed capabilities are already outside the app (email links, `signed_id`, sgids in rich text, ActiveStorage URLs in messages)? They set the SHIM lifetime.
6. For each job class: what is the retry policy, is it idempotent, and what is the backlog, including scheduled jobs? Is Redis persistent (AOF)?
   That decides the drain/import plan. Campfire's Redis was not persistent.
7. Which `dependent:`, `touch:` and `counter_cache` rules exist only in Ruby, with no DB constraint? Ecto deletes will not cascade.
8. Is Redis shared with other services, or used only by this app? That is the difference between KEEP and DELETE.
9. Is the target a single node, a cluster, or a SQLite appliance? It picks the Oban engine and peer, the PubSub topology, and the per-node limits for ETS caches and rate limits.
10. Which monkeypatches, initializers and gem settings change behavior (inflections, Devise pepper and stretches, time zone, host authorization)?
    They are hidden contracts.
11. Does the app use `structure.sql` (triggers, check constraints, FTS)? It is the Ecto baseline, and its triggers are behavior.
12. Which ActiveStorage services, key layouts and variant digests exist? Storage keys are a data contract.
13. Which locales, fallbacks and `_html` keys exist? They shape the Gettext conversion and the escaping audit.
14. What does rollback mean: restoring a snapshot, or Rails reading Elixir's writes? The second needs dual-format writes and a rehearsal.

## Libraries (versions checked by the plugin author on hex.pm, 2026-10-09; re-check before pinning)

| Need | Package | Version | Notes |
|---|---|---|---|
| Web, router, Channels | `phoenix` | 1.8.15 | Scopes, `phx.gen.auth`, verified routes |
| Server UI | `phoenix_live_view` | 1.2.12 | Streams, colocated hooks and CSS |
| Fan-out, presence | `phoenix_pubsub` | 2.4.1 | `:pg`, no Redis |
| HTTP server | `bandit` | 1.12.5 | Phoenix 1.8 default |
| Data | `ecto` / `ecto_sql` | 3.14.2 / 3.14.0 | `Repo.transact/2` since 3.13 |
| Adapters | `postgrex` / `myxql` / `ecto_sqlite3` | 0.22.4 / 0.9.0 / 0.25.0 | SQLite: one writer; check pool and transaction mode |
| 404 for missing records | `phoenix_ecto` | 4.7.0 | `Ecto.NoResultsError` → 404 |
| Jobs, cron | `oban` / `oban_web` | 2.24.1 / 2.13.1 | Lite (SQLite), Dolphin (MySQL 8.4+). Web is Apache-2.0 |
| Cookie and signature crypto | `plug_crypto` | 2.2.0 | `KeyGenerator` for one-way Rails cookie reads |
| Cable SHIM transport | `websock_adapter` | 0.6.0 | Raw WebSocket upgrade for a protocol adapter |
| Node-to-node pubsub over Redis | `phoenix_pubsub_redis` | 3.1.1 | Only when nodes cannot cluster. Not Action Cable compatible |
| Transitional Redis | `redix` | 1.9.2 | Drain and bridge only, with a removal milestone |
| Do not adopt | `exq` | 0.25.0 | Resque/Sidekiq-compatible on Redis: the Campfire trap |
| Legacy cookie store | `plug_rails_cookie_session_store` | 2.0.0 | Stale (2021). Legacy AES-CBC only, not the 5.2+ GCM default |
| Handoff token | `joken` | 2.7.0 | Short-lived HS256 handoff from Rails |
| Password hashes | `bcrypt_elixir` | 3.3.2 | Verifies Devise `$2a$` hashes |
| Authorization | `bodyguard` / `let_me` | 2.4.3 / 3.0.4 | Pundit-like / declarative rules |
| Rate limiting | `hammer` / `plug_attack` | 7.5.0 / 0.4.3 | `plug_attack` is stale (2021) but in production per the KB |
| Cache | `cachex` | 4.1.1 | TTL, `fetch/3`, limits |
| Email | `swoosh` / `mail` | 1.29.0 / 0.5.2 | Native provider adapters. `mail` parses inbound MIME |
| Storage | `ex_aws` / `ex_aws_s3` | 2.7.0 / 2.5.9 | KB gotchas: `encryption:` option, req 0.7 `get_to_post` |
| Images | `image` / `vix` | 0.72.0 / 0.42.0 | libvips in process. Run in Oban jobs |
| Sanitizer | `html_sanitize_ex` | 1.5.5 | Action Text allow-list |
| HTML parsing | `lazy_html` | 0.1.13 | Also the LiveViewTest engine |
| i18n | `gettext` / `ex_cldr` | 1.0.2 / 2.47.5 | Kanta: KB verdict skip |
| Time zones | `tz` | 0.28.4 | Rails zone names → IANA |
| Encrypted fields | `cloak_ecto` | 1.3.0 | Stable. Re-encrypt via backfill |
| YAML history | `yaml_elixir` | 2.12.2 | Read paper_trail `object` columns only |
| Audit | `carbonite` | 0.17.0 | Trigger-based. Captures legacy writes |
| Feature flags | `fun_with_flags` | 1.13.0 | Flipper-like gates |
| Web Push | `web_push_elixir` / `web_push_encryption` | 0.8.0 / 0.3.1 | Small user base / stale (2021, legacy `aesgcm`) |
| Strangler proxy | `reverse_proxy_plug` | 3.0.4 | Forward unported paths to Rails |
| Clustering | `dns_cluster` / `libcluster` | 0.3.1 / 3.5.0 | Phoenix default / Kubernetes and gossip strategies |
| Structured logs | `logger_json` | 7.0.4 | Replaces lograge formats; attach `:telemetry` handlers for metrics |
| Non-durable schedules | `quantum` | 3.5.3 | Stable (2024-02). Never for business-critical jobs |
