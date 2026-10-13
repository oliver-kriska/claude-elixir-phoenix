# Runtime — Conduit (django-realworld)

Source: `testbeds/django-realworld` @ `29c9d42831fa0cfc5a4aa7561f674396eacf20a2` · Deploy model: **none declared**. There is no Procfile, Dockerfile, compose file, gunicorn/uWSGI config, systemd unit, PaaS manifest or CI deploy job. README gives local-dev setup only (pyenv, Python 3.5.2). Settings are development-only: `DEBUG = True`, `ALLOWED_HOSTS = []`, and `SECRET_KEY` is hardcoded in `conduit/settings.py:23`. The de facto topology is one `manage.py runserver` process against a local SQLite file.

App shape: `http-api` (confirmed). It is a stateless JSON API (DRF) with JWT bearer auth. The only server-rendered surface is Django admin at `/admin/`.

## Process Topology

| Process | Command | Concurrency knob | Health check | Purpose | BEAM disposition |
|---------|---------|------------------|--------------|---------|------------------|
| R-01 web (dev server) | `python manage.py runserver` (inferred: README + `manage.py`; no other launcher exists) | none. runserver is threaded by default (one thread per request) | none | serves `/api/*` JSON, `/admin/`, and `/static/` (admin assets, served by `staticfiles` only while DEBUG=True) | **REPLACE**: one Phoenix release (`bin/conduit start`), Bandit endpoint. The only remaining knob is the Repo pool, which is 1 writer when the target stays on SQLite (see R-10) |
| R-02 WSGI entry | `conduit/wsgi.py` exposes `application`. No WSGI server is configured | n/a | n/a | the hook a production server (gunicorn/uWSGI) would use. Nothing uses it in the repo | **DELETE** (platform). Its job is covered by the Phoenix Endpoint |
| R-03 management CLI | `python manage.py <cmd>` (+ `django_extensions` commands such as `shell_plus`, `show_urls`) | n/a | n/a | migrations, superuser creation, dev shell | **MAP**: release `eval` functions (`Conduit.Release.migrate/0`, etc.) and `bin/conduit remote`. See Operator Duties |

There is no worker, scheduler, websocket, proxy or sidecar process.

## Datastores by Role

| ID | Component → role | Stores | Loss acceptable? | Consumers | Tags | Candidate verdict → target |
|----|------------------|--------|------------------|-----------|------|----------------------------|
| R-10 | SQLite `BASE_DIR/db.sqlite3` → system of record (settings.py:83-88) | users (with password hashes), profiles, follows, favorites, articles, tags, comments, plus Django tables (`django_session`, `django_admin_log`, `auth_group`, `auth_permission`, `django_content_type`, `django_migrations`) | **No.** It is the only durable state | the app only. No other service reads it | business, reliability, `data` contract | **KEEP SQLite or REPLACE with Postgres: UNDECIDED (Q1).** If SQLite stays, follow `sqlite-on-beam.md`: one writer Repo (`pool_size: 1`, `default_transaction_mode: :immediate`) and WAL. Legacy uses Django defaults (rollback journal, not WAL; 5 s `timeout`; autocommit with no `ATOMIC_REQUESTS`). Any change to these is a deliberate choice that must be written down. The file is gitignored (`.gitignore: db.sqlite3`), and nothing shows that a production dataset exists (Q2) |
| R-11 | SQLite → Django session store (`django.contrib.sessions`, default DB engine) | `django_session` rows for **admin logins only**. The API does not use sessions (JWT only) | Yes. Admin users log in again | Django admin | platform | **DELETE** together with Django admin (R-41). There is no session handoff because no API client holds a session cookie |
| R-12 | SQLite → schema-version ledger (`django_migrations`) | applied-migration names (10 migration files, 3 apps + Django contrib) | n/a | `manage.py migrate` | platform, operational | **REPLACE**: Ecto `schema_migrations`. If the existing DB is imported, give Ecto its own `migration_source` and baseline it on the legacy schema (data-compat) |
| R-13 | In-process memory → cache | **none configured.** There is no `CACHES` setting, so Django uses its default `LocMemCache`, but no code calls the cache (probe: no `cache` hits outside migrations). DRF throttling is not configured | Yes | none | historical | **DELETE**. Nothing to port. Add ETS/Cachex only if a measured need appears |

There is no Redis, broker, queue, pub/sub, search engine or object store. No component carries durable work besides R-10.

## Scheduled and Background Work

None. No crontab, `beat_schedule`, management commands, threads, `setInterval`-style loops or async tasks were found. Two synchronous model signals run **in-request**. They are listed here only because a rewrite could wrongly move them to the background:

| ID | Job | Schedule | Idempotent? | Overlap guard | External effects | Candidate |
|----|-----|----------|-------------|---------------|------------------|-----------|
| R-20 | `post_save(User)` → create Profile (`authentication/signals.py`) | inline on user insert | guarded by `created` | none. It is **not atomic** with the user insert (autocommit, no `transaction.atomic`) | none | **MAP** as an explicit `Ecto.Multi` step in `Accounts.register_user/1`. Making it atomic is a *strengthening*. Belongs to the mechanism ledger |
| R-21 | `pre_save(Article)` → slug = slugify(title) + `-` + 6 random `[a-z0-9]` (`articles/signals.py`, `core/utils.py`) | inline on article save when the slug is empty | no (random suffix). Uniqueness relies only on the DB unique index | none | none | **MAP** to changeset logic, with retry on a unique-constraint violation (strengthening). Belongs to the mechanism ledger |

## Storage, Search, Mail, Push, Observability

- **File storage:** none. `Profile.image` is a `URLField` that stores an external URL string. The serializer falls back to the hardcoded default `https://static.productionready.io/images/smiley-cyrus.jpg` (profiles/serializers.py:21). This is a `wire` contract value, not storage. Hand it to contract-surveyor.
- **Static files:** `STATIC_URL='/static/'`, used only by admin assets. There is no `STATIC_ROOT` and no collectstatic or WhiteNoise. **DELETE** together with admin.
- **Search:** none. The article list filters by exact `author`, `tag` and `favorited` (ORM `filter`). There is no FTS.
- **Mail / push:** none. `get_full_name`/`get_short_name` exist only to satisfy Django's user contract.
- **Logging / metrics / errors / tracing:** none configured (no `LOGGING`, no Sentry). With DEBUG=True, unhandled 500s return Django's **HTML debug page with settings and traceback**. That is a `defect` (information disclosure), not a contract. Target: Phoenix `Logger` + `:telemetry`, and JSON 500s through the FallbackController. The error-tracking choice is open (Q6).
- **CORS (R-30):** `django-cors-middleware==1.3.1`, `CORS_ORIGIN_WHITELIST = ('0.0.0.0:4000', 'localhost:4000')`. These are bare host:port entries in the old 1.x netloc format, with no scheme. `CORS_ALLOW_CREDENTIALS` keeps its default `False`, and allowed headers keep the package defaults (these include `authorization`). The middleware is placed before `CommonMiddleware`. Tags: `contract` (operational/wire): a RealWorld frontend dev server on port 4000 depends on it. **MAP** → `CORSPlug` (or `Corsica`) in the `:api` pipeline. Origins become `http://localhost:4000` and `http://0.0.0.0:4000` (scheme required; https?, Q4) and come from runtime config. Preflight `OPTIONS` must pass before auth.
- **Security middleware (R-31):** `SecurityMiddleware` adds nothing with the default settings (no HSTS or SSL redirect). `XFrameOptionsMiddleware` adds `X-Frame-Options: SAMEORIGIN` to every response. `CsrfViewMiddleware` is active, but DRF `APIView` is csrf-exempt and the custom JWT auth never enforces CSRF, so CSRF only protects admin forms. `CommonMiddleware` with the default `APPEND_SLASH` redirects slashless non-API URLs. Classify all of these as **incidental**. Target: Phoenix `:put_secure_browser_headers` (a superset) in the browser pipeline only. The API pipeline needs no CSRF. Trailing-slash routing is a wire question for contract-surveyor.
- **Host validation:** `ALLOWED_HOSTS=[]` with DEBUG=True allows only localhost, 127.0.0.1 and [::1]. Target: Endpoint `url`/`check_origin` from `PHX_HOST`.

## Auth Crypto in Force (operational, feeds data-compat)

- **R-32 JWT signing key = Django `SECRET_KEY`**, hardcoded in source. Tokens are HS256 with `{id, exp}`, valid for 60 days (`authentication/models.py:128-139`). Verification calls `jwt.decode(token, SECRET_KEY)` with no `algorithms=` pin (`backends.py:78`) under PyJWT 1.4.2, so HS384/HS512 tokens signed with the same key would also verify. Treat that as a `defect`: the target pins HS256. `exp` is computed from naive local `datetime.now()` with `strftime('%s')`, which works on glibc and is not portable. Target: `joken` HS256 with a key from `JWT_SECRET`/`SECRET_KEY_BASE` env. **Whether issued tokens must survive cutover is UNDECIDED (Q3).** If they must, the Elixir app needs the same leaked key. Rotating the key logs out every client, and those tokens expire within 60 days anyway.
- **R-33 Password hashes:** no `PASSWORD_HASHERS` override, so Django 1.10 defaults apply: `pbkdf2_sha256$<iter>$<salt>$<hash>`. Target: `Pbkdf2.verify_pass/2` with rehash on login (data-compat). `AUTH_PASSWORD_VALIDATORS` lists four validators, but they only run through `validate_password`/admin. The probe found no call to them in the API serializers. Confirm with mechanism-archaeologist.
- **R-34 Auth header scheme:** `Authorization: Token <jwt>`, case-insensitive prefix. Malformed headers count as anonymous rather than raising an error. This is a `wire` contract (charter) for contract-surveyor.

## Operator Duties

