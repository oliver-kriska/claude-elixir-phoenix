# Laravel → Elixir

Laravel 10–12.x on MySQL or Postgres (cookie and session facts checked against `laravel/framework` 12.x source), with Livewire, Inertia,
Horizon and Reverb/Echo, plus short Symfony rows (Doctrine, Messenger, Security). Read this alongside the verdict vocabulary and reason tags in the
elixir-way SKILL.md. `[U]` marks a framework detail that was not re-verified on 2026-10-09. Confirm it in the pinned package source before you rely on it.

## Probe: where mechanisms hide

| Look at | What it reveals | Contract or purpose to capture |
|---|---|---|
| `app/Models/**/*.php` → `function booted\|static::(creating\|saving\|updating\|deleting)\|#\[ObservedBy`; `app/Observers/**` | Model events and observers | Side effects and their order. `saveQuietly`, `withoutEvents` and mass `update()` already skip them |
| `addGlobalScope\|#\[ScopedBy\|use SoftDeletes\|function scope[A-Z]` | Global and local scopes | Implicit filters on every query (soft delete, tenancy, `active`) |
| `\$casts\|function casts\(\)\|Attribute::make\|get\w+Attribute\|set\w+Attribute\|\$appends` | Casts, accessors, mutators | Stored versus presented values, encrypted casts (`APP_KEY`), enums, computed fields appended to JSON |
| `\$hidden\|\$visible\|toArray\|JsonResource\|ResourceCollection` | JSON shape | Fields hidden from output (password hashes) and the exact response shape |
| `\$fillable\|\$guarded\|\$with\b\|\$touches\|preventLazyLoading` | Mass assignment, default eager loads, touch | Which attributes are writable, which relations load by default, which parents get touched |
| `morphTo\|morphMany\|morphMap\|enforceMorphMap` | Polymorphic types | Whether `*_type` stores class names (`App\Models\Post`) or morph-map aliases |
| `HasUuids\|HasUlids\|\$keyType\|\$incrementing = false` | Non-integer keys | `char(36)` and `char(26)` columns, ordering assumptions |
| `bootstrap/app.php` (11+) or `app/Http/Kernel.php` (≤10) → `withMiddleware\|middlewareGroups\|TrimStrings\|ConvertEmptyStringsToNull\|EncryptCookies` | Middleware order and input normalization | Global trimming and empty-to-null conversion, cookies excluded from encryption, CSRF exceptions (`except` lists) |
| `routes/*.php` + `php artisan route:list` → `->name\(\|->middleware\(\|->scopeBindings\|->withTrashed\|getRouteKeyName` | URL contract, route-model binding | Route names (used by Ziggy in JS), slug keys, scoped and soft-deleted bindings |
| `app/Http/Requests/**` → `function rules\|function authorize\|prepareForValidation\|function messages` | Validation and authorization per request | Rules, messages, the 422 error shape, redirect-back behavior |
| `app/Policies/**`, `Gate::(define\|before\|after)`, `@can\|->can\(\|authorize\(` | Authorization | Implicit `Gate::before` super-admin allows, and policy auto-discovery by naming convention |
| `config/session.php`, `config/auth.php`, `.env` → `SESSION_DRIVER\|serialization\|lifetime\|guards\|APP_KEY\|APP_PREVIOUS_KEYS` | Session store and crypto | Driver (file, redis, database), PHP or JSON payload serialization, guard names, key rotation |
| `config/sanctum.php`, `personal_access_tokens`, `EnsureFrontendRequestsAreStateful`, `config/passport.php` | SPA and API auth | Stateful domains, the `XSRF-TOKEN` cookie flow, token abilities, OAuth clients |
| `URL::(signedRoute\|temporarySignedRoute)\|hasValidSignature\|middleware\('signed'` | Signed URLs already sent | Purpose, expiry, and where they live (verification and unsubscribe emails) |
| `config/queue.php`, `app/Jobs/**` → `ShouldQueue\|\$tries\|\$backoff\|\$timeout\|retry_after\|after_commit\|ShouldBeUnique` | Queue semantics | Attempts, backoff, timeout versus `retry_after` (redelivery duplicates), after-commit dispatch, uniqueness locks |
| `jobs`, `failed_jobs`, `job_batches` tables; `config/horizon.php` | Queue state and supervision | Backlog, delayed jobs (`available_at`), failure retention, Horizon supervisors and balancing |
| `routes/console.php` (11+) or `app/Console/Kernel.php` → `Schedule::\|withoutOverlapping\|onOneServer\|runInBackground` | Scheduler | Time zone, overlap policy, single-server execution |
| `app/{Events,Listeners}/**`, `routes/channels.php`, `resources/js/**` → `ShouldBroadcast\|broadcastAs\|toOthers\|Echo\.\|\.private\(\|\.join\(` | Events and broadcasting | Listener side effects (queued or not), channel names, auth callbacks, the event names the JS listens for |
| `app/Livewire/**`, `resources/views/livewire/**` → `#\[Locked\|#\[Url\|wire:model\|wire:poll\|\$dispatch\|WithFileUploads` | Livewire components | Public state, URL-bound state, polling, events between components, uploads |
| `HandleInertiaRequests` → `share\(\|version\(`; `Inertia::(render\|lazy\|location)` | The Inertia contract | Shared props on every response, asset version, partial reloads, page component names |
| `app/Providers/**` → `register\(\|boot\(\|macro\(\|shouldBeStrict`; `env\(` outside `config/` | Container bindings, macros, config reads | Implementation swaps and monkeypatch-like macros. `env()` outside config files returns null under `config:cache`, so that code was already broken in production |
| `lang/**/*.php`, `lang/*.json` → `__\(\|trans\(\|trans_choice\(\|@lang` | i18n | Key style (dotted keys or source strings), `:name` placeholders, `trans_choice` ranges |
| `database/migrations/**`, `database/schema/*.sql` → `->morphs\(\|->foreignId\(\|->cascadeOnDelete\|DB::statement` | DDL, cascades, raw SQL | Which cascades the DB enforces, morph columns, raw triggers and views |
| `supervisord.conf`, `config/octane.php`, FPM pool files, `Procfile` → `pm.max_children\|numprocs\|octane` | Process topology | Why each process exists. Octane hints that state leaks have already been fought |
| Symfony `config/packages/{messenger,security,doctrine}.yaml` → `PrePersist\|PostPersist\|AsMessageHandler\|AsEventListener\|extends Voter` | Doctrine callbacks, Messenger, voters, kernel listeners | Lifecycle side effects, transport retry strategy, authorization votes, request/response listeners |

