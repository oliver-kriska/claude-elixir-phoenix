# Architecture: Conduit API on Phoenix

**Source:** `node-express-realworld` @ `30b68e1e8814` · **Target:** empty workspace (no `mix.exs` yet) · **Date:** 2026-10-09
**Bar:** ADR-000, Status ASSUMED (`--auto`). Everything below rests on it and nothing here is accepted.
**Mode:** `--auto`. ADRs are `proposed` or `ASSUMED`; divergences are `pending`. No code has been run, so nothing
here claims tested parity or speed.

## 1. Overview

The legacy app is one stateless Express process that serves the RealWorld JSON API to SPAs and API clients, backed by
one PostgreSQL database. It has no UI, jobs, cron, cache, sockets, mail or external HTTP calls (runtime.md, mechanisms.md
"Node probes").

**Shape:** `KB/app-shapes.md` shape 2 (SPA + JSON API), with no SPA in the repo. Clients are third-party RealWorld
front-ends that send `Authorization: Token <jwt>`.

**Target:** one Phoenix 1.8 release with **controllers and explicit `*JSON` view modules only**. No HTML, LiveView,
Oban, PubSub, cache or clustering (ADR-001). Ecto maps the Prisma schema unchanged (ADR-003). Every Express or Prisma
behaviour that the bar keeps byte-compatible lives in a named compat module at the edge (`RealworldWeb.Compat.*` for
HTTP, `Realworld.Compat.*` for value formats). Domain contexts stay idiomatic (ADR-006, ADR-008).

**Cutover:** Replacement (ADR-000 A1). Stop Node, start Phoenix against the same database, then an observation window
with rollback to the Node image. During the window Phoenix runs **zero DDL**, and every row it writes must stay
readable by Prisma (ADR-003). Tokens are compatible in both directions (ADR-004).

Steering files: none in SOURCE or TARGET (charter).

## 2. Context Map

Contexts are grouped by shared invariants, not by legacy controller (`auth`, `profile`, `article`, `tag`).

| Context | Owns (tables) | Invariants enforced | Public API (all take `%Scope{}` where identity matters) | Events / jobs | Calls into |
|---------|---------------|---------------------|-----------------------------------------------------------|---------------|------------|
| `Realworld.Accounts` | `"User"` | Case-sensitive unique email and username (`User_email_key`, `User_username_key`). `demo` is never client-settable (C-08). bcryptjs-compatible hashes with JS trim rules (C-02, C-30). Token format: HS256 `{user:{id}}`, 60 days (C-12). A fresh token on every register, login and `GET/PUT /user` (C-16) | `register_user(attrs)` · `authenticate(email, password)` · `get_current_user(scope)` · `update_user(scope, attrs)` · `issue_token(user)` · `verify_token(token) :: {:ok, user_id} \| :error` · `get_user_by_username(username)` | none | — |
| `Realworld.Profiles` | `"_UserFollows"` (follow graph) | A/B direction: A = followed, B = follower (C-03, **verification V-1**). Follow and unfollow are idempotent. Self-follow allowed. No demo filter on profiles | `get_profile(scope, username)` · `follow(scope, username)` · `unfollow(scope, username)` · `following_flag(query, viewer_id, author_binding)` (composable `EXISTS`) · `followed_ids_query(viewer_id)` | none | `Accounts.get_user_by_username/1` |
| `Realworld.Articles` | `"Article"`, `"Comment"`, `"Tag"`, `"_ArticleToTag"`, `"_UserFavorites"` | Slug = `slugify@1.6.6(title) <> "-" <> author_id`, unique (`Article_slug_key`, C-11). Only the author edits or deletes (C-19 bodies). The tag set is replaced atomically (ADR-012). Favorites are idempotent. **Visibility rule** across list, comments and tags (C-23, UNDECIDED). DB cascades do deletes (C-09). Only an article edit bumps `updatedAt` (C-04) | `list_articles(scope, filters)` → `{articles, count}` · `feed(scope, page)` · `get_article(scope, slug)` · `create_article(scope, attrs)` · `update_article(scope, slug, attrs)` · `delete_article(scope, slug)` · `favorite(scope, slug)` · `unfavorite(scope, slug)` · `list_comments(scope, slug)` · `add_comment(scope, slug, attrs)` · `delete_comment(scope, comment_id)` · `popular_tags(scope)` | none | `Profiles.followed_ids_query/1` and `Profiles.following_flag/3` (read-only query composition) |

Supporting namespaces (not contexts, no tables):

