# Django → Elixir

Django 4.2 LTS–5.x on Postgres or MySQL, with Celery (Redis or RabbitMQ broker), DRF and Channels, plus short Flask, SQLAlchemy and FastAPI rows.
Session and signing facts were checked against Django `main` source and the 5.2 docs. Read this alongside the verdict vocabulary and reason tags in the
elixir-way SKILL.md. `[U]` marks a framework detail that was not re-verified on 2026-10-09. Confirm it in the pinned package source before you rely on it.

## Probe: where mechanisms hide

| Look at | What it reveals | Contract or purpose to capture |
|---|---|---|
| `*/models.py`, `*/models/**` → `class Meta:` with `db_table\|ordering\|managed = False\|unique_together\|constraints` | Table names, default ordering, unmanaged tables | Tables are named `<app_label>_<model>` unless overridden. `Meta.ordering` silently orders every query. `managed = False` tables belong to another owner |
| `objects = \|class \w+Manager\|def get_queryset\|base_manager_name` | Custom default managers | Hidden filters on the default manager (soft delete, tenancy, `is_active`). Related lookups use `_base_manager` and skip them |
| `signals.py`, `apps.py` `ready()` → `@receiver\|post_save\|pre_save\|post_delete\|m2m_changed\|\.connect\(` | Persistence hooks | Side effects and their order. `QuerySet.update()`, `bulk_create` and raw SQL already bypass signals, so record which writes trigger effects |
| `def save\(\|def delete\(` in models | Overridden persistence | Derived fields, side effects and cascades hidden inside `save` |
| `ForeignKey\(\|OneToOneField\(` → `on_delete=` | Cascades | Django runs `CASCADE`, `SET_NULL` and `PROTECT` in Python. By default the DB FKs have no ON DELETE action (Postgres: DEFERRABLE INITIALLY DEFERRED) |
| `auto_now\|auto_now_add\|default=` with a callable | Values set in Python | No DB defaults exist, so Ecto and every other writer must set them |
| `CharField\(.*blank=True` without `null=True` | The empty-string convention | Django stores `""`, not NULL. Ecto `cast` turns `""` into nil by default |
| `settings.py` → `MIDDLEWARE\|ATOMIC_REQUESTS\|USE_TZ\|TIME_ZONE\|DEFAULT_AUTO_FIELD\|AUTH_USER_MODEL\|APPEND_SLASH` | Global behavior | Middleware order, per-request transactions, aware or naive datetimes, id width, the custom user table, trailing-slash redirects |
| `settings.py` → `SESSION_ENGINE\|SESSION_SERIALIZER\|SESSION_COOKIE_\w+\|SECRET_KEY_FALLBACKS\|PASSWORD_HASHERS\|CACHES` | Auth and cache crypto in force | Session store and serializer, cookie names, key rotation, hasher order (the first one hashes new passwords), cache backend (`LocMemCache` is per process) |
| `urls.py` → `path\(\|re_path\(\|include\(\|name=\|app_name`; callers → `reverse\(\|{% url` | URL contract | Names and namespaces used by `reverse`, regex converters, trailing slashes |
| `templates/**`, `templatetags/*.py`, `TEMPLATES` `context_processors` | Template globals and custom tags | Variables every template gets implicitly (`request`, `user`, `messages`, `csrf_token`), and what each custom tag does |
| `mark_safe\|format_html\|SafeString\|autoescape off`, plus the `safe` filter in templates | Escaping exceptions | Every place HTML is trusted (Iron Law 12) |
| `forms.py` → `ModelForm\|def clean_\w+\|def clean\(` | Validation and normalization | Field cleaning, cross-field rules, the error wording users see |
| `admin.py` → `admin.site.register\|ModelAdmin\|actions =` | Staff back office | Which staff workflows depend on Django admin. Port them last |
| `transaction.atomic\|on_commit\(\|select_for_update\(` | Transaction boundaries | Atomic units, row locks, after-commit side effects |
| `celery.py`, `tasks.py` → `@shared_task\|@app.task\|autoretry_for\|max_retries\|acks_late\|rate_limit\|time_limit`; `CELERY_*`/`task_*` settings | Job semantics | Ack mode, retries, visibility timeout, rate and time limits, routing per task, and the ETA/countdown tasks in flight |
| `beat_schedule\|CELERY_BEAT_SCHEDULE`, `django_celery_beat_*` tables | Cron | Static or admin-editable schedules, schedule time zone |
| `consumers.py`, `routing.py`, `CHANNEL_LAYERS` → `group_send\|group_add\|AsyncWebsocketConsumer\|AuthMiddlewareStack` | Realtime | Client message shapes, group names, socket auth |
| `serializers.py` → `SerializerMethodField\|read_only_fields\|write_only\|def validate_\w*\|to_representation` | API representation and input validation | Field names, computed and write-only fields, per-field validation |
| `REST_FRAMEWORK` settings; `views.py` → `permission_classes\|authentication_classes\|throttle_classes\|pagination_class` | API cross-cutting policy | Auth schemes, throttle rates (kept in the cache backend), page size, `COERCE_DECIMAL_TO_STRING`, datetime format |
| `ContentType\|GenericForeignKey\|GenericRelation\|django_content_type` | Polymorphic references | Which tables point at `content_type_id` + `object_id`. Content-type ids differ between databases |
| `locale/**/LC_MESSAGES/*.po`, `gettext\(\|pgettext\(\|ngettext\(\|{% trans\|{% blocktrans`, `LocaleMiddleware` | i18n | Domains (`django`, `djangojs`), python-format placeholders, the language cookie and URL prefixes |
| `migrations/*.py` → `RunPython\|RunSQL` | Data migrations | Business logic and SQL that ran once, and may need to run again for new tenants |
| `gunicorn.conf.py`, `uwsgi.ini`, `asgi.py`, `Procfile`, `supervisord.conf` → `workers\|threads\|max_requests\|preload_app` | Process topology | Why each process exists. `max_requests` recycling hints at memory leaks |
| Flask `before_request\|g\.\|Blueprint\(`; FastAPI `Depends\(\|BackgroundTasks\|lifespan\|response_model=` | Request hooks, context locals, DI, after-response work | What runs per request, what each handler needs, which work runs in-process after the response |