## Mechanism map

| Legacy mechanism | Usual purpose (why) | Reason tags | Default verdict → Elixir way | Literal-translation trap | Cutover / compat note |
|---|---|---|---|---|---|
| `routes/web.php`/`api.php`, named routes, `route()`, Ziggy | Map URLs to handlers; names in Blade and JS | contract | MAP → `Phoenix.Router` + verified routes `~p` | A route-name map module generated from `route:list` | JS that calls Ziggy's `route('posts.show')` needs a generated manifest or rewritten links. Keep the URLs |
| Middleware groups, `TrimStrings`, `ConvertEmptyStringsToNull` | Cross-cutting work, global input normalization | business | MAP → router pipelines, with normalization in changesets | A global plug that rewrites `conn.params` | Ecto's default `empty_values` already turns `""` and whitespace into nil, roughly like ConvertEmptyStringsToNull. Ecto never trims non-empty strings, so add `update_change(:x, &String.trim/1)` where TrimStrings mattered, and honor its `except` list (passwords) |
| Controllers + FormRequest | Validate and authorize before the action | business | MAP → a changeset per operation + a scope check in the context | Porting FormRequest as a macro DSL | JSON errors are 422 `{"message", "errors": {"field": [...]}}`. Web forms redirect back with errors and old input |
| Route-model binding | Load the model named in the URL | business | MAP → load through the scope in the context (`Blog.get_post_by_slug!(scope, slug)`) | A global plug calling `Repo.get!` that ignores the scope | Custom keys (`getRouteKeyName`), scoped bindings and soft-deleted exclusion are contracts. `Ecto.NoResultsError` gives the same 404 |
| Blade, components, directives (`@csrf`, `@can`, `@auth`) | Compose HTML | business | MAP → HEEx components. `@can` becomes assigns derived from the scope | Porting `{!! $html !!}` straight to `raw/1` | Audit every `{!! !!}` (Iron Law 12) |
| Livewire components | Stateful server components | platform | REPLACE → LiveView and LiveComponents. `wire:model` → `phx-change` forms, `$dispatch` → `send/2` or PubSub, `wire:poll` → server push | Porting the snapshot-and-checksum round trip, or parking component state in Redis or ETS per session | Livewire ships component state through the browser on every request because PHP keeps nothing between requests [U: checksum details]. In LiveView the state lives in the process, but `handle_event` params are still untrusted (Iron Law 11) |
| Alpine.js | Client-side interactivity | business | MAP → `Phoenix.LiveView.JS` or colocated hooks. KEEP Alpine for purely client-side widgets | Rewriting every Alpine snippet as a hook | Alpine inside LiveView needs the `onBeforeElUpdated` clone hook from the LiveView JS-interop guide |
| Inertia | SPA pages (Vue, React) with server routing | business | KEEP the frontend with the `inertia` hex adapter (official inertiajs org), or REPLACE page by page with LiveView | Rewriting a large React or Vue frontend into LiveView by default | Shared props (`share()`), asset version 409 + `X-Inertia-Location`, partial reloads, the `errors` prop shape, page component names |
| Eloquent models, `$fillable`/`$guarded` | Active record with mass-assignment safety | business | MAP → schema + changesets + context. `$table`, `$primaryKey`, `CREATED_AT` → `schema "..."`, `@primary_key`, `@timestamps_opts`; renamed columns via `source:`; `@schema_prefix` for tables outside `public` on Postgres. `cast/3` allow-list per operation | Wrappers that mimic `Post::find` and `->save()`. Casting every schema field | Map onto the existing tables |
| `$casts`, accessors/mutators, PHP backed enums | Stored versus presented values | business / contract | MAP → Ecto types, `Ecto.Enum` (string or integer values), virtual fields computed in the context or the JSON module | Protocol tricks that emulate lazy accessors | Encrypted casts use `APP_KEY`. Backfill them into `cloak_ecto` through a decrypt-only shim |
| `$hidden`/`$visible`/`$appends`, API Resources | Control JSON output | contract | MAP → JSON modules with explicit fields | `@derive Jason.Encoder` on schemas, which leaks the password hashes that `$hidden` protected | Freeze response shapes with golden files |
| `$with`, lazy loading, `preventLazyLoading` | Default eager loads; lazy convenience | historical | MAP → explicit `preload` in context queries (Iron Law 6) | A lazy-load helper that calls the Repo on access | Responses that embed `$with` relations by default must keep them |
| Model events and observers | Side effects on persistence | business (often historical) | MAP → an explicit pipeline: changeset → `Repo.transact` → `Oban.insert` → PubSub after commit | An event-registry GenServer | `saveQuietly`, `withoutEvents` and mass `update()` skip events in legacy. Keep the same coverage |
| Global scopes, `SoftDeletes` | Implicit filters | business | MAP → query functions, with `Repo.prepare_query/3` enforcing the filter; `where: is_nil(p.deleted_at)` | A hidden magic filter | `withTrashed()` call sites list the exceptions. Check partial unique indexes |
| Polymorphic `morphTo` | One FK pointing at many tables | contract | MAP → `Ecto.Enum, values: [post: "App\\Models\\Post"]` (or the morph-map aliases) + a plain `*_id` | Resolving class-name strings to modules at runtime (Iron Law 10) | Values are class names unless `enforceMorphMap` is on, so a PHP namespace rename breaks them |
| UUID/ULID keys (`HasUuids`, `HasUlids`) | Non-guessable or sortable ids | business | MAP → `@primary_key {:id, :string, autogenerate: false}` for `char` columns under MyXQL, or a custom type. Generate ids in the changeset | `Ecto.UUID` or `:binary_id` over `char(36)` (they dump 16 bytes) | Queries may assume ULID ordering |
| MySQL conventions: `timestamp`, unsigned bigint, `tinyint(1)` | Laravel defaults on MySQL | contract | MAP → `timestamps(type: :naive_datetime)` in the app time zone, `:id`, `:boolean` (MyXQL loads 0/1) | Assuming `utc_datetime_usec` | Check the connection charset before any write: some deployments deliberately send UTF-8 bytes over a latin1 connection |
| `migrations` table, `schema:dump` | Versioned DDL | contract | KEEP the `migrations` table. MAP new DDL to Ecto with an explicit `migration_source`, with the baseline from `database/schema/*.sql` | Porting the historical migrations | No table-name collision with Ecto, but one DDL owner at a time |
| Validation rules, the `unique:` rule | Input integrity | business | MAP → changeset validations + a DB unique index + `unique_constraint/3` | Uniqueness checked by an app-level SELECT | Dedupe and add the missing indexes first |
| Queues (`ShouldQueue` on redis, database or sqs) | Work beyond the share-nothing request | reliability, platform | MAP → an Oban worker inserted in the same transaction. Dolphin engine on MySQL 8.4+, Postgres engine otherwise | Consuming Laravel payloads from Redis or the `jobs` table (`data.command` is a PHP-serialized object): the Campfire Resque-worker trap | Drain per job class. During coexistence, Laravel can insert into `oban_jobs` with `DB::table(...)->insert` [U] |
| Queue semantics: `$tries`, `$backoff`, `retry_after` versus `--timeout`, `after_commit`, `ShouldBeUnique` | Delivery and duplicate control | business | MAP → `max_attempts`, `backoff/1`, `timeout/1`, `unique:`. DELETE `after_commit`: insert inside the transaction | Recreating cache-lock uniqueness | Defaults are `retry_after` 90 s and worker timeout 60 s. Jobs that ran past `retry_after` were redelivered, so check each job's idempotency (Iron Law 7) |
| Batches and chains (`Bus::batch`, `Bus::chain`, `job_batches`) | Fan-out/fan-in | business | REPLACE → enqueue the next step from `perform/1`. Oban Pro Batch or Chain (paid) only if needed | ETS counters with polling | Batch progress UIs move to PubSub |
| Horizon | Supervise Redis workers, auto-balance, metrics | reliability, platform | DELETE → Oban queues in the release + `oban_web` (Apache-2.0) + `oban_met`. Balancing becomes per-queue `limit` | DynamicSupervisor auto-scaling of worker pools | Tags and metrics that ops use map to Oban telemetry |
| Scheduler (`schedule:run` cron, `withoutOverlapping`, `onOneServer`) | Run periodic tasks once | reliability, platform | MAP → Oban cron (top-level `cron:` key, `Oban.Cron`, Oban 2.24+); `withoutOverlapping` → `unique: [period: :infinity, states: :incomplete]`, which skips inserting a tick while one is unfinished. DELETE the cache locks | A `Process.send_after` loop | Remove the crontab line in the same deploy |
| Events and listeners (`Event::dispatch`, queued listeners) | Decouple side effects | business (often historical) | MAP → direct context calls. Queued listeners → Oban. In-app fan-out → PubSub | A generic event bus | — |
| Broadcasting: `ShouldBroadcast`, Echo, Reverb/Pusher/Soketi, `routes/channels.php` | Realtime from share-nothing PHP | platform | REPLACE → `Phoenix.Channel` or LiveView + PubSub, presence channels → `Phoenix.Presence`. SHIM → keep the Pusher-protocol server and publish through its HTTP API with `Req` | Re-implementing the Pusher protocol in Elixir as the target | Channel names (`private-`, `presence-`), `broadcastAs` event names, `/broadcasting/auth` signatures, `toOthers()` through `X-Socket-ID` |
| Notifications (`via()`, `notifications` table) | Multi-channel notifications | business | MAP → a Notifications context + one Oban job per channel + PubSub | Porting the channel-driver class hierarchy | Keep the table: `type` holds class names, `data` is JSON, `notifiable_type` is a morph |
| Mail (Mailables, Markdown mail, queued mail) | Transactional email | business | MAP → `Swoosh` + HEEx or `phoenix_swoosh` + Oban | A provider SDK next to Swoosh | Dedupe by idempotency key while both apps send |
| Cache (`Cache::remember`, tags, `Cache::lock`) | A shared cache across FPM workers | reliability, platform | REPLACE → ETS or `Cachex`. Locks → advisory or row locks, `:global`; Oban `unique:` only for duplicate enqueues | One GenServer as the cache, or a public ETS table wiped at 4,096 entries (Campfire). Reading Laravel's PHP-serialized cache entries | Invalidate on legacy writes during coexistence |
| Sessions (file, redis, database) | Per-user state across share-nothing requests | platform | REPLACE → `phx.gen.auth`. SHIM → a handoff endpoint or a one-way read | A PHP `unserialize()` parser (Campfire wrote a Ruby Marshal codec for the same reason) | Switch `session.serialization` to `json` before cutover (the option exists in 12.x). The default payload is PHP `serialize()` |
| EncryptCookies + the `APP_KEY` Encrypter | Tamper-proof, confidential cookies | contract | SHIM → a decrypt-only reader (AES-256-CBC + HMAC-SHA256 through `:crypto`) for the cutover | Writing Laravel-encrypted cookies from Elixir | Validate and strip the `hash_hmac('sha1', name . 'v2', key) . '\|'` prefix. Try `APP_PREVIOUS_KEYS` for rotated keys |
| Auth guards, Breeze/Fortify/Jetstream, remember-me | Login flows | business | REPLACE → `phx.gen.auth`. `$2y$` hashes: swap the prefix to `$2b$` before `Bcrypt.verify_pass`. `$argon2id$` → `Argon2.verify_pass`. Rehash on login | Porting guards and user providers | The `remember_web_*` cookie holds `id\|token\|hash` [U]. Honor it through the handoff, or force a re-login deliberately |
| Sanctum (SPA cookies, PATs), Passport | SPA and API auth | business / contract | MAP → Phoenix session + CSRF for the SPA. PATs verify natively (`{id}\|{plaintext}`, SHA-256 stored [U]), so keep the scheme. Passport → `boruta` | JWT sessions for the SPA | axios sends `X-XSRF-TOKEN` from the `XSRF-TOKEN` cookie. Keep that cookie contract with a plug, or switch the SPA to the meta tag |
| Gates, policies, spatie/laravel-permission | Authorization | business | MAP → context functions that take `%Scope{}`; `Bodyguard` or `LetMe`; `Permit` (KB: evaluate) for role-heavy models | A global, reflective policy lookup by naming convention | Make `Gate::before` super-admin allows explicit. Keep the `roles`, `permissions` and `model_has_*` tables as a read model |
| Signed URLs (`signedRoute`, `temporarySignedRoute`) | Stateless links | contract | SHIM → a narrow HMAC-SHA256 verifier for links already sent [U]. New links use `Phoenix.Token` | Porting a general-purpose URL signer | Unsubscribe links can be permanent, which makes the verifier a KEEP |
| Service container, providers, facades, macros | Swap implementations; global access | historical (DI inside a request platform) | MAP → behaviours + config + explicit module arguments. DELETE the container | A registry GenServer. Facades as singleton processes | Macros (`Str::macro`) become plain functions |
| Config, `.env`, `config:cache`, Artisan commands | Config and ops scripts | business | MAP → `config/runtime.exs` and release functions (`bin/app eval`). Long backfills become Oban jobs | `env()` reads at runtime. Mix tasks in production | Export `APP_KEY` only for the handoff, then remove it |
| Storage disks (Flysystem), `storage:link`, Spatie MediaLibrary | Files on local disk or S3 | business | KEEP the paths. MAP → `ExAws.S3`, `Plug.Static` for the public disk, LiveView uploads, conversions with `image` in Oban | Re-implementing Flysystem | Keep the MediaLibrary `media` table (`model_type`, `collection_name`, `conversions_disk`) as a read model |
| Telescope, Pulse | Observability | business | MAP → `:telemetry` + `phoenix_live_dashboard` + `oban_web` | Porting request-recording middleware | — |
| Cashier, Scout, Pennant | Billing, search, feature flags | business | MAP → `stripity_stripe` behind a facade + an Oban webhook job unique on the event id; Postgres FTS or a search client with Oban index sync; `FunWithFlags` | Porting Cashier as a library | Keep `subscriptions` and `subscription_items` as a read model. Script Pennant `features` into `fun_with_flags_toggles` |
| PHP-FPM, OPcache, Octane, Supervisor workers | Share-nothing concurrency, boot cost | platform | DELETE → one release on BEAM schedulers | Tuning process counts | `POOL_SIZE` is the remaining knob |
| Symfony Doctrine ORM (unit of work, lifecycle callbacks, lazy proxies) | Data mapper with an identity map | business | MAP → Ecto schemas + an explicit `Ecto.Multi`. Callbacks → the explicit pipeline. KEEP `doctrine_migration_versions` [U: default table name] | Emulating the identity map and `flush()` | Doctrine's flush ordering becomes an explicit Multi step order |
| Symfony Messenger | Async messages and jobs | reliability, platform | MAP → Oban (the doctrine transport becomes a transactional insert). `retry_strategy` → `max_attempts` and `backoff/1` | Consuming Messenger envelopes (PHP-serialized by default [U]) | Drain the transports. Keep `messenger_messages` read-only for inspection |
| Symfony Security, voters, Forms, Twig, kernel listeners, Mercure | Auth, authorization, forms, templates, request hooks, SSE push | business (Mercure: platform) | MAP → plugs + scope functions (voters), changesets + `to_form`, HEEx, Endpoint plugs (`kernel.request`/`kernel.response`). Mercure → PubSub + Channels or LiveView | One giant `Voter`-style dispatcher | `auto` password hashers produce bcrypt or `$argon2id$` hashes. Verify with `bcrypt_elixir` or `argon2_elixir` |