- `Realworld.Accounts.Scope`: `%Scope{user_id: pos_integer() | nil}`. It holds **only the verified token's user id**.
  The auth plug never loads the user, because legacy never checks that the user exists (C-15). Contexts load the user
  where legacy does.
- `Realworld.Compat`: value-format adapters with one owner each. `Slug` is the slugify 1.6.6 port (ADR-007).
  `JsString` covers JS `trim`, the JS whitespace class, `Number(x) || default` coercion and JS truthiness. `Time` covers
  `now_ms/0` and `iso8601_ms/1`. `DatabaseUrl` translates Prisma URL params (ADR-013).
- `RealworldWeb.Compat`: HTTP edge SHIMs (ADR-006). `ExpressCors`, `ExpressHeaders` (weak ETag/304, `X-Powered-By`,
  header trimming), `ExpressBodyParser`, `ExpressPathCase`, `NotFound` (Express HTML 404) and `LegacyErrors`
  (error envelopes). Plus `RealworldWeb.Plugs.Auth` with `mode: :optional | :required` (ADR-004).

Why three contexts and not five: comments and tags share the visibility rule and the article ownership and cascade
invariants, so they share `Articles`. Splitting them would spread one product rule over three owners. The follow graph
is a separate owner because its A/B invariant has its own blocking verification (V-1), and three surfaces read it
(profile, author `following`, feed). It is the one context near the "wraps one table" smell. ADR-002 records why it
still pays for itself.

## 3. Data Layer

- **Repo topology:** PostgreSQL, one `Realworld.Repo`. `parameters: [timezone: "UTC"]`,
  `migration_source: "ecto_schema_migrations"` and `pool_size` from `POOL_SIZE` or the translated `connection_limit`.
- **Schema mapping (ADR-003):** `schema "User"`, `"Article"`, `"Comment"`, `"Tag"`. Fields are snake_case with
  `source: :camelCase`. Default `:id` PKs over the SERIAL sequences, never computed. Timestamps:
  `timestamps(inserted_at: :created_at, inserted_at_source: :createdAt, updated_at: :updated_at, updated_at_source: :updatedAt, type: :utc_datetime_usec, autogenerate: {Realworld.Compat.Time, :now_ms, []})`
  on `Article` and `Comment`. `User` has no timestamps. `User.image` is `read_after_writes: true` with no Ecto default,
  so the DB default applies (C-07). `demo` defaults to false and is never cast.
- **Join tables:** schemaless `insert_all(..., on_conflict: :nothing, conflict_target: [:A, :B])` and `delete_all` on
  `"_ArticleToTag"`, `"_UserFavorites"` and `"_UserFollows"`. Flags (`favorited`, `favoritesCount`, `following`) come
  from `EXISTS` and `count` subqueries, not from preloaded user lists (M-19).
- **Constraint names:** `unique_constraint(..., name: "User_email_key" | "User_username_key" | "Article_slug_key")`,
  and `foreign_key_constraint(:article_id, name: "Comment_articleId_fkey")` (name to be verified with `\d` on the
  snapshot). Associations use `on_delete: :nothing` because the DB cascades (C-09).
- **DDL authority:** during the observation window nobody runs DDL. `priv/repo/migrations/` stays empty. No
  `Ecto.Migrator` child exists. `Realworld.Release.migrate/0` refuses unless `ECTO_DDL_OWNER=true`.
  `_prisma_migrations` is untouched. Tests load a committed `priv/repo/structure.sql`, dumped from the 4 Prisma
  migrations applied to a scratch DB. After rollback retires, Ecto takes ownership with an assert-don't-create
  baseline (ADR-003).
- **Transactions:** `Repo.transact/2` or `Ecto.Multi` for article create and update (article, tag upsert, links) and
  for nothing else that needs it. No side effects exist, so the after-commit rule does not come up. Article update
  takes `FOR UPDATE` on the row (ADR-012).

## 4. Web, Realtime, UI

- **No UI** (A4). Phoenix controllers with `action_fallback RealworldWeb.FallbackController` and explicit view modules
  (`UserJSON`, `ProfileJSON`, `ArticleJSON`, `CommentJSON`, `TagJSON`). The views emit `Jason.OrderedObject` in the
  legacy key order, because A4 says byte-compatible. Golden fixtures pin the order.
- **Timestamps on the wire:** `Realworld.Compat.Time.iso8601_ms/1` gives `YYYY-MM-DDTHH:MM:SS.mmmZ` (C-20). Never the
  default `Jason.Encoder` for `DateTime`.
