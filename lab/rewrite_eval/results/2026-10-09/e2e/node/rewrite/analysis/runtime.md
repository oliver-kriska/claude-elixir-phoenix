# Runtime — node-express-realworld ("Conduit" API)

Source: `testbeds/node-express-realworld` @ `30b68e1` · Deploy model: single container / single host (Nx-generated `Dockerfile`, or `npm ci && npx prisma migrate deploy && node dist/api/main.js` per README). No compose, k8s, Procfile, PaaS manifest, CI pipeline (README shows a Travis badge; no `.travis.yml` in tree) or crontab.

Topology summary: one stateless Node process + one PostgreSQL database. No Redis, queue, cache, scheduler, websocket, object storage, mail or search. The only durable state is PostgreSQL.

## Process Topology

| ID | Process | Command | Concurrency knob | Health check | Purpose | BEAM disposition |
|----|---------|---------|------------------|--------------|---------|------------------|
| R-01 | web (Express 4.18) | `CMD ["node","api"]` (Dockerfile:22); README alt `node dist/api/main.js` | none: single event loop, no PM2/cluster; DB concurrency = Prisma pool (default `num_cpus*2+1`, overridable via `?connection_limit=` in `DATABASE_URL`) [inferred, Prisma default] | none declared (no Docker `HEALTHCHECK`); `GET /` returns `{"status":"API is running on /api"}` (src/main.ts:21) and is the only probe-able path; e2e test hits it (e2e/src/server/server.spec.ts) | serve RealWorld JSON API under `/api`, static images | REPLACE → Phoenix endpoint (Bandit) in an `mix release`; keep `GET /` body as a health/contract route (tags: contract, operational) |
| R-02 | build step | `nx build` → esbuild to `dist/api`, copies `src/assets/**`, generates `package.json` + lockfile (project.json:5-40) | — | — | produce deployable artefact | REPLACE → `mix release` (+ Dockerfile from `mix phx.gen.release --docker`); tags: platform |
| R-03 | container image | `node:lts-alpine`, non-root `api` user, `npm --omit=dev install` at image build (Dockerfile) | — | — | runtime packaging | REPLACE → Debian/Alpine release image, non-root user kept; tags: platform |
| R-04 | migrate (one-shot) | `npx prisma migrate deploy` (README "Deploy on a remote server") — NOT in the Dockerfile | — | — | apply SQL migrations at deploy | REPLACE → `MyApp.Release.migrate/0` via `bin/migrate` (see Operator Duties); tags: operational |
| R-05 | seed (one-shot, dev/demo) | `npx prisma db seed` → `src/prisma/seed.ts` (12 users x 12 articles x comments, `demo: true`) | — | — | demo data | MAP → `priv/repo/seeds.exs`; must set `demo = true` because the API filters on it (see Q3); tags: business |
| R-06 | crash/shutdown policy | none: no `process.on('SIGTERM'|'uncaughtException')`, no `server.close` (grep: only `app.listen` at src/main.ts:55) | — | — | — | DELETE → OTP supervision + Bandit/Phoenix graceful drain on SIGTERM; tags: platform |

## Datastores by Role

| ID | Component → role | Stores | Loss acceptable? | Consumers | Tags | Candidate verdict → target |
|----|------------------|--------|------------------|-----------|------|----------------------------|
| R-10 | PostgreSQL → system of record | `User`, `Article`, `Comment`, `Tag`, implicit m-n tables (`_ArticleToTag`, `_UserFavorites`, `_UserFollows`) (src/prisma/schema.prisma; 4 migrations) | No — only durable state | this API only (no other service observed); `_prisma_migrations` table read by Prisma CLI | business, contract (data) | KEEP database + schema; MAP access → Ecto schemas with `schema "User"` etc. (PascalCase, quoted), implicit join columns `A`/`B` |
| R-11 | PostgreSQL → migration history | `_prisma_migrations` (Prisma-managed) | No while Prisma may still run (coexistence / rollback) | Prisma CLI | operational | UNDECIDED → baseline Ecto migration over existing schema; whether `_prisma_migrations` is retained or dropped depends on cutover mode (Q1) |
| R-12 | PostgreSQL → identity uniqueness | unique indexes `User_email_key`, `User_username_key`, `Article_slug_key`, `Tag_name_key` (renamed in 20211221184529_deprecated_preview) | No | API error paths (duplicate email/username, slug) | business | MAP → `unique_constraint/3` with the exact index names |
| R-13 | PostgreSQL → column defaults | `User.image` default `https://api.realworld.io/images/smiley-cyrus.jpeg` (20211105153605_api_url); `createdAt/updatedAt` default `now()`; `updatedAt` has NO `@updatedAt`, so it is set only by app code or never (src/prisma/schema.prisma) | No | JSON responses (`image`, `updatedAt`) | contract (wire, data) | MAP → keep DB defaults; check whether services set `updatedAt` on update before choosing Ecto `timestamps` (Q4) |
| R-14 | Process memory → Prisma client singleton | one `PrismaClient` (global cached only in development) (src/prisma/prisma-client.ts) | Yes | — | platform | DELETE → `Repo` under the application supervisor |
| R-15 | Local disk → static images | `src/assets/images/{demo-avatar.png,smiley-cyrus.jpeg}` served at `/images/*` by `express.static` (src/main.ts:18) | Yes (bundled in build) | browsers / front-ends rendering avatars | contract (wire) | MAP → `priv/static/images`, `Plug.Static` at `/images` (note: default avatar URLs point at external `api.realworld.io`, not this host) |