## Disappears on the BEAM (DELETE candidates)

- **PHP-FPM pools, `pm.max_children`, OPcache tuning, Octane workers and their state-leak resets.** Always delete.
- **Supervisor/systemd queue workers and Horizon.** Delete once each job class is drained, including delayed jobs (`available_at`), its producers
  are off or insert into `oban_jobs`, and ops dashboards point at `oban_web`.
- **Redis as queue broker.** Delete when no other app consumes those queues. Apps on the `database` queue driver (the Laravel 11+ skeleton default [U]) drain the `jobs` table instead.
- **Reverb, Soketi, Pusher.** Delete when no Echo client remains: web moved to `phoenix.js` or LiveView, mobile apps updated. Until then, SHIM.
- **The `schedule:run` crontab with `onOneServer` and `withoutOverlapping` cache locks.** Delete once Oban Cron runs the entries. On the SQLite
  Lite engine (isolated peers), guarantee one active instance.
- **`Cache::lock` and `ShouldBeUnique` locks.** Replace `ShouldBeUnique` with Oban `unique:` (it suppresses duplicate inserts, not
  concurrent runs) and `Cache::lock` with advisory locks. While both runtimes contend for the same work, use a DB lock that both respect.
- **`config:cache`, `route:cache`, `view:cache`, `event:cache`.** Always delete: config loads at boot, and routes and templates compile.
- **Livewire snapshots, checksums and `#[Locked]`.** Delete page by page, once each page is a LiveView.
- **The service container, facades and provider `register` wiring.** Always delete.
- **The `after_commit` queue option, `ShouldQueueAfterCommit`, `DB::afterCommit`.** Always delete once enqueue happens inside the transaction.
- **`preventLazyLoading`, `$with` tuning, Debugbar N+1 hunting.** Always delete: an unloaded association raises. Still review Repo calls inside loops.
- **Redis or memcached as a cache server.** Delete on a single node (ETS, Cachex) or a cluster (per-node cache + PubSub invalidation). Do not
  delete while Laravel still writes the cached tables unless those writes invalidate too.
