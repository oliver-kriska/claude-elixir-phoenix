# Architecture — Conduit (django-realworld → Phoenix)

Status: **proposed** (designed inside ADR-000, Status ASSUMED under `--auto`; nothing here is approved)
Date: 2026-10-09 · Source: `testbeds/django-realworld` @ 29c9d42831fa · Target: empty workspace (no Phoenix project yet)
Inputs: ADR-000, charter.md, analysis/{features,contracts,mechanisms,runtime}.md, consults/{ecto-schema-designer,security-analyzer}.md, kb/ (versions checked by the plugin author on hex.pm 2026-10-09).
Nothing was executed. No parity or speed claim is made anywhere in this document.

## 1. Overview

**Shape.** SPA + JSON API (app-shapes.md section 2; features.md "Shape"; runtime.md "http-api confirmed"). There is one deploy unit (R-01), no UI, no jobs, no realtime, no cache, and no second writer. The machine consumers are RealWorld frontends (C-10..C-31).

**Target.** One Phoenix 1.8 release serving JSON only (no LiveView, no HTML, no assets, no mailer), Ecto on the **legacy SQLite file kept as-is** through `ecto_sqlite3`, three domain contexts, and one web edge that owns the legacy wire format. Oban and `Phoenix.PubSub` are **not** added: no legacy mechanism needs durable background work or fan-out (runtime.md "Scheduled and Background Work: None"; R-20/R-21 are in-request and stay in-request). That is "framework by default, where it applies", not a deviation (ADR-001).

**Cutover.** Replacement in one maintenance window (ADR-000). Only one runtime writes at a time. Every client logs in once because the JWT key rotates (C-14).

**What changes against legacy** (all `pending` in divergences.md): the security fixes C-14, C-15, C-32, C-33, C-34 (ASSUMED in ADR-000), the incidental relaxations C-45..C-56, the env contract (C-44), and the recorded strengthenings (atomic writes, FK enforcement, WAL). Defects ADR-000 left UNDECIDED stay UNDECIDED here. Consult proposals that would decide them are listed in divergences.md as **proposed, not adopted**.

## 2. Context Map

Contexts follow invariants, not Django apps. The Django `profiles` app splits: the profile row belongs to the account invariant "every user has exactly one profile" (C-05), while the follow graph is its own invariant set. Favorites live with articles because their only observable effect is the article read model (`favorited`, `favoritesCount`, `?favorited=`).

| Context | Owned schemas (table) | Invariants enforced | Public functions (sketch) | Cross-context calls | Events / jobs |
|---------|-----------------------|---------------------|---------------------------|---------------------|---------------|
| `Conduit.Accounts` | `User` (`authentication_user`), `Profile` (`profiles_profile`) | unique username and email, case-sensitive (C-04); email domain lowercased on create only (M-14); password 8–128, no Django validators (C-27); exactly one profile per user, created atomically (C-05, strengthening); credential check with one message for unknown, inactive and wrong (C-13); Django-format PBKDF2 hashes verify (C-02); token `{id, exp}` HS256, 60 days, new key (C-11, C-14, C-15); `is_active` re-checked on every request (C-12) | `register_user(attrs)`, `authenticate(email, password)`, `update_user(scope, attrs)`, `get_scope_for_token(token)`, `issue_token(user)`, `get_profile_by_username(username)`, `create_operator_user(attrs)` (release) | none outbound | none |
| `Conduit.Social` | `Follow` (`profiles_profile_follows`) | directed edge from → to; pair unique; idempotent follow and unfollow (C-28); self-follow refusal (C-38: **UNDECIDED**, the artifact `pk ≤ 256` is never reproduced) | `follow(scope, username)`, `unfollow(scope, username)`, `following?(viewer_profile_id, profile_id)`, `following_ids(viewer_profile_id, profile_ids)`, `followed_profiles_query(profile_id)` | `Accounts.get_profile_by_username/1` | none |
| `Conduit.Articles` | `Article` (`articles_article`), `Tag` (`articles_tag`), `ArticleTag` (`articles_article_tags`), `Favorite` (`profiles_profile_favorites`), `Comment` (`articles_comment`) | slug unique, generated `slugify(title)-[a-z0-9]{6}` ≤255 only when empty, fixed on title edit, client-writable (C-06, C-29); tag `slug = lower(tag)`, oversize legacy values served (C-07); `tagList` replaces the set on update (C-29); author-only update (C-32, ASSUMED change); comment delete by its author, scoped to the URL's article (C-33, ASSUMED change); idempotent favorites (C-28); list order `-created_at, -updated_at` (M-12); limit/offset paging, default 20, no max (C-24); comments paged at 20 with `commentsCount` (C-23) | `list_articles(scope, params)`, `feed(scope, params)`, `get_article(scope, slug)`, `create_article(scope, attrs)`, `update_article(scope, slug, attrs)`, `favorite(scope, slug)`, `unfavorite(scope, slug)`, `list_comments(scope, slug, params)`, `add_comment(scope, slug, attrs)`, `delete_comment(scope, slug, id)`, `list_tags()` | `Social.followed_profiles_query/1` (feed), `Social.following_ids/2` (author cards), `Accounts` profile preload for authors | none |