- **Realtime:** none in legacy, none in target. No `Phoenix.PubSub` child.
- **Endpoint plug order** (it mirrors Express `main.ts:13-19`, ADR-006):

```elixir
# RealworldWeb.Endpoint (shape only)
plug RealworldWeb.Compat.ExpressHeaders     # before_send: weak ETag + 304, X-Powered-By, drop Plug's default cache-control, drop x-request-id
plug RealworldWeb.Compat.ExpressCors        # every OPTIONS -> 204 + Express headers, halt; otherwise ACAO: *
plug Plug.Static, at: "/", from: :realworld, only: ~w(images)
plug Plug.RequestId                         # for logs only; the header is stripped by ExpressHeaders
plug Plug.Telemetry, event_prefix: [:phoenix, :endpoint]
plug RealworldWeb.Compat.ExpressBodyParser  # wraps Plug.Parsers [:urlencoded, :json], length: 102_400; parse errors -> legacy 500 (C-32a)
plug Plug.Head                              # Express answers HEAD for GET routes
plug RealworldWeb.Compat.ExpressPathCase    # case-insensitive literal segments, position-aware (C-36a)
plug RealworldWeb.Router
# Not included on purpose: Plug.MethodOverride (Express has none), Plug.Session, :accepts (406 would be new)
```

- **Router:** `scope "/api"`. Routes are defined **in contract order**, and the required-auth scope comes first so
  that `GET /articles/feed` compiles before `GET /articles/:slug` (C-36). Three pipelines: `:public` (register and
  login; express-jwt is not mounted there, so a bad token is ignored), `:optional_auth` and `:required_auth`. The
  per-route matrix comes from the JSDoc `@auth` tags (M-07) and is confirmed per controller in slice S1. Last comes
  `match :*, "/*path", RealworldWeb.Compat.NotFound, :show`, which returns Express's HTML `Cannot <METHOD> <path>`
  404 for unknown paths and wrong methods (C-33).
- **`GET /`** returns 200 `{"status":"API is running on /api"}` with no DB check (C-33).

## 5. Jobs, Caching, Auth Edge

- **Jobs:** none exist, so there is no Oban. Every write is synchronous in the request, as in legacy. Not adding Oban
  is not a deviation: there is no durable async obligation to own (ADR-001). If mail, webhooks or cleanup arrive
  later, Oban (`Oban.Engines.Basic`) is the default.
- **Caching:** none in legacy, and no measured need. No ETS or Cachex.
- **Auth edge (ADR-004, ADR-005):**
  - `RealworldWeb.Plugs.Auth`:
    - It reads only the first `authorization` header and splits on a single space, like JS `split(' ')`.
    - It accepts only the case-sensitive schemes `Token` and `Bearer`. Anything else counts as no token.
    - When a token is present it is always verified, on optional routes too (C-14, fail-closed).
    - Every failure returns `401` with the prebuilt body `{"status":"error","message":"missing authorization credentials"}`.
    - On success it assigns `current_scope = %Scope{user_id: id}`. It looks up no user (C-15).
  - `Realworld.Accounts.Token` is an explicit Joken config:
    - HS256 only, with `iat` and `exp = iat + 5_184_000`. No `iss`, `aud`, `jti` or `nbf`. Zero leeway.
    - `user.id` must be an integer.
    - Tokens without `exp` are rejected (DV-07, pending).
  - The secret comes from `runtime.exs`. Whether the `superSecret` fallback stays is C-37a, UNDECIDED (ADR-011).
  - Passwords use `bcrypt_elixir`. Verification accepts `$2a$`. New hashes use
    `Bcrypt.hash_pwd_salt(pw, log_rounds: 10, legacy: true)`, which gives `$2a$10$`.
  - `Realworld.Compat.JsString.trim/1` applies JS trim semantics on register and login. Update hashes the
    password untrimmed (C-30, UNDECIDED).
  - An unknown email at login still costs one bcrypt-10 (`Bcrypt.no_user_verify/1`). This equalizes timing with no
    wire change.
  - No rehash on login while rollback is possible.
- **Revocation:** none, by contract (C-15 kept). No sockets exist, so there is no reconnect re-check to design.
- **Log hygiene:** `filter_parameters: ["password", "token"]`. Request logging never logs `authorization`.
  `debug_errors: false` in prod.

## 6. Process Table

| Name | Runtime reason | Supervisor | Restart | Overload policy |
|------|----------------|------------|---------|-----------------|
| *(none beyond framework defaults)* | — | — | — | — |