- **Telescope and Pulse storage tables.** Delete once telemetry dashboards replace them.
- **File and redis session drivers.** Delete after the handoff window: the longest session or remember-me lifetime.

## Keep or shim (with conditions)

- **Inertia frontend (KEEP).** Swap only the backend adapter to `inertia`. Preserve shared props, the asset-version 409 flow, partial reloads and the
  `errors` prop. No sunset is needed if the team keeps Vue or React. Regenerate the Ziggy route manifest from Phoenix routes, or rewrite the links.
- **Pusher-protocol server (SHIM).** Keep Reverb, Soketi or Pusher running while Echo clients exist. Elixir publishes through the Pusher HTTP API
  with `Req` and answers `/broadcasting/auth` with the same HMAC, so private and presence channels keep working [U]. Sunset when the Echo clients are gone.
- **`APP_KEY` decrypt-only shim (SHIM).** For the session handoff and the encrypted-cast backfill only. It never encrypts new data. Sunset after
  the session lifetime has passed and the backfill is complete.
- **Signed URL verifier (KEEP narrow).** For verification and unsubscribe links already in inboxes. It lives as long as the longest-lived link, and
  permanent unsubscribe links make it permanent.
- **Sanctum personal access tokens (KEEP the scheme).** They verify natively in Elixir, so API clients keep working without re-issuing tokens.
- **`migrations`, `notifications`, `failed_jobs` (KEEP as read models).** Keep `failed_jobs` for explicit replay-or-discard decisions. Never auto-replay it.
- **Filament and Nova (KEEP on legacy).** Port the admin last. Until then it writes to the shared DB under the per-table ownership rules.
- **Redis shared with other PHP services (KEEP as an integration).** Wrap it in an owned module (Iron Law 20). This app's cache, pubsub and jobs still move to BEAM-native homes.
- **MySQL older than 8.4.** Oban's Dolphin engine needs 8.4+. Upgrade MySQL first, or keep jobs in a separate Postgres repo and document the
  lost atomic enqueue with an explicit outbox. Never fall back to an in-memory queue.
