# ADR-000: Compatibility Bar

**Status**: ASSUMED (auto, needs approval)
**Date**: 2026-10-09 · **Source**: `testbeds/node-express-realworld` @ `30b68e1e8814` · **Decided by**: `--auto`

## Assumptions

Each line is a `--auto` default taken from `compatibility-bar.md`. None is approved.

- **A1 Cutover = Replacement.** Rule: `runtime.md` shows one deployable (the Express web process) and one database (PostgreSQL).
- **A2 Data = Keep schema as-is.** Rule: always. Ecto maps the PascalCase/camelCase Prisma tables unchanged.
- **A3 Identity = Keep sessions and hashes.** Rule: always. Legacy JWTs and bcryptjs hashes keep working, so no user is logged out.
- **A4 Clients = No UI; keep wire protocols.** Rule: the app shape is `http-api` with no UI. The RealWorld JSON API stays byte-compatible.
- **A5 Contracts = Keep all.** Rule: always. This includes the quirks and the two security-relevant contracts flagged ⚠ below. Keeping them is the conservative default, not a recommendation.
- **A6 Perf goal = No regression against a measured legacy baseline.** Rule: the baseline is a roadmap slice-0 task.
- **A7 Steering = Charter wins.** No steering files were found, so there are no conflicts.
- **A8 Scope = All preserved features** (charter: whole app).

### Consequential assumptions that block `/phx:plan`

`/rewrite:roadmap --auto` will not hand a slice to `/phx:plan` while these are ASSUMED:

1. **A1 Cutover mode.** It decides rollback and schema authority.
2. **A3 Identity.** It requires carrying the production `JWT_SECRET` over, and that value is unconfirmed (C-37).
3. **C-21 favorite-response leak kept** ⚠. Emails and bcrypt hashes go out on the wire. Every analyst recommends changing it.
4. **C-23 demo-only visibility rule kept** ⚠. Product rule or demo-host artefact? It hides real users' content from each other.
5. **C-37 `superSecret` fallback kept** ⚠. Tokens can be forged if `JWT_SECRET` is unset.
6. **Bug-for-bug policy** (C-14, C-19, C-27, C-30, login 403). Every kept quirk becomes a named compat behaviour.

## Cutover Mode

**Replacement.** There is one Express process, no workers, no queues, no cache and one PostgreSQL database. The
Phoenix release replaces the Node container in one maintenance window. The cutover is rehearsed against a
production-like snapshot. Rollback works by redeploying the Node image against the same database, which Elixir
has not changed at the schema level. A restore is needed only if Elixir-written rows must be discarded.

Rollback stays cheap only if:

- Elixir changes no DDL before the observation window closes.
- Elixir mints tokens the Node app accepts (C-12 shared secret and format).
- Every row Elixir writes satisfies Prisma's expectations: `updatedAt` default, `TIMESTAMP(3)`, sequences, and join-table A/B semantics (C-03, C-04, C-06).

## Kept Contracts

| Contract | Surface | Disposition | Consumers | Witness |
|----------|---------|-------------|-----------|---------|
| C-01 PascalCase tables / camelCase columns | data | keep | port, rollback to Node | analysis/contracts.md C-01 |
| C-02 bcryptjs `$2a$10$` hashes, trim on register/login | data | keep | every existing user | C-02 |
| C-03 Prisma implicit m2m tables (`_ArticleToTag`, `_UserFavorites`, `_UserFollows` A/B) | data | keep | port, rollback | C-03 (A/B direction of `_UserFollows` unconfirmed, see M-16) |
| C-04 `TIMESTAMP(3)` UTC, `updatedAt` DB default | data | keep | clients via JSON timestamps | C-04 |
| C-05 case-sensitive unique constraints and their index names | data | keep | changeset error mapping | C-05 |
| C-06 SERIAL int4 PKs and sequences | data | keep | rollback | C-06 |
| C-07 `User.image` default URL | data | keep | clients | C-07 |
| C-08 `User.demo` flag | data | keep | visibility rule C-23 | C-08 |
| C-09 FK `ON DELETE CASCADE` | data | keep | delete flows | C-09 |
| C-10 `_prisma_migrations` history | data | keep (untouched; see Data) | rollback to Node | C-10 |
| C-11 slug = slugify 1.6.6 (case-preserved) + `-authorId` | data | keep (byte-compatible, golden-tested) | public URLs | C-11 |
| C-12 legacy JWT (HS256, `{user:{id}}`, 60d) | wire | keep, two-way | all logged-in clients | C-12 |
| C-13 `Token` and `Bearer` schemes | wire | keep | clients | C-13 |
| C-14 every JWT failure → 401 envelope, including optional-auth routes | wire | keep | clients | C-14 |
| C-15 stateless tokens, no revocation | wire | keep | clients | C-15 |
| C-16 fresh token on register/login/GET+PUT user | wire | keep | clients | C-16 |
| C-17 user envelope (incl. `id` inconsistency) | wire | keep | clients | C-17 |
| C-18 422 validation messages | wire | keep | clients | C-18 |
| C-19 other error bodies (404 `{}`, 403 login, Prisma 500s) | wire | keep (bug-for-bug) | clients | C-19 |
| C-20 article object shape | wire | keep | clients | C-20 |
| C-21 favorite/unfavorite leak ⚠ | wire | keep (ASSUMED; change recommended) | clients | C-21 |
| C-22 list articles query + ordering | wire | keep | clients | C-22 |
| C-23 demo visibility rule ⚠ | wire | keep (ASSUMED) | anonymous + non-demo users | C-23 |
| C-24 feed | wire | keep | clients | C-24 |
| C-25 slug URLs, rename → old 404 | wire | keep | clients | C-25 |
| C-26 comments shape, unordered | wire | keep | clients | C-26 |
| C-27 article CRUD statuses, tag wipe without `tagList` | wire | keep (bug-for-bug) | clients | C-27 |
| C-28 profiles + follow | wire | keep | clients | C-28 |
| C-29 tags top-10 | wire | keep | clients | C-29 |
| C-30 truthy-only user update, untrimmed password | wire | keep (bug-for-bug) | clients | C-30 |
| C-31 CORS `*` | wire | keep | browser front-ends | C-31 |
| C-32 JSON + form-urlencoded bodies, 100kb limit | wire | keep | clients | C-32 |
| C-33 `GET /` liveness body, unknown-path 404 | wire | keep | monitors (unconfirmed) | C-33 |
| C-34 `/images/*` static at web root | wire | keep | clients rendering avatars | C-34 |
| C-35 Express response semantics (content type, weak ETag/304) | wire | keep | clients/proxies | C-35 |
| C-36 route table under `/api` | wire | keep | clients | C-36 |
| C-37 env vars incl. `superSecret` fallback ⚠ | operational | keep (ASSUMED; fail-to-boot recommended) | operators | C-37 |
| C-38 operator commands (migrate, seed) | operational | keep in spirit: release tasks replace `npx prisma` | operators | C-38 |
| C-39 seeded demo dataset semantics | operational | keep | anonymous viewers | C-39 |
| C-40 logging (single boot line) | operational | relax: Phoenix logs requests by default; no consumer depends on silence | operators | C-40 |

