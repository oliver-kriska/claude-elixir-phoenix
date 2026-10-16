# ADR-000: Compatibility Bar

**Status**: ASSUMED (auto, needs approval)
**Date**: 2026-10-09 · **Source**: $S/testbeds/django-realworld @ 29c9d42831fa · **Decided by**: --auto

## Assumptions (only when ASSUMED)

- **Cutover = Replacement.** Rule: runtime.md shows one deployable (R-01) and one database (R-10).
- **Data = Keep schema as-is.** Rule: always. Engine stays SQLite (`ecto_sqlite3`) because that is the legacy engine (R-10, C-42). Moving to Postgres is an open decision (runtime Q1), not a default.
- **Identity = Keep hashes, one re-login.** The default would be "keep sessions and hashes", but the security-defect rule overrides it for tokens. The JWT key is the committed `SECRET_KEY` (C-14), so legacy tokens are not accepted after cutover. Password hashes are kept (C-02).
- **Clients = No UI; keep the wire protocol.** Rule: the shape is http-api with no UI. The RealWorld JSON API under `/api` is kept as a contract.
- **`contract` items: keep.** Rule: a consumer is evidenced (RealWorld frontends, the README, operators).
- **`incidental` items: relax**, each with a `pending` divergence. No SHIM is built for them.
- **`defect` items: UNDECIDED.** Each one blocks only its own slice.
- **Security defects (C-14, C-15, C-32, C-33, C-34): change toward safe behaviour**, ASSUMED, with a `pending` divergence. They block the handoff of their slice.
- **Rollback window: bounded**, until the first approved destructive DDL and at most one release cycle. Open decision.
- **Performance goal: no regression vs a measured legacy baseline.** Slice 0 measures the baseline.
- **Steering: charter wins.** No steering files exist (charter.md).
- **Production data assumed to exist.** Q2 is unanswered, so the bar takes the conservative choice of carrying an existing `db.sqlite3` over intact.

## Cutover Mode

**Replacement.** There is one Django process (R-01) on one SQLite file (R-10), with no queues, cron, background work or second writer (runtime.md). Traffic moves in one maintenance window: stop legacy, copy `db.sqlite3`, start the Phoenix release on the same file (schema kept as-is), then smoke-test. Rollback means restoring the pre-cutover file copy and restarting legacy, valid until the first approved destructive DDL. Both runtimes never write at the same time, so the transition-contract table does not apply. The one cross-runtime concern is identity: all clients log in again once (see Identity).

## Kept Contracts