The domain is plain modules over `Repo`. The only processes are the framework's: Telemetry, the Repo pool and the
Bandit endpoint. bcrypt runs as a NIF on dirty schedulers inside the request process, so it needs no pool.

## 7. Supervision Tree

```elixir
Realworld.Supervisor (strategy: :one_for_one)
├── RealworldWeb.Telemetry        # telemetry_poller + metrics (framework default)
├── Realworld.Repo                # Postgrex pool; pool_size from POOL_SIZE / DATABASE_URL connection_limit
└── RealworldWeb.Endpoint         # Bandit on $PORT (default 3000), graceful drain on SIGTERM
# Absent on purpose: Phoenix.PubSub, DNSCluster, Oban, Finch, Ecto.Migrator (ADR-001, ADR-003)
```

## 8. Dependencies

Versions come from `KB/stacks/node.md` and `KB/data-compat.md` (hex.pm, verified 2026-10-09), unless marked `verify`.

```elixir
{:phoenix, "~> 1.8"},          # 1.8.15 (KB 2026-10-09)
{:bandit, "~> 1.12"},          # 1.12.5 (KB 2026-10-09)
{:ecto_sql, "~> 3.14"},        # 3.14.0; ecto 3.14.2 (KB 2026-10-09); Repo.transact/2 since 3.13
{:postgrex, "~> 0.22"},        # 0.22.4 (KB 2026-10-09)
{:joken, "~> 2.7"},            # 2.7.0 (KB 2026-10-09)
{:bcrypt_elixir, "~> 3.3"},    # 3.3.2 (KB 2026-10-09)
{:jason, "~> 1.4"},            # verify: version not in KB; needs Jason.OrderedObject (>= 1.3, verify)
{:plug, "~> 1.20"},            # 1.20.3 (hex-library-researcher consult, 2026-07 release)
{:telemetry_metrics, "~> 1.0"}, {:telemetry_poller, "~> 1.0"},   # verify
# dev/test only
{:sobelow, "~> 0.13", only: [:dev, :test], runtime: false},     # verify
{:mix_audit, "~> 2.1", only: [:dev, :test], runtime: false}     # verify
```

Elixir and OTP versions: `verify` (not in KB). Rejected on purpose: `cors_plug` and `corsica` (no exact Express
preflight parity), every Hex slug library (none matches slugify 1.6.6), `etag_plug` (stale, strong tags), `guardian`
(cookie and claim conventions not needed), `oban` and `cachex` (no obligation). See the hex-library-researcher consult.

## 9. Transition Contract (Replacement)

The bar picks Replacement, so these rows cover the cutover window and the rollback window only. There is no long-lived
coexistence.

| Aggregate | Write owner | Routing | Schema authority | Identity | Jobs / events | Data movement | Cutover | Rollback |
|-----------|-------------|---------|------------------|----------|---------------|---------------|---------|----------|
| Users (`"User"`) | Node until stop, then Phoenix only. No dual writes | One upstream at a time, switched at the LB or container | Frozen. Nobody runs DDL. `_prisma_migrations` untouched | Both runtimes mint and verify the same HS256 `{user:{id}}` 60-day tokens under the same `JWT_SECRET`. No revocation | none | none (same DB) | Rehearse on a prod snapshot. Stop Node, deploy Phoenix, run contract smoke probes, then the observation window | Redeploy the Node image. Phoenix hashes are `$2a$10$`, so Node verifies them. Phoenix tokens verify in Node |
| Follow graph (`"_UserFollows"`) | same | same | same | — | none | none | **Blocked until V-1 confirms A = followed, B = follower** | Rows Phoenix inserts use the same A/B direction, so Node reads them correctly. A wrong direction would invert feeds on both runtimes |
| Articles, tags, favorites | same | same | same | — | none | none | Slug golden corpus must pass (ADR-007) | Phoenix rows carry ms-precision UTC timestamps, legacy-format slugs and Prisma-shaped join rows (C-03, C-04, C-11) |
| Comments | same | same | same | — | none | none | — | same as articles |

- **Fencing:** Node is stopped (drained) before Phoenix takes traffic. There is no window with two writers. In-flight
  Node requests drain with the container stop, and Phoenix starts only after that.
- **Last reversible point:** the first Ecto DDL change, which is the baseline migration run with
  `ECTO_DDL_OWNER=true`. Until then, rollback is a redeploy. A restore is needed only if Phoenix-written rows must be
  discarded.
- **Old readers versus new writes:** the S9 rehearsal runs the pinned Node build against a DB that Phoenix has
  written to. Witnesses: `prisma migrate status` up to date, Node `GET /api/user` with a Phoenix token returns 200, and
  Node login with a Phoenix-made hash returns 200.