## Changed or Retired Contracts

| Contract | Change | Consumers affected | Approval |
|----------|--------|--------------------|----------|
| C-40 logging | Standard Phoenix/Logger request logs replace a single `console.info` line | operators only | ASSUMED (operational relax, no client impact) |

No contract is deliberately relaxed under `--auto`. The design still departs from legacy behaviour, mostly on failure paths, deny-only hardening and changes that cannot be avoided. These are listed as DV-01…DV-17 in `divergences.md` (all `pending`) and must be reviewed together with this bar. Candidate changes the user should decide on: C-21, C-23, C-37, the C-19/C-27/C-30 quirks.

## Data

- **Schema:** kept as-is. Ecto schemas use the existing table names as sources (`schema "User"`, `"Article"`, …, which Postgrex quotes) and map camelCase columns with `field ..., source: :createdAt`. Join tables are mapped explicitly with `A`/`B` columns.
- **DDL authority:** during the observation window, nobody changes DDL. Prisma's `_prisma_migrations` stays untouched so a Node rollback runs `prisma migrate deploy` cleanly. After the window closes and rollback is retired, Ecto takes DDL ownership. It records a baseline migration that checks the existing schema instead of creating it. Renaming to snake_case is a later, separate decision (expand → contract) and is not part of this rewrite.
- **Files:** two static avatar images move into `priv/static/images/`. There are no user uploads.

## Identity

- **Issuer and reader:** both runtimes. Elixir verifies and mints HS256 `{user:{id}}` tokens with a 60-day `exp` under the same `JWT_SECRET`, so tokens it mints stay valid after a rollback to Node.
- **Passwords:** bcryptjs `$2a$10$` hashes verify unchanged. New hashes use the same cost and trimming rules (C-02, C-30).
- **Revocation:** none (C-15). Kept.
- **Precondition:** the production `JWT_SECRET` value must be confirmed and carried over before cutover. The `superSecret` fallback is kept under `--auto` (⚠ ASSUMED).

## Clients and UI

No UI. Every RealWorld front-end and API client must keep working with no change. LiveView is not in scope.

## Performance Goal

No regression against legacy: p95 latency and throughput on a named workload (list articles, feed, single article,
favorite, login), measured against the Node build at `30b68e1` on the same hardware and database. Roadmap slice 0
captures the baseline. Until it exists, the gate is "measure only".

## Steering Files

| File | Weight | Conflict | Resolution |
|------|--------|----------|------------|
| (none found) | — | — | — |

## Transition Concerns (Replacement)

The mode is Replacement, so there is no long-running coexistence. These rows still apply to the cutover window and rollback:

| Concern | Decision |
|---------|----------|
| Write ownership | One writer at a time. Node is drained (stopped) before Phoenix takes traffic. No dual writes |
| Schema authority | Frozen during the observation window. `_prisma_migrations` untouched; Ecto baseline after rollback retires |
| Identity | Two-way token compatibility (same secret, alg, claims, exp) so rollback keeps sessions |
| Jobs and events | None exist |
| Data movement | None. Same database, no ETL |
| Cutover | Rehearse on a prod snapshot; stop Node → deploy Phoenix → smoke the contract probes → observation window |
| Rollback | Redeploy the Node image against the same DB. Last reversible point: first Ecto DDL change |