- **Symfony Mercure hub (SHIM).** Keep it while SSE clients exist. Elixir publishes to it over HTTP. Sunset when clients move to Channels or LiveView.
- **Symfony Messenger producers (SHIM).** Unported code dispatches into `oban_jobs` with a plain insert, rather than Elixir consuming Messenger envelopes.

## Questions the architect must ask

1. Which driver serves each concern: session, cache, queue, broadcast? Redis may not exist at all, which changes what gets deleted.
2. Per page: Blade, Livewire or Inertia? Will the Vue or React frontend stay? That decides REPLACE with LiveView or KEEP with the `inertia` adapter.
3. Which MySQL version runs in production? Dolphin needs 8.4+. Otherwise upgrade, or keep a separate Postgres jobs repo and lose atomic enqueue.
4. Is `session.serialization` set to `php` or `json`? Which Laravel version, and how long does remember-me last? Together they decide the handoff and which sessions survive.
5. Which Echo clients exist (web, mobile), and which private and presence channels and event names do they use? That sets the Pusher shim's lifetime.
6. What is in the queues: delayed jobs, `failed_jobs` awaiting a decision, jobs that run past `retry_after`? Duplicates already happening reveal the idempotency gaps.
7. Which global scopes, `Gate::before` rules and auto-discovered policies exist? Implicit authorization must become explicit.
8. Which columns use encrypted casts, and has `APP_KEY` been rotated (`APP_PREVIOUS_KEYS`)? That sets the backfill plan.
9. Is a morph map enforced, or do `*_type` columns hold class names? That fixes the `Ecto.Enum` values.
10. Which inputs depend on `TrimStrings` and `ConvertEmptyStringsToNull`, and on their `except` lists? Normalization parity depends on it.
11. Which signed URLs are already in users' inboxes, and how long do they live? That sets the verifier's lifetime.
12. Is Octane in use, and what was the performance goal? Record the measured baseline, and check whether any state-leak workaround encodes a business rule.
13. Symfony: which Messenger transports and serializer, Doctrine lifecycle callbacks and voters exist? They go into the same ledger.
14. Which admin (Filament, Nova) do staff depend on, and can it stay on legacy until last?