Request scope: `%Conduit.Accounts.Scope{user, profile}` (Phoenix 1.8 scope style), or `nil` for anonymous. It is built once per request by the auth plug with one join (user + profile), replacing `request.user` and the lazy `request.user.profile` (M-39). Contexts receive `scope.profile.id` for authoring, following and favoriting, because `author_id` and the pair tables reference **profile** ids, not user ids (consult Q1). Controllers never compare ids.

The web edge `ConduitWeb` holds: router, controllers, per-resource JSON modules (`UserJSON`, `ProfileJSON`, `ArticleJSON`, `CommentJSON`, `TagJSON`), `ConduitWeb.LegacyErrors` (the C-16/C-26 envelope rules, one module), `ConduitWeb.FallbackController`, `ConduitWeb.Plugs.TokenAuth`, `ConduitWeb.Params` (wrapper extraction, strict integer parsing), and Corsica in the Endpoint.

## 3. Data Layer

### Repo topology (ADR-003, proposed, measurement-gated)

- `Conduit.Repo`: the writer. `pool_size: 1`, `default_transaction_mode: :immediate`, `journal_mode: :wal`, `synchronous: :full` (see below), `busy_timeout: 5_000` (matches Django's 5 s sqlite `timeout`, runtime.md R-10), `timeout: 15_000`.
- `Conduit.Repo.Read`: `read_only: true`, Exqlite `mode: :readonly`, `pool_size: min(schedulers_online, 8)`. `Conduit.Repo.reader/0` returns the writer inside a transaction (sqlite-on-beam rule 7). Tests point the reader at the writer.
- **Why two Repos is only proposed.** Legacy has no foreign writer at runtime (Replacement). The remaining foreign accessors are the operator's backup (`VACUUM INTO`) and the `sqlite3` CLI. Slice 0 measures busy errors, checkout queue time and write p95 for (a) writer + reader and (b) one Repo with `pool_size: 1` under the baseline workload. Choose (a) only if it wins or ties without busy errors; otherwise (b). The decision is recorded back into ADR-003.
- **WAL is a change** (legacy uses Django's default rollback journal). Readers stop blocking the writer, but `-wal`/`-shm` files appear next to `db.sqlite3`, and a plain `cp` of a live file is no longer a valid backup. Hence DV-22 and the new backup duty (ADR-012). `synchronous: :full` is chosen so that an acknowledged write survives power loss, because legacy (rollback journal, default `FULL`) gave that guarantee; `:normal` would be a silent durability downgrade.
- Log `SELECT sqlite_version()` at boot (rule 16).

### Legacy schema mapping (ADR-004, ADR-005)

| Schema | `schema` | Key mapping notes |
|--------|----------|-------------------|
| `Accounts.User` | `authentication_user` | `field :password_hash, :string, source: :password, redact: true`; `last_login` (LegacyDateTime, nullable, never written by the API); `is_superuser`, `is_staff`, `is_active` `:boolean` (0/1), written with legacy defaults (`false`, `false`, `true`) on create (C-55); `has_one :profile` |
| `Accounts.Profile` | `profiles_profile` | `belongs_to :user`; `bio`, `image` NOT NULL with `""` (cast nil → `""`, `empty_values: []`); no URL validation on `image` |
| `Social.Follow` | `profiles_profile_follows` | `id`, `from_profile_id` (follower), `to_profile_id` (followee); no timestamps |
| `Articles.Article` | `articles_article` | `slug`, `title`, `description`, `body`, `belongs_to :author, Accounts.Profile`; `many_to_many :tags, through ArticleTag` for reads |
| `Articles.Comment` | `articles_comment` | `body`, `belongs_to :article`, `belongs_to :author, Accounts.Profile` |
| `Articles.Tag` | `articles_tag` | `tag` (display), `slug` (= lower(tag)); no length validation on load or reuse |
| `Articles.ArticleTag` | `articles_article_tags` | `id`, `article_id`, `tag_id`; no timestamps |
| `Articles.Favorite` | `profiles_profile_favorites` | `id`, `profile_id`, `article_id`; no timestamps |

- Integer autoincrement PKs (`:id`). Join tables get schema modules and are written with `insert_all(..., on_conflict: :nothing)` (no `conflict_target`, see consult Q3) and `delete_all`. Never `put_assoc` for tags, follows or favorites.
- Timestamps: `@timestamps_opts [type: Conduit.Ecto.LegacyDateTime, inserted_at: :created_at, autogenerate: {Conduit.Ecto.LegacyDateTime, :utc_now, []}]` on User, Profile, Article, Comment, Tag (ADR-005). `insert_all`/`update_all` set timestamps by hand. `LegacyDateTime` loads both legacy widths (`YYYY-MM-DD HH:MM:SS` and `…SS.ffffff`) as UTC and always dumps `YYYY-MM-DD HH:MM:SS.ffffff` (space, 6 digits, no zone). The global `datetime_type` stays at its default.
- Unique constraints: `unique_constraint/3` with explicit `name:` (ecto_sqlite3 derives `<table>_<col>_index` from the error text, consult Q5; **verify on 0.25.0**, VO-03).
- No `foreign_key_constraint/3` (cannot match on SQLite). Parent existence is checked in the context, which returns `{:error, :not_found}`.
- Ordering lives in queries: `order_by: [desc: :created_at, desc: :updated_at, desc: :id]`. The `:id` tiebreak is a deterministic widening of the legacy "ties undefined" (DV-23).
- Viewer-relative fields (`favorited`, `favoritesCount`, `following`) are batch queries per page, not per row (M-22).

### DDL authority

Ecto owns DDL from cutover. `migration_source: "ecto_schema_migrations"`; `django_migrations` is never read by the app nor written (C-42). Migration 1 replays the legacy DDL **verbatim** (`CREATE TABLE IF NOT EXISTS`, `CREATE [UNIQUE] INDEX IF NOT EXISTS`, Django index names) from `sqlite3 .schema` of a legacy-built copy, so a fresh dev DB equals production and an imported DB gets no DDL. `down/0` raises. A release preflight refuses to migrate when `django_migrations` lacks the expected app migrations or when `sqlite_master.sql` for the 8 tables differs from the baseline (consult Q4). No destructive DDL until a new ADR; the Django framework tables (C-53) stay in place and unmapped (ADR-004).

**Foreign keys.** Legacy declared FKs without enforcement (Django 1.10 on SQLite) and cascaded in Python. ecto_sqlite3 enables `PRAGMA foreign_keys` (**verify default on 0.25.0**, VO-04). Consequences: inserts referencing missing parents fail (the context checks first) and parent deletes with children fail, so every delete path removes children explicitly in one transaction (M-26). The pre-cutover orphan scan (ADR-013) is mandatory. Recorded as DV-21.

### Transactions (ADR-010)

`Repo.transact/2` with a `with` chain (or `Ecto.Multi`) per multi-write operation. Legacy ran in autocommit (M-21), so each of these is a recorded strengthening (DV-20):

| Operation | Commits together |
|-----------|------------------|
| `Accounts.register_user/1` | user insert + profile insert (`bio: ""`, `image: ""`) (M-01, C-05) |
| `Accounts.update_user/2` | user changeset + profile changeset (M-18) |
| `Articles.create_article/2` | article insert + tag upsert + article_tags insert (M-02, M-20) |
| `Articles.update_article/3` | article update + article_tags replace when `tagList` is present (C-29) |
| any future parent delete | children first, then parent (M-26) |

Single-statement writes (follow, favorite, comment add/delete) run without an explicit transaction. Write transactions never wrap slow work; there is none in this app.

## 4. Web, Wire Contract and UI

No UI (ADR-000 "Clients and UI"). Phoenix router + controllers + explicit JSON modules. The legacy wire format is the product contract, so it is implemented directly in the JSON modules and `LegacyErrors`. That is MAP, not SHIM: no foreign protocol is translated, and it is permanent.

**Router.** One `scope "/api"` with explicit routes for every slashless path in C-17. Plug drops empty path segments, so `/api/articles/` also matches (a widening ADR-000 already relaxed, DV-19; **verify**, VO-08). Route order and two route rows are **UNDECIDED** and stay blocked:
- C-35: whether `get "/articles/feed"` is declared before `get "/articles/:slug"` (fix) or after (legacy shadowing). Blocks the feed slice.
- C-36: whether `delete "/articles/:slug"` exists. Blocks the article-write slice.
- C-39: profile route accepts any username or only `\w+`. Blocks the profile slice.

**Pipelines.**

```
Endpoint: Plug.RequestId → Plug.Telemetry → Plug.Parsers(json, urlencoded, multipart; length ~1 MB, see DV-P8) → Corsica → Router
:api            accepts ["json"], put_secure_browser_headers (DV-13), TokenAuth (tri-state)
:public_auth    applies the C-16 policy to {:error, msg} on public routes  (UNDECIDED: refuse with 403, legacy; or treat as anonymous)
:require_auth   anonymous → 403 {"<label>": {"detail": "Authentication credentials were not provided."}} (legacy status quo; C-16 UNDECIDED)
```

`TokenAuth` assigns `:auth` = `:anonymous | {:ok, scope} | {:error, message}`. Header parsing keeps C-10: whitespace split, exactly 2 parts, prefix `token` case-insensitive, else anonymous. The C-16 decision then becomes a one-line pipeline policy rather than a structural change (security consult Q2).

**Error envelopes (C-26, C-16).** One module, `ConduitWeb.LegacyErrors`, renders:
- changeset and validation errors → 400 `{"errors": {"<field>": ["msg"]}}`, non-field under `"error"`;
- bare validation (self-follow) → 400 `{"errors": ["You can not follow yourself."]}`;
- not found → 404 with the per-route key below;
- everything else (auth refusal, forbidden, parse error, method) → `{"<label>": {"detail": msg}}` or bare `{"detail": msg}` when the route's legacy view used DRF's default renderer.

| Route | Label | NotFound body |
|-------|-------|---------------|
| `POST /api/users`, `POST /api/users/login`, `GET/PUT /api/user` | `user` | — |
| `GET /api/profiles/:username` | `profile` | `{"errors":{"profile":"A profile with this username does not exist."}}` |
| `POST/DELETE /api/profiles/:username/follow` | `profile` | `{"errors":{"detail":"A profile with this username was not found."}}` |
| `GET/POST /api/articles`, `GET/PUT /api/articles/:slug`, feed | `article` | `{"errors":{"article":"An article with this slug does not exist."}}` |
| `POST/DELETE /api/articles/:slug/favorite` | `article` | `{"errors":{"detail":"An article with this slug was not found."}}` |
| `GET/POST /api/articles/:slug/comments` | `comment` | create: `{"errors":{"comment":"An article with this slug does not exist."}}`; list on unknown slug: 200 empty (C-23) |
| `DELETE /api/articles/:slug/comments/:id` | none (bare) | `{"errors":{"comment":"A comment with this ID does not exist."}}` |
| `GET /api/tags` | none (bare) | — |

The table is derived from code reading (contracts C-16, C-26, features F-14 "verify"). Golden files recorded from an isolated legacy run freeze it (VO-10, needs user permission, contracts Q7). Unknown routes and crashes → JSON 404/500 with no stack trace, headers or route list (C-34, C-48; DV-05, DV-10). `debug_errors: false` outside dev.

**Request bodies.** `ConduitWeb.Params.wrapped(params, "user")` returns the map under the wrapper or `%{}` (C-18). Controllers cast only whitelisted fields. A missing wrapper becomes 400 field-required, as in legacy. The non-object body and comment-`author` crashes (C-41) are **UNDECIDED**: no 500 is reproduced, but the visible outcome (400 vs ignore and 201) waits for the decision.

**JSON output.** Jason. Field sets exactly as C-19..C-23 (article without `id`, profile `image` smiley fallback, user `image` raw, comment with `id`). Timestamps render as `YYYY-MM-DDTHH:MM:SS.ffffff+00:00` (C-30 kept; the exact Python text, which omits zero microseconds, is relaxed: DV-11). `tagList` order: newest tag first (Tag ordering, C-20). The analysis disagrees on this point (status.md), so it is VO-11.

**CORS (C-31).** Corsica 2.1.3 in the Endpoint before the router, so preflight passes without a token. Origins come from `CORS_ORIGINS` (strict comma list, `*` rejected) and default to `http://localhost:4000`, `https://localhost:4000`, `http://0.0.0.0:4000`, `https://0.0.0.0:4000` (legacy netloc match, any scheme). `allow_credentials: false`, allow headers include `authorization` and `content-type`.

## 5. Jobs, Realtime, Caching

- **Jobs: none.** No Oban. R-20/R-21 (signals) stay synchronous and become explicit transaction steps. Adding Oban later uses `Oban.Engines.Lite` on the writer Repo, in the same file (sqlite-on-beam).
- **Realtime: none.** No PubSub, Channels or sockets in legacy or target.
- **Caching: none.** R-13 (unused LocMemCache) is deleted. ETS or Cachex is added only after a measured need, with complete keys and no cached errors.
- **Rate limiting: none in the baseline.** Login/register throttling (Hammer 7.5.0, 429) is **proposed only** (DV-P4). It belongs to the PBKDF2 iteration decision (OD-2).

## 6. Auth Edge (ADR-006, ADR-007, ADR-008)

- **Tokens.** `Conduit.Accounts.Token` wraps Joken 2.7.0 with a hand-built signer (`Joken.Signer.create("HS256", secret)`) and **no** `Joken.Config` default claims. It encodes exactly `%{"id" => user.id, "exp" => now + 60 * 86_400}`. Verify: `Joken.verify/2` (algorithm pinned through JOSE `verify_strict`, C-15; VO-02), then a pattern match `%{"id" => id, "exp" => exp}` with positive integer `id`, `exp > now`, leeway 0, then `Repo.get(User, id)`, then `is_active`. Messages kept: "Invalid authentication. Could not decode token.", "No user matching this token was found.", "This user has been deactivated.". A fresh token on login, register, GET and PUT `/api/user` (C-12). Keys: sign with `JWT_SECRET`; verify with `JWT_SECRET` then optional `JWT_SECRET_PREVIOUS`. The legacy committed key is never configured. Optional boot guard: refuse a `JWT_SECRET` whose SHA-256 equals the leaked key's fingerprint (store the hash only).
- **Missing `exp`.** Legacy PyJWT 1.4.2 accepted tokens without `exp`. Rejecting them is a **proposed** divergence (DV-P5). Until it is approved the verifier must not silently reject them: the claim match treats `exp` as optional, and the slice decision flips it. No legitimate client can hold such a token after the key rotation, so the risk is low either way.
- **Passwords.** `Conduit.Accounts.Password` in front of pbkdf2_elixir 2.3.1: strict format gate `pbkdf2_sha256$<iter>$<salt>$<b64>`, iteration ceiling 2,000,000, anything else (`!…` unusable, empty, other hashers) → false after a dummy verify, never a raise. New and changed passwords are written in Django format (`format: :django`, sha256) so legacy can still verify them after a rollback hand-back. **Iteration count is OD-2 (UNDECIDED)**: the configured value stays at the legacy 30,000 until the user decides; rehash-on-login is implemented and only fires when the stored count is below the configured one. Unknown email, inactive user and wrong password share one code path (`Pbkdf2.no_user_verify/1`) and one message (C-13).
- **Authorization.** In contexts, against `scope.profile.id`. `update_article`: not found → 404, `author_id != profile.id` → `{:error, :forbidden}` → 403 (C-32). `delete_comment`: one query joining the article by the URL slug and the comment id (strict `Integer.parse`); nil → 404 "A comment with this ID does not exist.", author mismatch → 403 (C-33). The 403 body text and shape (`{"article":{"detail":"You do not have permission to perform this action."}}` and bare `{"detail": …}` on comment delete) are **proposed** (DV-P6) and frozen only after approval.
- **Revocation** stays legacy: stateless tokens, `is_active` re-checked per request, password change does not revoke (C-12; contracts Decision 9 open). No sockets exist, so there is no reconnect path to re-check.
- **Logging.** `filter_parameters: ["password", "token"]`; the `authorization` header is never logged.

## 7. Process Table

No long-lived process beyond the framework defaults. Domain logic is plain modules.

| Name | Runtime reason | Supervisor | Restart | Overload policy |
|------|----------------|------------|---------|-----------------|
| (none) | — | — | — | — |

Framework defaults started: `ConduitWeb.Telemetry`, `Conduit.Repo` (DBConnection pool of 1; queueing via `queue_target`/`queue_interval`, request timeout above DBConnection `timeout`), `Conduit.Repo.Read` (only if ADR-003 option (a) wins), `ConduitWeb.Endpoint` (Bandit). If DV-P4 rate limiting is approved, Hammer's ETS backend adds one supervised process (per-node counters; single node).

## 8. Supervision Tree

```
Conduit.Supervisor (one_for_one)
├── ConduitWeb.Telemetry
├── Conduit.Repo                 # writer: pool_size 1, BEGIN IMMEDIATE, WAL, synchronous FULL
├── Conduit.Repo.Read            # read-only pool; started after the writer (WAL switch needs a writable connection); ADR-003 gate
├── {Conduit.Boot, []}           # one-shot Task (restart: :temporary): logs sqlite_version(), journal_mode, foreign_keys
└── ConduitWeb.Endpoint          # Bandit; Corsica → Router
```

Migrations are not run at boot. They run from the release (`bin/conduit eval "Conduit.Release.migrate()"`) after the preflight.

## 9. Dependencies

Versions from KB (checked by the plugin author on hex.pm, **2026-10-09**; re-check before pinning). Elixir and OTP versions: **verify** (not in KB).

```elixir
{:phoenix, "~> 1.8.15"},          # kb/stacks/django.md
{:bandit, "~> 1.12"},             # 1.12.5, kb/infrastructure.md
{:ecto_sql, "~> 3.14"},           # 3.14.0 (ecto 3.14.2), Repo.transact/2
{:ecto_sqlite3, "~> 0.25.0"},     # KB 0.25.0; the consult read 0.22.0 source: VO-03, VO-04, VO-05
{:jason, "~> 1.4"},               # 1.4.5
{:joken, "~> 2.7"},               # 2.7.0; hand-built signer, no default claims
{:pbkdf2_elixir, "~> 2.3"},       # 2.3.1; Django format verify and hash: VO-01
{:corsica, "~> 2.1"},             # 2.1.3 (kb/ui-strategy.md: dormant but stable)
# only if DV-P4 is approved:
# {:hammer, "~> 7.5"},            # 7.5.0
# dev/test: sobelow, mix_audit (versions: verify)
```

No slugify package: `Conduit.Articles.Slug` reproduces Django 1.10 `slugify` (NFKD, drop non-ASCII, strip `[^\w\s-]`, lowercase, collapse `[-\s]+` to `-`) in a few lines, plus a 6-char `[a-z0-9]` suffix from `:crypto.strong_rand_bytes` and hyphen-boundary truncation to 255 (C-06). Golden vectors come from Python `slugify` outputs recorded offline (VO-07).

## 10. Transition Contract (Replacement)

ADR-000: one maintenance window, never two writers. The per-aggregate table collapses to one row, because every aggregate has the same owner per phase.

| Concern | Before cutover | Cutover | After cutover |
|---------|----------------|---------|---------------|
| Write owner (all aggregates) | Django | nobody (both stopped) | Phoenix |
| Routing | all `/api` → Django | maintenance response at the proxy (if any) | all `/api` → Phoenix |
| Schema authority | `django_migrations` | Ecto baseline recorded in `ecto_schema_migrations` (no DDL on the imported file) | Ecto, additive-only until the rollback window closes |
| Identity | Django issues and reads tokens (leaked key) | — | Phoenix issues and reads; legacy tokens rejected (403 under the C-16 status quo); every client logs in once; password hashes verify unchanged |
| Jobs and events | none | none | none |
| Data movement | — | stop Django, `VACUUM INTO` a rollback copy, run read-only scans (ADR-013), set WAL, start Phoenix on the same file | — |
| Fencing | — | Django process stopped and its start disabled before Phoenix starts; boot check refuses to start if another process holds a write lock (busy on `BEGIN IMMEDIATE` at boot) | — |
| Rollback | — | — | **Preferred:** hand the live file back to Django (checkpoint, `PRAGMA journal_mode=DELETE`), which keeps post-cutover writes because the port writes only Django-readable values (Django-format hashes, legacy datetime text, no DDL on legacy tables). Clients log in again (different key). **Fallback (ADR-000):** restore the pre-cutover copy, which loses post-cutover writes; it needs explicit approval at the time. Valid until the first approved destructive DDL, at most one release cycle (OD-6) |

## 11. Performance Plan

ADR-000 goal: **no regression vs a measured legacy baseline**: p95 latency and throughput for `GET /api/articles?limit=20`, `GET /api/articles/:slug`, `GET /api/articles/feed`, and `POST /api/users/login`, on the same SQLite dataset and machine.

- **P0/P1 (slice 0).** Build the untouched legacy at 29c9d42831fa in an isolated environment. This needs the user's permission (contracts Q7, Iron Law 10). Seed one dataset and checksum it. Record req/s, p50/p95/p99 at c1/c16/c64, CPU per successful response, and errors. Pin OTP and log `System.schedulers_online()`. Legacy runs under `runserver` (threaded dev server): record that as the baseline's server, and do not substitute gunicorn without the user's say.
- **Gates.** Every route ≤ baseline p95 and ≥ baseline throughput at each concurrency. Login is measured at **the configured PBKDF2 iteration count**: at 30,000 the gate applies as written; if OD-2 raises it, login needs an explicit carve-out in ADR-007, because PBKDF2 cost dominates that route by design.
- **Repo topology** is chosen by the ADR-003 measurement, not assumed.
- **P2 before tuning.** Count queries per request (the N+1 removal in M-22 is the expected main gain; unmeasured).
- No speed claim until P4 matched runs on the shipping SHA.

## 12. Slices for `/phx:plan`

| Slice | Capabilities | Ledger focus | Blocked by |
|-------|--------------|--------------|------------|
| S0 Foundation and baseline | F-14 (envelopes, errors, CORS), config, Repo, baseline migration, LegacyDateTime, JSON 404/500 | C-01, C-03, C-34, C-42, C-44, M-08, M-09, M-11, M-36, M-40 | Q7 permission (legacy run for golden files and perf baseline); C-41 visible outcome |
| S1 Accounts and auth | F-01, F-02, F-03, F-04 | C-02, C-05, C-10..C-15, C-22, C-27, M-01, M-04, M-05, M-16..M-19 | C-16, C-40, C-37, OD-2 (iterations), DV-P5 |
| S2 Profiles and follow | F-05, F-06 | C-21, C-28, M-23, M-24 | C-38, C-39 |
| S3 Read articles and tags | F-09, F-10 | C-19, C-20, C-24, M-12, M-22, M-29, M-30 | VO-11 (`tagList` order) |
| S4 Write articles | F-07, F-08 | C-06, C-07, C-29, C-32, M-02, M-20, M-27 | C-08, C-09, C-36, DV-P6 |
| S5 Feed | F-11 | M-30 | C-35 |
| S6 Favorites | F-12 | C-28 | — |
| S7 Comments | F-13 | C-23, C-33 | C-41, DV-P6 |
| S8 Operator and cutover rehearsal | F-15 | C-43, C-52, C-53, M-33, R-03 | OD-5 (admin use), OD-6 (rollback window), Q2 (production data exists) |

## 13. Verification Obligations (carried from consults; none run)

| ID | Claim to prove | How | Blocks |
|----|----------------|-----|--------|
| VO-01 | pbkdf2_elixir 2.3.1 verifies Django 1.10 `pbkdf2_sha256$30000$…` and writes the same format | fixture from Django 1.10 `make_password('correct horse')` produced offline: correct → true, `wrong` → false, `!xyz` → false without raising; Django verifies a port-written hash | S1 |
| VO-02 | Joken 2.7.0 pins HS256 through JOSE `verify_strict` | HS384, HS512 and `alg:none` tokens with the right key → rejected; HS256 → accepted; header bytes `{"alg":"HS256","typ":"JWT"}` | S1 |
| VO-03 | ecto_sqlite3 0.25.0 derives unique constraint names as `<table>_<col>_index` (consult read 0.22.0) | changeset test per unique index on a DB built from the verbatim baseline | S0, S1, S4 |
| VO-04 | ecto_sqlite3 0.25.0 enables `foreign_keys` by default; the decode path accepts both legacy datetime widths | boot check logs the PRAGMA; load fixtures `…:40` and `…:40.500000` | S0 |
| VO-05 | `LegacyDateTime` text sorts port rows correctly against legacy rows (C-03) | legacy row at `…:40.500000`, port row 1 s later → listed first; legacy text unchanged after a non-timestamp update | S0 |
| VO-06 | Exact legacy DDL (FK clauses, inline vs named pair uniques, index names) | `sqlite3 .schema` on a DB built by the 10 legacy migrations in isolation (Q7) | S0 |
| VO-07 | Python 1.10 `slugify` parity for new slugs | golden vectors (Unicode, punctuation, 300-char titles, empty title) generated offline | S4 |
| VO-08 | Plug/Phoenix match `/api/articles/` to the slashless route | router test | S0 |
| VO-09 | Corsica matches the scheme-qualified defaults and rejects `http://evil.test` | preflight tests | S0 |
| VO-10 | Error label and NotFound key per route (section 4 table) | golden files from an isolated legacy run (Q7) | S0..S7 |
| VO-11 | `tagList` order (newest tag first vs insertion order) | isolated legacy run | S3 |
| VO-12 | Repo topology choice (ADR-003) | slice-0 measurement: busy errors, checkout queue time, write p95 | S0 |

## 14. Open Decisions

| ID | Decision | Options | Blocks |
|----|----------|---------|--------|
| OD-1 | Defects left UNDECIDED by ADR-000: C-08, C-09, C-16, C-35, C-36, C-37, C-38 (+ purge of existing self-follows), C-39, C-40, C-41 | per row in the ledger; consult proposals in divergences.md DV-P1..P8 | their slices only |
| OD-2 | PBKDF2 iteration count for new and rehashed passwords | keep 30,000 (no perf change, legacy parity); raise to ~600,000 (OWASP 2023) with a login perf carve-out and DV-P4 rate limiting; an intermediate value benchmarked in slice 0 | S1 login gate |
| OD-3 | SQLite vs Postgres (runtime Q1) | stay on SQLite (ADR-000 default) or a separate ETL project with a new ADR | none now |
| OD-4 | Repo topology | writer + reader vs single writer Repo (ADR-003 measurement) | S0 |
| OD-5 | Django admin use (M-33, C-52) | retire (ADR-000 relax) vs provide a back office (backpex 0.22.0) if an operator needs one | S8 |
| OD-6 | Rollback window and method | hand-back of the live file (preferred) vs restore of the pre-cutover copy; window length | S8 |
| OD-7 | Production CORS origins, observability (runtime Q4, Q6) | env-configured; error tracker choice | S8 |
| OD-8 | Stronger revocation (contracts Decision 9) | keep stateless (default) vs a token table | none now |