| Contract | Surface | Class | Disposition | Consumers | Witness |
|----------|---------|-------|-------------|-----------|---------|
| C-01 legacy tables and columns readable, M2M direction intact | data | contract | keep | existing install | analysis/contracts.md C-01 |
| C-02 Django `pbkdf2_sha256$30000$…` hashes verify | data | contract | keep (verify; new-hash format is a design ADR) | every existing user (no reset flow) | contracts.md C-02 |
| C-03 UTC timestamps, legacy SQLite text format round-trips, port rows sort correctly with legacy rows | data | contract | keep | list ordering | contracts.md C-03 |
| C-04 uniqueness: username, email, slugs, pair tables | data | contract | keep (case policy unchanged: case-sensitive) | DB integrity | contracts.md C-04 |
| C-05 every user has exactly one profile | data | contract | keep, made atomic (strengthening) | every authenticated view | contracts.md C-05, M-01 |
| C-06 existing slugs stay valid; generation format; slug fixed on title edit | data | contract | keep | bookmarked URLs | contracts.md C-06 |
| C-07 tag display text plus `slug = lower(tag)`; oversize legacy values tolerated | data | contract | keep | tag filters | contracts.md C-07 |
| C-10 `Authorization: Token <jwt>`; case-insensitive prefix; malformed header = anonymous | wire | contract | keep | RealWorld frontends | contracts.md C-10 |
| C-11 JWT shape HS256 `{id, exp}`, 60-day expiry | wire | contract | keep the shape and lifetime; **the key changes** (see C-14) | frontends storing tokens | contracts.md C-11 |
| C-12 stateless tokens; fresh token on login, register, GET/PUT user | wire | contract | keep | frontends | contracts.md C-12 |
| C-13 login request, response and error texts | wire | contract | keep | sign-in form | contracts.md C-13 |
| C-17 route table under `/api/` (slash-optional set) | wire | contract | keep the listed paths. Accepting a trailing slash on routes where legacy rejects it is relaxed (Phoenix default; divergence pending) | frontends | contracts.md C-17 |
| C-18 wrapped request bodies | wire | contract | keep | frontends | contracts.md C-18 |
| C-19 response envelopes | wire | contract | keep | frontends | contracts.md C-19 |
| C-20 article object fields, no `id`, `tagList` order | wire | contract | keep (`tagList` order to be verified, see status.md open) | frontends | contracts.md C-20 |
| C-21 profile object with smiley image fallback | wire | contract | keep | frontends | contracts.md C-21 |
| C-22 user object with raw `image` | wire | contract | keep | frontends | contracts.md C-22 |
| C-23 comment object; paging at 20 + `commentsCount`; unknown slug → 200 empty | wire | contract | keep | comment UI | contracts.md C-23 |
| C-24 article list params, ordering, no max `limit`; feed envelope | wire | contract | keep | home page | contracts.md C-24 |
| C-25 status-code table (201 on favorite and follow, 204 on comment delete, 400 validation) | wire | contract | keep | frontends | contracts.md C-25 |
| C-26 error envelopes (400 field map, `error` key, list for self-follow, model-keyed vs `detail` NotFound) | wire | contract | keep, frozen by golden files | frontends | contracts.md C-26 |
| C-27 input validation rules (password 8–128, any username chars, email ≤254) | wire | contract | keep | register and settings forms | contracts.md C-27 |
| C-28 idempotent favorite and follow toggles | wire | contract | keep | buttons | contracts.md C-28 |
| C-29 partial article update; `tagList` replaces the set; client-writable slug | wire | contract | keep (after C-32, only the author can write) | editor | contracts.md C-29 |
| C-30 ISO 8601 timestamps with explicit UTC offset | wire | contract | keep (exact text relaxed, C-49) | frontends | contracts.md C-30 |
| C-31 CORS origins `localhost:4000`, `0.0.0.0:4000`; no credentials | wire | contract | keep as runtime-configurable defaults | dev frontend | contracts.md C-31 |
| C-42 data at `db.sqlite3`; the port's migration ledger must not clash with `django_migrations` | operational | contract | keep (Ecto `migration_source` separate) | existing install | contracts.md C-42 |
| C-43 operator bootstrap: migrate, run, create superuser | operational | contract | keep as equivalents: release `migrate`, `start`, and a create-user `eval` task | operators | contracts.md C-43 |

## Changed or Retired Contracts

| Contract | Change | Consumers affected | Approval |
|----------|--------|--------------------|----------|
| C-11 token key | Tokens are signed with a new secret read from the environment. Legacy-signed tokens are rejected (403 under the C-16 status quo), so every client logs in once | every logged-in client | ASSUMED (consequence of C-14) |
| C-44 env contract | Required runtime env added: JWT secret, `SECRET_KEY_BASE`, DB path, CORS origins, `PHX_HOST`. `DJANGO_SETTINGS_MODULE` is retired | operators | ASSUMED (consequence of C-14, C-34) |

## Incidental Behaviour

| Item | Legacy default | Disposition (relax / keep with consumer) | Divergence |
|------|----------------|------------------------------------------|------------|
| C-45 DRF API root, format suffixes, `?format=` | DRF DefaultRouter | relax (dropped) | pending |
| C-46 browsable HTML API | DRF renderers | relax (JSON only) | pending |
| C-47 DRF `OPTIONS` metadata | DRF SimpleMetadata | relax (CORS preflight only) | pending |
| C-48 Django HTML 404 and APPEND_SLASH redirects | Django | relax (JSON 404) | pending |
| C-49 exact `isoformat()` timestamp text | Python | relax (ISO 8601 with UTC offset; C-30 kept) | pending |
| C-50 JSON byte formatting | json.dumps / DRF | relax (Jason) | pending |
| C-51 `X-Frame-Options: SAMEORIGIN` | Django middleware | relax (Phoenix secure headers) | pending |
| C-52 Django admin and its sessions/CSRF | contrib.admin | relax (retired; C-43 equivalent kept) | pending; operator use is unknown (M-33) |
| C-53 framework tables (`django_session`, `auth_*`, …) | contrib apps | relax (left in place unmapped; no DDL) | pending |
| C-54 `PATCH /api/user` = PUT | DRF | relax (PUT only) | pending |
| C-55 `is_staff`/`is_superuser`/`last_login` semantics | Django auth | relax (columns kept and written with legacy defaults, no behaviour) | pending |
| C-56 per-route slug regex differences | Django/DRF regex | relax (one slug matcher) | pending |