| Duty | Today (command/anchor) | Must exist in the release as |
|------|------------------------|------------------------------|
| Schema migration | `python manage.py migrate` (manual, README implies) | `bin/conduit eval "Conduit.Release.migrate()"`, run at deploy |
| Create admin/staff user | `python manage.py createsuperuser` → `UserManager.create_superuser` (models.py:38) | UNDECIDED: needed only if a staff back office survives (Q5). Otherwise `Conduit.Release.create_user/…` for seeding |
| Back office CRUD | Django admin at `/admin/`. **No `admin.py` registers any model**, so only `auth.Group` appears (the custom User is not registered) | **DELETE** (R-41): nearly no capability. Confirm nobody uses it (Q5) |
| Dev shell / introspection | `manage.py shell`, `django_extensions` (`shell_plus`, `show_urls`) | `iex -S mix`, `bin/conduit remote`, `mix phx.routes` |
| Backup / restore | none. The DB is a single local file | if SQLite: `VACUUM INTO` / backup API (never `cp` of a live file). If Postgres: `pg_dump`. A new duty, record it in the ADR |
| Secret rotation | impossible without a code change (key hardcoded) | `SECRET_KEY_BASE` + JWT key from env in `config/runtime.exs` |
| Data import at cutover | n/a | UNDECIDED (Q2): an import from `db.sqlite3` is needed only if a production dataset exists |

## Environment Contract

| Env var | Read at | Purpose | Keep name? |
|---------|---------|---------|------------|
| `DJANGO_SETTINGS_MODULE` | `manage.py:6`, `conduit/wsgi.py:14` (`setdefault` → `conduit.settings`) | settings module selection | **No**. It is Django-specific. DELETE |
| *(none other)* | settings.py reads no env vars. `SECRET_KEY`, `DEBUG`, DB path and CORS origins are hardcoded | — | Target introduces `DATABASE_PATH` or `DATABASE_URL`, `SECRET_KEY_BASE`, `JWT_SECRET` (or derive from SECRET_KEY_BASE), `PHX_HOST`, `PORT`, `CORS_ORIGINS`. These are new names with no legacy consumer |

## BEAM Disposition Summary

| ID | Mechanism | Verdict |
|----|-----------|---------|
| R-01 | runserver web process | REPLACE → Phoenix release |
| R-02 | WSGI entry | DELETE |
| R-03 | manage.py CLI | MAP → release tasks |
| R-10 | SQLite system of record | UNDECIDED (KEEP SQLite vs Postgres), Q1 |
| R-11 | DB session store (admin only) | DELETE with admin |
| R-12 | `django_migrations` | REPLACE → Ecto migrations |
| R-13 | default LocMemCache (unused) | DELETE |
| R-20/21 | signals (inline) | MAP (mechanism ledger) |
| R-30 | CORS whitelist | MAP → CORSPlug, contract |
| R-31 | security/CSRF/clickjacking middleware | MAP (browser pipeline) / DELETE (API) |
| R-32 | JWT key = hardcoded SECRET_KEY | REPLACE (joken, env key). Token survival UNDECIDED, Q3 |
| R-33 | pbkdf2_sha256 hashes | MAP → pbkdf2_elixir |
| R-41 | Django admin + static assets | DELETE (pending Q5) |

## Questions

1. **Q1 (blocks R-10):** Does the target stay on SQLite (single-node, one writer) or move to Postgres? Nothing in the source makes SQLite a product contract, and with no deploy it looks like a dev default. Postgres is the conventional Phoenix default. The answer belongs in ADR-000.
2. **Q2:** Is there a production `db.sqlite3` (or another DB) to migrate, or does the rewrite start empty? This decides the data import and password-hash compatibility work.
3. **Q3:** Must JWTs issued by the legacy app stay valid after cutover? If yes, the key in the public repo must be reused. Recommendation: rotate it and accept that clients log in again (60-day tokens). That counts as a guarantee change and needs approval.
4. **Q4:** Which frontend origins must CORS allow in production? Legacy allows only `localhost:4000` and `0.0.0.0:4000` (dev).
5. **Q5:** Does anyone use `/admin/`? No models are registered there. Can it be dropped, together with sessions, CSRF, `createsuperuser`, `is_staff` and `is_superuser`? Note that `is_staff` and `is_superuser` remain columns in `authentication_user` (data contract).
6. **Q6:** What production observability is expected (error tracking, request logs, metrics)? Legacy has none.

## Coverage

- Files read: 15 source files (settings, urls, wsgi, manage.py, requirements, README, .gitignore, auth backend/models/signals, article signals, core utils/models, partial greps of views and serializers) plus inventory, charter, budget and KB excerpts. About 120 KB, within budget (100 files / 0.5 MB).
- Deploy files searched: none exist (no Procfile/Docker/compose/k8s/systemd/CI/fly/serverless).
- Not read in full: per-view serializers and migrations (owned by contract-surveyor and mechanism-archaeologist). Exact SQLite column types and datetime text format are left to data-compat.
- No budget frontier remains. Every process is typed.