No Redis, cache, queue, pub/sub, lock, rate-limiter or session store exists. Auth is stateless JWT (no server-side session or token revocation table).

## Scheduled and Background Work

| ID | Job | Schedule | Idempotent? | Overlap guard | External effects | Candidate |
|----|-----|----------|-------------|---------------|------------------|-----------|
| — | none found | — | — | — | — | No `setInterval`/`setTimeout`, cron, node-cron, BullMQ or worker process in SOURCE. No Oban needed for parity |

All writes are synchronous in the request. `bcrypt.hash(password, 10)` (auth.service.ts:58,156) is the only CPU-heavy request work; on the BEAM it runs in the request process (`Bcrypt`/`bcrypt_elixir`), no pool needed.

## Storage, Search, Mail, Push, Observability

| ID | Concern | Today | External contract | BEAM disposition |
|----|---------|-------|-------------------|------------------|
| R-20 | File storage | none (avatars are URLs stored as strings) | `image` is a free-form URL | — |
| R-21 | Static assets | `express.static(__dirname + '/assets')` → `/images/...` | 2 image paths | MAP → `Plug.Static` (R-15) |
| R-22 | Search | none (article filters are SQL `where` via Prisma) | — | — |
| R-23 | Mail / push | none | — | — |
| R-24 | Logging | single `console.info("server up on port …")` (src/main.ts:56); no request logging; seed logs errors to stderr | none | REPLACE → `Logger` + `Plug.Telemetry` request logs (improvement, not parity) |
| R-25 | Metrics / tracing / error tracking | none | — | optional: Telemetry metrics; not a parity requirement |
| R-26 | CORS | `cors()` with defaults → `Access-Control-Allow-Origin: *`, all methods (src/main.ts:13) | wire: any browser front-end on any origin can call the API | MAP → `CORSPlug` with origin `*`; tags: contract |
| R-27 | Body parsing | `bodyParser.json()` + `urlencoded({extended:true})` (src/main.ts:14-15) — default 100kb limit | wire: form-encoded bodies accepted too | MAP → `Plug.Parsers` `:json, :urlencoded`; note the 100kb limit vs Plug's 8MB default |
| R-28 | Error envelope | global handler: `UnauthorizedError` → 401 `{"status":"error","message":"missing authorization credentials"}`; `HttpException` → `errorCode` + `message` as JSON; else 500 + message (src/main.ts:27-46) | wire: RealWorld clients parse these | MAP → `FallbackController` + `ErrorJSON` reproducing these bodies; tags: contract |
| R-29 | Auth tokens | HS256 JWT, payload `{user:{id}}`, `expiresIn: '60d'` (token.utils.ts); accepted prefixes `Token` and `Bearer` (auth.ts:5-12); secret `JWT_SECRET` with hard-coded fallback | wire + operational: existing tokens stay valid for 60 days across cutover only if secret, alg and claim shape are kept | MAP → `Joken` (or `JOSE`) HS256 with same secret/claims; plug accepting both prefixes; tags: contract, reliability (session continuity) |

## Operator Duties