## Defects

| Contract | Defect | Security? | Disposition (UNDECIDED / change → safe) | Divergence | Blocks slice |
|----------|--------|-----------|-----------------------------------------|------------|--------------|
| C-14 | committed `SECRET_KEY` is the JWT key → token forgery | yes | change → new env-supplied secret; legacy tokens rejected — ASSUMED | pending | auth slice |
| C-15 | JWT decode does not pin the algorithm | yes (token-forgery class) | change → HS256 only — ASSUMED | pending | auth slice |
| C-32 | any user can update any article | yes (authz bypass) | change → author-only, 403 otherwise — ASSUMED | pending | article-write slice |
| C-33 | any user can delete any comment; slug ignored | yes (authz bypass) | change → comment author only, scoped to the URL's article — ASSUMED | pending | comments slice |
| C-34 | `DEBUG=True`: technical 404/500 pages leak URLs, settings and tracebacks | yes (information exposure) | change → JSON errors, no debug pages in prod — ASSUMED | pending | foundation slice |
| C-08 | case-variant tag → 500 | no | UNDECIDED | — | article-write slice |
| C-09 | slug collision not retried → 500 | no | UNDECIDED | — | article-write slice |
| C-16 | auth failures 403 not 401; bad token refused on public endpoints | no | UNDECIDED | — | auth slice |
| C-35 | `/api/articles/feed` shadowed by detail route | no | UNDECIDED (the Phoenix router fixes it by default; needs a decision) | — | feed slice |
| C-36 | no article DELETE (405) | no | UNDECIDED | — | article-write slice |
| C-37 | `PUT /api/user` ignores password and image | no | UNDECIDED | — | account slice |
| C-38 | self-follow guard fails for pk ≥ 257 | no | UNDECIDED (plus legacy self-follow rows: purge or keep) | — | follow slice |
| C-39 | `\w+` profile route vs any-char usernames | no | UNDECIDED | — | profile slice |
| C-40 | register/login omit `bio`/`image` | no | UNDECIDED | — | auth slice |
| C-41 | crashes on input (comment `author` key, non-object JSON body) | no | UNDECIDED | — | foundation/comments slices |

## Data

Keep the legacy schema as-is. Ecto schemas map the existing Django tables with explicit `source`, `join_through` and column names (C-01, M-40). DDL authority moves to Ecto at cutover. Its migration ledger is a separate `migration_source` that never touches `django_migrations` (C-42). No destructive DDL without a new ADR; framework tables are left in place (C-53). The engine stays SQLite through `ecto_sqlite3`, single node, one writer. A move to Postgres is open (runtime Q1) and would become ETL plus a new ADR. Legacy timestamp text must round-trip and sort with port-written rows (C-03). No file storage exists.

## Identity

- The Phoenix app issues and reads tokens. They stay HS256 JWTs with payload `{id, exp}` and a 60-day lifetime (C-11, C-12), signed with a new secret from the environment and verified with the algorithm pinned to HS256 (C-14, C-15).
- Legacy tokens stop working at cutover, so every client logs in once.
- Password hashes: legacy `pbkdf2_sha256$30000$…` hashes must verify (C-02). Whether new or rehashed passwords use the Django format or a native one is a design ADR.
- Revocation stays as it is in legacy: stateless, with only `is_active` (C-12). Stronger revocation is open (contracts Decision 9).

## Clients and UI

There is no UI. The RealWorld JSON API under `/api` must keep working unchanged for existing frontends: paths, envelopes, status codes and error shapes as listed under Kept Contracts. Changes come only from approved defect and security dispositions. LiveView does not apply.

## Performance Goal

No regression against a measured legacy baseline: p95 latency and throughput for the article list (`limit=20`), single article, feed, and login, on the same SQLite dataset and machine. Roadmap slice 0 measures the baseline. Running legacy requires an isolated copy and the user's permission (contracts Q7), because analysis never executes SOURCE.

## Steering Files

| File | Weight | Conflict | Resolution |
|------|--------|----------|------------|
| none | — | — | charter wins |

## Transition Concerns (staged cutover or coexistence)

Not applicable: cutover is Replacement and only one runtime writes at a time. The cutover runbook still has to cover the following in the release-rehearsal slice:
- the forced re-login;
- the pre-cutover `db.sqlite3` copy as the rollback point;
- a pre-cutover data scan for orphan rows, self-follows (C-38), case-variant emails (C-04), oversize tag slugs (C-07), and users without a profile (C-05).