## Libraries (versions checked by the plugin author on hex.pm, 2026-10-09; re-check before pinning)

| Need | Package | Version | Notes |
|---|---|---|---|
| Web, router, Channels | `phoenix` | 1.8.15 | Scopes, `phx.gen.auth`, verified routes, `Phoenix.Token` |
| Server UI | `phoenix_live_view` | 1.2.12 | Replaces Livewire |
| Fan-out, presence | `phoenix_pubsub` | 2.4.1 | Replaces Reverb and Pusher fan-out |
| Data | `ecto` / `ecto_sql` | 3.14.2 / 3.14.0 | `Repo.transact/2`, `prepare_query/3` |
| Adapters | `myxql` / `postgrex` | 0.9.0 / 0.22.4 | MyXQL loads `tinyint(1)` as boolean |
| 404 for missing records | `phoenix_ecto` | 4.7.0 | Route-model-binding 404 parity |
| Jobs, cron, dashboard | `oban` / `oban_web` / `oban_met` | 2.24.1 / 2.13.1 / 1.3.2 | Dolphin for MySQL 8.4+. Web is Apache-2.0 (replaces Horizon's UI) |
| Inertia backend | `inertia` | 3.0.1 | Official inertiajs org. Keeps Vue/React pages |
| Islands | `live_vue` / `live_react` | 1.2.3 / 2.0.0 | Single-maintainer community packages |
| Password hashes | `bcrypt_elixir` / `argon2_elixir` | 3.3.2 / 4.1.3 | Swap `$2y$` to `$2b$` before verifying |
| Authorization | `bodyguard` / `let_me` / `permit` | 2.4.3 / 3.0.4 / 0.4.1 | Permit: KB verdict evaluate |
| OAuth2 server | `boruta` | 2.3.8 | Replaces Passport |
| Rate limiting | `hammer` | 7.5.0 | Replaces `RateLimiter` and `throttle` |
| Cache | `cachex` | 4.1.1 | Replaces `Cache::remember` |
| Email | `swoosh` / `phoenix_swoosh` | 1.29.0 / 1.2.1 | Native provider adapters. `phoenix_swoosh` is stable |
| Encrypted fields | `cloak_ecto` | 1.3.0 | Stable. Backfill from encrypted casts |
| Storage | `ex_aws` / `ex_aws_s3` | 2.7.0 / 2.5.9 | KB gotchas: `encryption:` option, req 0.7 `get_to_post` |
| Images | `image` / `vix` | 0.72.0 / 0.42.0 | MediaLibrary conversions, run in Oban |
| HTTP client | `req` | 0.7.5 | Pusher HTTP API, Mercure publish, webhooks |
| Filtering, pagination | `flop` / `flop_phoenix` | 0.29.0 / 0.27.0 | Match `paginate()` envelopes in the JSON module |
| OpenAPI | `open_api_spex` | 3.22.4 | Replaces l5-swagger |
| i18n | `gettext` / `ex_cldr` | 1.0.2 / 2.47.5 | JSON source-string files convert almost directly; `:name` becomes `%{name}` |
| Payments | `stripity_stripe` | 3.3.2 | Community-maintained. Wrap it behind a facade (Iron Law 20) |
| Feature flags | `fun_with_flags` | 1.13.0 | Replaces Pennant |
| Admin | `backpex` | 0.22.0 | After Filament or Nova retires |
| Strangler proxy | `reverse_proxy_plug` | 3.0.4 | Forward unported paths to Laravel |
| Dashboards | `phoenix_live_dashboard` | 0.9.1 | Replaces Telescope and Pulse |