## Mechanism map

| Legacy mechanism | Usual purpose (why) | Reason tags | Default verdict → Elixir way | Literal-translation trap | Cutover / compat note |
|---|---|---|---|---|---|
| `urls.py` `path`/`re_path` + `reverse()`, `{% url %}` | Map URLs to views by name | contract | MAP → `Phoenix.Router` + verified routes `~p` | Porting the regex router, or generating a name→path module | Phoenix matches `/posts` and `/posts/` alike (Plug drops empty segments). Django's `APPEND_SLASH` 301s and slash-terminated links are a client and SEO contract. `re_path` constraints become plug or changeset validation. First-match shadowing (a route hidden behind an earlier pattern) is a `defect` unless a consumer is named |
| `MIDDLEWARE` list | Cross-cutting request processing | business (some platform) | MAP → Endpoint plugs + router pipelines. DELETE WhiteNoise (→ `Plug.Static`) and runtime-only entries | Replicating the order one-to-one | Port the behavior-bearing entries: security headers, locale, CORS, auth |
| `ATOMIC_REQUESTS = True` | Roll back every write of a failing view | historical (convenience) | REPLACE → `Repo.transact/2` around each context operation | A plug that wraps every action in a transaction and holds the connection through rendering and HTTP calls | List the multi-write views that rely on rollback-on-exception and give each an explicit transaction |
| FBVs, CBVs + mixins, `@login_required`, `LoginRequiredMixin` | Reuse pre-view logic | business | MAP → controllers + function plugs, LiveView `on_mount` | Emulating CBV inheritance with `use` macros | Load objects through the scope: `get_object_or_404` becomes `Blog.get_post!(scope, id)` |
| Forms, `ModelForm`, `clean_*` | Validate and normalize input | business | MAP → a changeset or `embedded_schema` + `to_form/1` | Porting the form class hierarchy | Error wording is user-visible. Record whether you preserve or change it |
| Templates/Jinja2, `{% extends %}`, tags and filters, context processors | Compose HTML with implicit globals | business | MAP → HEEx function components, `<Layouts.app>`, explicit assigns. The `messages` processor becomes `put_flash/3` | String-rendered layouts. A helpers god-module | `\|safe` and `mark_safe` become a `raw/1` audit (Iron Law 12) |
| `models.Model` + Manager/QuerySet | ORM entity + query API | business | MAP → an Ecto schema (`schema "blog_post"`) + context query functions. `db_column=` becomes `field :x, source: :legacy_col`; M2M tables map with `join_through: "blog_post_tags"` | `Post.objects.filter` wrapper modules | Set `@primary_key` per table. `DEFAULT_AUTO_FIELD` decides int or bigint |
| `Meta.ordering` | A default order everywhere | historical (sometimes business) | MAP → an explicit `order_by` in each context query | Dropping it silently, so lists come back in arbitrary order | Find the templates and APIs that assume the order first |
| Custom default managers | Hide rows by default | business | MAP → explicit query functions, with `Repo.prepare_query/3` enforcing tenancy or soft delete | Re-creating the hidden filter as magic | In Django, related-object access uses `_base_manager`, which ignores the filter, so related loads behave differently |
| Signals and `save()` overrides | Hook side effects into persistence | business (often historical) | MAP → an explicit context pipeline: changeset → `Repo.transact` → `Oban.insert` in the same transaction → PubSub after commit | A signal-bus GenServer. A generic `after_save` registry | Django's bulk paths skip signals. Do not add effects to them by accident |
| `on_delete=CASCADE\|SET_NULL\|PROTECT` | Referential behavior | platform (emulated in Python) | MAP → `Ecto.Multi` deletes now, and DB `ON DELETE` actions in an Ecto migration after cutover | Assuming the DB cascades | An Ecto `Repo.delete` on a parent fails at commit (deferred FK) or leaves `SET_NULL` children dangling |
| `auto_now`, `auto_now_add`, callable `default=` | Values set in Python | platform | MAP → `timestamps(inserted_at: :created, updated_at: :modified)`, `autogenerate:`, changeset defaults | Expecting DB defaults that do not exist | Column names are app-specific. Other writers (scripts, Celery) must set them too |
| `CharField(blank=True)` storing `""` | Avoid two empty states | contract | MAP → `cast(attrs, fields, empty_values: [])` for those fields, or `field :x, :string, default: ""` | Ecto's default `empty_values` turns `""` and whitespace into nil: NOT NULL violations, or NULLs where queries test `= ''` | Test round trips with empty and whitespace-only input |
| `unique=True`, `UniqueConstraint`, `unique_together` | Integrity | business | MAP → `unique_constraint/3` (Django already created the DB indexes). `unsafe_validate_unique/4` for form feedback | A SELECT check before each insert | Django's constraint names differ from Ecto's guess, so pass `name:` |
| Multi-table inheritance, proxy and abstract models | Model hierarchies | historical (sometimes business) | MAP → MTI: two schemas, the child with `@primary_key {:post_ptr_id, :id, autogenerate: false}` + `belongs_to`. Proxy: a query function. Abstract: fields written out per schema | Emulating inheritance with macros | An MTI insert writes two rows, so use one `Ecto.Multi` |
| contenttypes `GenericForeignKey` | One FK pointing at many tables | contract | MAP → plain `content_type_id` + `object_id`. Resolve type ids from `django_content_type` at boot and cache them in `:persistent_term` | Hard-coding content-type ids, or an `Ecto.Enum` over them | The ids differ per database and environment. Normalize to per-parent FKs after cutover |
| `JSONField`, `ArrayField`, `HStoreField` | Flexible columns | business | MAP → `:map`/`embeds_*`, `{:array, type}`, and `:map` for hstore (a Postgrex extension) | Decoding JSON by hand | Keys arrive as strings in whatever case Python wrote |
| `transaction.atomic`, `select_for_update`, `on_commit` | Atomicity, row locks, after-commit work | business (reliability, platform for `on_commit`) | MAP → `Repo.transact/2` and `lock("FOR UPDATE")`. DELETE `on_commit`: `Oban.insert` inside the transaction replaces it | Spawning a Task inside the transaction to "run after commit" | — |
| `django_migrations` + `RunPython` | Versioned DDL and data migrations | contract | KEEP the table untouched. MAP new DDL to Ecto with an explicit `migration_source` | Porting the historical migrations | No table-name collision with Ecto, but only one system owns DDL at a time. Re-run `RunPython` logic only if new tenants need it |
| `django.contrib.auth`, `PASSWORD_HASHERS`, reset tokens | Users, passwords, staff flags, stateless reset links | business | REPLACE → `mix phx.gen.auth` mapped onto `auth_user` (or `AUTH_USER_MODEL`). `pbkdf2_sha256$` hashes verify and are written with `:crypto.pbkdf2_hmac/5` (data-compat.md), never `pbkdf2_elixir`. Rehash on login | Porting Django's hasher framework. Re-deriving `PasswordResetTokenGenerator` hashes | `bcrypt_sha256$` is bcrypt over the hex SHA-256 of the password, and `argon2$` prefixes a PHC string [U]: strip and adapt before verifying. Reset links in flight break at cutover |
| Sessions (`django_session`, signed JSON) | Per-user state across share-nothing workers | platform | REPLACE → `phx.gen.auth` sessions. SHIM → a handoff endpoint, or a one-way read of `django_session` | Writing Django session rows from Phoenix | Check `expire_date`, and try `SECRET_KEY_FALLBACKS` for rotated keys. Treat Pickle sessions (serializer removed in Django 5.0 [U]) as logged out |
| Permissions, groups, django-guardian, rules | Authorization | business | MAP → context functions that take `%Scope{}`. `Bodyguard` or `LetMe` | `has_perm` string lookups through a global registry | Keep `auth_permission`, `auth_group` and the object-permission tables as a read model first |
| CSRF (`csrftoken` cookie, `X-CSRFToken` header) | Forgery protection | business | MAP → `Plug.CSRFProtection` + a `get_csrf_token()` meta tag | Reading Django's cookie token in Phoenix | JS that reads the `csrftoken` cookie (axios, htmx config) must switch to the meta tag |
| i18n `.po`, `LocaleMiddleware`, `django_language` cookie | Translate the UI and negotiate the locale | business | MAP → `Gettext` reusing the `.po` files + a locale plug. `ex_cldr` for formatting | DB-backed runtime translations (Kanta: KB verdict skip) | Convert `%(name)s` to `%{name}`. Domain `django` becomes `default`. Iron Law 25 |
| Cache framework, `cache_page`, `{% cache %}` | A shared cache for processes that share nothing | platform | REPLACE → ETS or `Cachex`. DELETE page and fragment caching after measuring | Porting `LocMemCache` behavior as a GenServer. Caching per-user HTML in a shared store (Campfire leaked CSRF tokens that way) | `LocMemCache` was per worker, so invalidation was already inconsistent. Redis entries are pickled: never read them from Elixir |
| Celery tasks (`@shared_task`) + broker | Work beyond the request; the GIL; a worker fleet | reliability, platform | MAP → an Oban worker enqueued in the same transaction, with string-keyed IDs in args | A Celery-protocol consumer on Redix or AMQP (the Campfire Resque trap in Python form). An in-memory queue (Campfire PR #10: "The queue is not durable") | Drain per task. **Oban for Python** (PyPI `oban` 0.6.6, pre-1.0) shares the schema, so Django can insert into `oban_jobs` during coexistence |
| Celery ack and retry semantics | The delivery guarantee per task | business | MAP → Oban at-least-once delivery with `max_attempts`, `backoff/1`, `timeout/1` and a queue `limit` | Keeping at-most-once delivery by moving "early ack" tasks to a `Task` | Celery defaults: early ack (`acks_late=False`, so a crash loses the task), `max_retries=3`, `default_retry_delay=180` s, and retries only through `retry()` or `autoretry_for`. Visibility-timeout redelivery duplicates long tasks. Every task must become idempotent (Iron Law 7) |
| Celery canvas (chain, group, chord) + result backend | Fan-out/fan-in, polling for results | reliability, platform | REPLACE → enqueue the next step from `perform/1`, `Task.async_stream` inside a job, Oban Pro Workflow (paid) only if needed. DELETE the result backend in favor of PubSub progress to a LiveView | Chord counters in ETS with polling | Polling endpoints become push |
| Celery beat, django-celery-beat | A scheduler outside the app | reliability, platform (business if admin-editable) | MAP → Oban cron (top-level `cron:` key, `Oban.Cron`, Oban 2.24+). Admin-editable schedules become a small table read by a cron job (or Oban Pro DynamicCron [U]) | A `Process.send_after` loop | Disable each beat entry in the same deploy that enables its Oban entry |
| Channels consumers + `channels_redis` + Daphne | Sockets in an ASGI side process; cross-process groups | platform | REPLACE → `Phoenix.Channel` or LiveView over `Phoenix.PubSub`. SHIM → a raw WebSocket adapter (`websock_adapter`) that speaks the legacy JSON. DELETE `channels_redis` | A Channels-compatible group layer on Redis | Group names and message shapes are the contract for existing clients |
| DRF serializers | Validate input and shape output | contract | MAP → JSON modules with explicit fields + an `embedded_schema` changeset per endpoint | A serializer class hierarchy. `@derive Jason.Encoder` on schemas | Freeze the output with golden files: decimals as strings (`COERCE_DECIMAL_TO_STRING` is on by default), the datetime format, null versus missing |
| DRF ViewSets + routers | CRUD endpoints by convention | contract | MAP → `resources` + controllers | A generic ViewSet macro | Route names (`-list`, `-detail`), trailing slashes, `?format=`, OPTIONS metadata. DELETE the browsable API |
| DRF authentication, permissions, throttles | API identity and per-endpoint policy | business | MAP → hashed API token rows (the UserToken pattern), scope functions, `Hammer`. `joken` only for JWT interop | Storing tokens in plaintext forever. A GenServer limiter | `authtoken_token.key` is plaintext: look it up once, then store a hash. Keep the `Authorization: Token <key>` scheme. Throttle counters lived in the Django cache, per process with `LocMemCache` |
| DRF pagination, filtering, error envelopes | Index endpoints and errors | contract | MAP → `Flop`, with the envelope built in the JSON module | Re-implementing django-filter's lookup language | `{"count","next","previous","results"}`. Validation errors are 400 with `{"field": [...]}`, where Phoenix generators use 422 |
| drf-spectacular, Graphene/Strawberry | OpenAPI for SDKs; a GraphQL API | contract | MAP → `open_api_spex`; `absinthe` + `dataloader` | A hand-written spec that drifts. A Repo call per GraphQL field (N+1) | Diff the legacy OpenAPI spec and the GraphQL introspection schema against the new ones in CI |
| Django admin | Staff CRUD | business | KEEP on the legacy app until last, then `backpex` or `phx.gen.live` pages | A reflection-driven admin with no authorization review | Admin writes to the shared DB follow the per-table ownership rules |
| `FileField` + django-storages; `send_mail`, anymail | Files and email | business | MAP → LiveView uploads + `ExAws.S3`; `Swoosh` + an Oban worker | A provider SDK next to Swoosh | Stored names are relative to `MEDIA_ROOT`/`AWS_LOCATION`. Keep them |
| django-tenants (`search_path`) | Schema-per-tenant isolation | business | MAP → the `prefix:` option or `put_query_prefix`, `@schema_prefix "public"` for shared apps, migrations per prefix | `SET search_path` on pooled connections, which leaks to the next checkout | Keep the existing schema layout first |
| simple-history, reversion, django-waffle | Audit, feature flags | business | MAP → `carbonite` (it also captures legacy writes) or audit rows in the Multi; `FunWithFlags` | — | django-waffle is not Elixir's Waffle (uploads) |
| Gunicorn/uWSGI workers, `max_requests`, the ASGI/WSGI split | Concurrency around the GIL; recycling leaky workers | platform | DELETE → one release on BEAM schedulers | Tuning worker counts on the BEAM | `POOL_SIZE` is the remaining knob |
| Management commands, `settings.py`, django-environ | Ops scripts and config | business | MAP → release functions (`bin/app eval`) and `config/runtime.exs` | Mix tasks in production | Export `SECRET_KEY` only for the handoff, then remove it |
| Flask: blueprints, `before_request`, `g`/`current_app`, itsdangerous session cookie, Flask-Login | Route groups, request hooks, context locals, a signed session | platform (context locals), contract (cookie) | MAP → router scopes + pipelines and explicit assigns. REPLACE the session through a handoff | Recreating `g` in the process dictionary | The `session` cookie is signed, not encrypted (salt `cookie-session`, HMAC-SHA1 [U]) |
| SQLAlchemy session + Alembic | Unit of work, lazy loading, versioned DDL | business / contract | MAP → Ecto schemas + explicit `preload`. KEEP `alembic_version` and give Ecto its own `migration_source` | Emulating the Session identity map and autoflush | `lazy="select"` relationships hid N+1 queries. One DDL owner |
| FastAPI: Pydantic models, `Depends`, `response_model`, `BackgroundTasks`, uvicorn workers | Validation, DI, output filtering, after-response work, async I/O | business / reliability, platform | MAP → `embedded_schema` + changesets, plugs and explicit args, explicit JSON modules. `BackgroundTasks` → Oban if the work must survive a restart, else `Task.Supervisor`. DELETE the event-loop tuning | Mapping every `BackgroundTasks` call to Oban by reflex, or durable work to a Task | 422 `{"detail": [{"loc", "msg", "type", ...}]}` errors and `/openapi.json` are client contracts (`open_api_spex`) |

## Disappears on the BEAM (DELETE candidates)

- **The Celery worker fleet and its supervisord or systemd units.** Delete once every task type is drained, including ETA and countdown tasks, and
  its producers are switched off or enqueue through Oban for Python.
- **Redis or RabbitMQ as this app's broker.** Delete when nothing else consumes it. A RabbitMQ exchange used for cross-service events is an integration (see below).
- **The Celery result backend and polling endpoints.** Delete when clients move to push (LiveView, Channels), or when a polling endpoint reads a DB row or Oban job state.
- **The celery beat process.** Delete once Oban Cron runs the entries and any admin-editable schedules live in a table.
- **`transaction.on_commit` enqueue hacks.** Always delete once enqueue is transactional.
- **Daphne/uvicorn side processes and `channels_redis`.** Delete when clients have moved or the raw-WebSocket shim runs inside the release, and every node is in one cluster.
- **Gunicorn/uWSGI tuning, `max_requests`, `preload_app`, gevent/eventlet monkeypatching, `sync_to_async` bridges.** Always delete.
- **`LocMemCache` and Redis as a cache server.** Delete on a single node (ETS, Cachex) or a cluster (per-node cache + PubSub invalidation). Do not
  delete while Django still writes the cached tables unless those writes invalidate too.
- **Thread locals (django-crum; Flask `g`, `request`, `current_app`).** Always delete in favor of an explicit scope.
- **nplusone and debug-toolbar N+1 hunting.** Always delete: an unloaded association raises. Still review Repo calls inside loops.
- **`ATOMIC_REQUESTS` as a mechanism.** Delete it, but only after its rollback behavior is restated as an explicit transaction per operation.
- **Polling-table job queues (`select_for_update(skip_locked=True)` loops) and django-redis locks.** Replace the queues with Oban and the
  locks with advisory or row locks; Oban `unique:` only stops duplicate inserts.
  `select_for_update` that is business locking stays.
- **Pickle-serialized cache and session entries.** Always delete. Never decode pickle in Elixir.
- **FastAPI `BackgroundTasks` and Flask threads for after-response work.** Delete in favor of `Task.Supervisor` (non-durable) or Oban (durable).

## Keep or shim (with conditions)

- **Django admin (KEEP on legacy).** It keeps running against the shared DB until last, with explicit per-table write ownership. It is the
  highest-value, lowest-risk thing to leave in place.
- **Session handoff (SHIM).** Prefer an internal legacy endpoint that returns a short-lived signed token. Otherwise read `django_session` one way:
  verify the signature (SHA-256, salt `django.contrib.sessions.SessionStore`), check `expire_date`, read `_auth_user_id`, and check
  `_auth_user_hash` against the password hash [U]. Sunset after `SESSION_COOKIE_AGE`.
- **Oban for Python producers (SHIM).** Unported Django views enqueue straight into `oban_jobs`. Pin the pre-1.0 version. Sunset each producer when its view is ported.
- **Python-only work (KEEP).** ML, pandas or PDF libraries without a BEAM equivalent stay in a Python worker behind a queue contract. Oban for
  Python can consume `oban_jobs` too. Port it only when the dependency goes away.
- **Raw-WebSocket adapter (SHIM).** For native or third-party clients that speak the Channels consumer JSON: a `websock_adapter` handler over
  `Phoenix.PubSub` that authorizes each message through a scope function. Sunset when those clients ship `phoenix.js` or move to LiveView.
- **RabbitMQ for cross-service events (KEEP as an integration).** Consume it with `broadway_rabbitmq` and enqueue Oban jobs for durable work. Do not use it as this app's job queue.
- **The DRF API contract (KEEP).** Status codes (400, not 422), decimal strings, trailing slashes and pagination envelopes stay byte-compatible
  until every consumer has migrated, even where Phoenix conventions differ.
- **Cross-runtime invalidation during coexistence (SHIM).** Django signals never reach Elixir. Use a DB trigger with `pg_notify`, consumed by
  `Postgrex.Notifications`, or carbonite's transaction log. Remove it once Elixir owns the table's writes.
- **`django_migrations`, `django_content_type`, `auth_permission` (KEEP).** They stay while Django runs. Elixir reads content types and never writes them.

## Questions the architect must ask

1. Which `SESSION_ENGINE`, `SESSION_SERIALIZER`, Django version and `SECRET_KEY_FALLBACKS` are in use? They pick the handoff and decide which sessions survive.
2. Is `ATOMIC_REQUESTS` on, and which views write more than one row? Their rollback semantics must become explicit.
3. Celery: what are `task_acks_late`, the broker and the visibility timeout? Which tasks are idempotent, what ETA/countdown backlog exists, and who
   reads results? Delivery changes from at-most-once to at-least-once under Oban.
4. Can staff edit beat schedules (django-celery-beat)? Then the schedule needs a table, not static cron config.
5. Who consumes the API (mobile apps, SDKs, partners), and is the DRF contract frozen with golden files? Decimals, 400 versus 422, slashes and envelopes all depend on it.
6. Which models use `GenericForeignKey`, multi-table inheritance or proxies? That sets the mapping and the normalization plan.
7. Which `on_delete` rules exist, and does any non-Django writer touch those tables? The cascades exist only in Python.
8. Which CharFields store `""`, and which columns rely on `auto_now` or Python defaults? Ecto `empty_values` and defaults must match.
9. What does staff use Django admin for, and can it stay until last? It is the largest low-risk KEEP.
10. What are `USE_TZ` and `TIME_ZONE`, and are stored datetimes aware or local? That picks the Ecto type and any shift on read (with `tz`).
11. Are Channels clients only browsers, or native apps with a custom JSON protocol? That decides between the raw-WebSocket shim and a direct move.
12. Which work depends on Python-only libraries? KEEP it behind a queue contract rather than porting it.
13. Tenancy: django-tenants schemas or row-level filtering? That sets the Ecto prefix strategy and per-schema migrations.
14. Flask/FastAPI: which `BackgroundTasks` or threads must survive a restart, and who consumes `/openapi.json`? It splits Oban from Task and fixes the spec contract.

## Libraries (versions checked by the plugin author on hex.pm, 2026-10-09; re-check before pinning)

| Need | Package | Version | Notes |
|---|---|---|---|
| Web, router, Channels | `phoenix` | 1.8.15 | Scopes, `phx.gen.auth`, verified routes, `Phoenix.Token` |
| Server UI | `phoenix_live_view` | 1.2.12 | Replaces Channels consumers for browser UI |
| Fan-out, presence | `phoenix_pubsub` | 2.4.1 | Replaces `channels_redis` |
| Data | `ecto` / `ecto_sql` | 3.14.2 / 3.14.0 | `Repo.transact/2`, `prepare_query/3`, query prefixes |
| Adapters | `postgrex` / `myxql` | 0.22.4 / 0.9.0 | `Postgrex.Notifications` for cross-runtime invalidation |
| Jobs, cron | `oban` / `oban_web` / `oban_met` | 2.24.1 / 2.13.1 / 1.3.2 | Oban for Python (PyPI 0.6.6) shares the schema |
| Password hashes | `:crypto.pbkdf2_hmac/5` / `bcrypt_elixir` / `argon2_elixir` | OTP / 3.3.2 / 4.1.3 | PBKDF2 through `:crypto`, a dirty NIF. `pbkdf2_elixir` 2.3.1 runs each HMAC round in Elixir on the normal schedulers: concurrent hashes at Django's 1,000,000 iterations starve the DB pool |
| Handoff, JWT interop | `joken` | 2.7.0 | Short-lived HS256 handoff; simplejwt interop |
| Authorization | `bodyguard` / `let_me` | 2.4.3 / 3.0.4 | Scope-taking policies / declarative rules |
| Rate limiting | `hammer` | 7.5.0 | Replaces DRF throttles and django-ratelimit |
| Cache | `cachex` | 4.1.1 | Replaces `LocMemCache` and Redis caches |
| i18n | `gettext` / `ex_cldr` | 1.0.2 / 2.47.5 | Reuse the `.po` files. Kanta: KB verdict skip |
| Time zones | `tz` | 0.28.4 | Local-time (`USE_TZ = False`) data |
| Email | `swoosh` | 1.29.0 | Native provider adapters, not anymail |
| Storage | `ex_aws` / `ex_aws_s3` | 2.7.0 / 2.5.9 | KB gotchas: `encryption:` option, req 0.7 `get_to_post` |
| JSON | `jason` | 1.4.5 | Or Elixir 1.18+ `JSON` |
| Filtering, pagination | `flop` / `flop_phoenix` | 0.29.0 / 0.27.0 | Build the DRF envelope in the JSON module |
| OpenAPI | `open_api_spex` | 3.22.4 | Replaces drf-spectacular and FastAPI's generated spec |
| GraphQL | `absinthe` / `dataloader` | 1.12.0 / 2.0.2 | `dataloader` is stable (2024-12) |
| Admin | `backpex` | 0.22.0 | After Django admin retires |
| Raw WebSocket SHIM | `websock_adapter` | 0.6.0 | Legacy Channels JSON protocol |
| Cross-service AMQP | `broadway_rabbitmq` | 0.8.2 | Stable (2024-11). Integration only, not the job queue |
| Strangler proxy | `reverse_proxy_plug` | 3.0.4 | Forward unported paths to Django |
| Audit | `carbonite` | 0.17.0 | Trigger-based. Captures Django writes |
| Feature flags | `fun_with_flags` | 1.13.0 | Replaces django-waffle |