## 10. Performance Plan

The goal comes from ADR-000 A6: **no regression** in p95 latency or throughput against the Node build at `30b68e1`, on
the same hardware and database.

- **P0 workload:** list articles (anonymous and authed), feed, single article, favorite, login (bcrypt cost 10). Run
  at concurrency 1, 16 and 64 on the seeded dataset (12 users, 144 articles, 1,728 comments) and on a larger
  prod-shaped snapshot if one is available.
- **Metrics per route:** req/s, p50, p95 and p99, CPU per successful response, peak memory, wire bytes, errors.
- **P1 baseline (slice S0):** untouched upstream `30b68e1` image, pinned `node:lts-alpine` digest, dedicated host,
  same `nofile`. **Until the baseline exists, the gate is "measure only".** No claim of speed.
- **Expected hotspots (hypotheses, not claims):**
  - Legacy loads full `favoritedBy` and `followedBy` lists per article. The target uses subqueries, which removes
    that work. This must be measured.
  - Login latency will differ, because bcrypt runs as a dirty NIF instead of pure-JS bcryptjs.
  - `ExpressHeaders` hashes every response body with SHA-1 for the ETag. Profile this in P2.
- **Pool sizing:** start at `POOL_SIZE=10` and tune from P2 profiles. Never size per request.

## 11. Proposed Slices (input for `/rewrite:roadmap`, not a plan)

| Slice | Content | Blocked by |
|-------|---------|------------|
| S0 | Isolation decision for characterization runs. Golden fixtures (slugify corpus, jsonwebtoken and bcryptjs fixtures, HTTP goldens from the pinned legacy build). Perf baseline. V-1 scratch-DB check | isolation decision (open) |
| S1 | Skeleton: release, `runtime.exs`, Repo over `structure.sql`, edge SHIMs, `GET /`, static images, 404 HTML, error envelopes | C-32a (parser error status), C-37a (secret policy) |
| S2 | Identity: register, login, `GET/PUT /user`, tokens, hashes | C-18a (login 403), C-30 (update quirks), C-19a (500 bodies) |
| S3 | Profiles and follow | V-1, C-19a |
| S4 | Article reads: list, feed, single, tags | **C-23 / M-11** (list and tags acceptance), V-1 (feed) |
| S5 | Article writes: create, update, delete, slug | C-27 (tag wipe), C-19a |
| S6 | Favorites | **C-21 / M-20** |
| S7 | Comments | C-26, **C-23 / M-11** (list acceptance) |
| S8 | Operator duties: migrate gate, seed task, Dockerfile | C-23 (whether the demo seed matters in prod) |
| S9 | Cutover rehearsal and rollback test | all of the above, plus confirming the production `JWT_SECRET` |

## 12. Open Decisions

UNDECIDED rows (each lists the slices it blocks; see `ledger.md`):

1. **C-21 / M-20** favorite response leaks emails and bcrypt hashes (ADR-009). Blocks S6.
2. **C-23 / M-11** demo-only visibility rule (ADR-010). Blocks S4 and S7 acceptance, and S8 seed relevance.
3. **C-37a** `superSecret` fallback (ADR-011). Blocks S1 boot config and the S9 go/no-go.
4. **Bug-for-bug policy** (ADR-008): C-18a login 403 (S2), C-19a which 500s stay 500 and what their body says (S2–S7
   error probes), C-26 comment quirks (S7), C-27 tag wipe on update (S5), C-30 update quirks (S2).
5. **C-32a** oversized-body status. The contract register says 413, but the library source says the legacy app returns
   500 `"request entity too large"` (ADR-014, DV-01). Blocks the S1 parser probe only.

Blocking verifications (facts to confirm, not product choices):

- **V-0** Isolation decision for running the pinned legacy build to produce goldens. Rule 10: never run it without
  one.
- **V-1** `_UserFollows` direction. Prisma's rule gives A = followed and B = follower (about 70–75% confidence). A
  scratch-DB check is needed (ecto-schema-designer Q2). Blocks S3, S4 feed and S9.
- **V-2** `SHOW timezone` on the prod snapshot, plus a legacy-created `createdAt` checked against UTC.
- **V-3** FK constraint names (`\d "Comment"`).
- **V-4** Production `JWT_SECRET` is set and is not `superSecret` (checked offline, never logged).
- **V-5** Whether anything probes `GET /`. Whether any client sends form-encoded bodies or non-canonical path case
  (access logs). These do not block, because the bar keeps all three.