| Duty | Today (command/anchor) | Must exist in the release as |
|------|------------------------|------------------------------|
| Apply migrations at deploy | `npx prisma migrate deploy` (README) | `bin/<app> eval "App.Release.migrate()"` (release module) |
| Seed demo data | `npx prisma db seed` (package.json `prisma.seed`) | `mix run priv/repo/seeds.exs` in dev; a release task if demo data is needed in prod (Q3) |
| Build image | `npx nx docker-build api` (project.json `docker-build`) | `docker build` of the release Dockerfile |
| Run server | `docker run -p 3000:3000 -t api` / `node dist/api/main.js` | `bin/<app> start` with `PHX_SERVER=true`, listening on `PORT` (default 3000) |
| Generate DB client | `npx prisma generate` (README) | DELETE — no codegen in Ecto |
| Backups / restore | none in repo (delegated to host/DB provider) [inferred] | unchanged — PostgreSQL-level (`pg_dump`/provider snapshots); no app duty |
| Secret rotation (`JWT_SECRET`) | none; rotating invalidates every token immediately (single secret, no `kid`) | same behavior unless a redesign is approved |
| Maintenance mode, admin CLI, data export | none | — |

Duty count: 5 that must exist (migrate, seed, build, run, health route); 3 absent today.

## Environment Contract

| Env var | Read at | Purpose | Keep name? |
|---------|---------|---------|------------|
| `DATABASE_URL` | src/prisma/schema.prisma (`env("DATABASE_URL")`); README | Postgres connection (may carry Prisma-only query params like `connection_limit`, `schema`) | Yes — but strip/translate Prisma-specific params for Ecto (Q5) |
| `JWT_SECRET` | src/app/routes/auth/auth.ts:16,21; token.utils.ts:4 | HS256 signing/verification; falls back to literal default if unset | Yes, same value required for token continuity; drop the fallback (fail fast) — needs approval (Q2) |
| `PORT` | src/main.ts:53 (default 3000); Dockerfile `ENV PORT=3000`; e2e/src/support/test-setup.ts | listen port | Yes |
| `HOST` | Dockerfile `ENV HOST=0.0.0.0`; e2e test-setup only (app does not read it) | bind address (informational) | Optional → `PHX_HOST`/endpoint `ip` |
| `NODE_ENV` | src/prisma/prisma-client.ts:19; README requires `production` | dev-only Prisma singleton caching | DELETE (platform) → `MIX_ENV` at build |

## Questions

- Q1 (R-11): Cutover mode — big-bang or coexistence with the Node app on the same database? Decides whether Prisma's `_prisma_migrations` stays authoritative during coexistence and who owns schema changes.
- Q2 (R-29): Is the `'superSecret'` fallback ever relied on in any deployment (i.e., is `JWT_SECRET` unset anywhere)? If so, keeping existing tokens valid means keeping that value; removing the fallback is a guarantee change.
- Q3 (R-05): Is demo data (`demo = true`) expected in production? `tag.service.ts:6` and `article.service.ts:14,421` filter on `demo`, so the seed has runtime meaning beyond development.
- Q4 (R-13): `updatedAt` has only a DB default and no `@updatedAt`; does any service set it on update? Affects whether Ecto `timestamps()` would change visible `updatedAt` values.
- Q5: What hosts this in production (container platform, DB provider, TLS terminator)? Nothing in repo states it; needed for health check path and pool sizing.
- Q6 (R-03): The image runs `npm install` without `prisma generate` and the generated `package.json` may lack the `prisma.schema` path; how is the Prisma client generated in the shipped image today? Only matters if the Node image must keep running during coexistence.

## Coverage

Read: Dockerfile, package.json, project.json, nx.json (listing), README.md, .gitignore, src/main.ts, src/app/routes/routes.ts, auth.ts, token.utils.ts, prisma-client.ts, schema.prisma, all 4 migrations + migration_lock.toml, seed.ts, e2e support files; grep across src/ and e2e/ for `process.env`, timers, Redis/queue/cache libraries, signal handlers, `$transaction`, bcrypt, `demo`.
Not present in SOURCE (searched, absent): compose, Procfile, k8s/Helm, fly/serverless config, CI workflows, crontab, Redis/queue/cache deps, `.env.example`.
Gaps: production hosting, DB backup policy and real `DATABASE_URL` params are outside the repo (Q5). Service-level business logic (article/profile/tag services) was read only for infra-relevant calls; behavior belongs to the domain analysis.
