# Divergences

**Source:** `node-express-realworld` @ `30b68e1e8814` · **Date:** 2026-10-09 · **Mode:** `--auto`

This file lists every place where the Elixir design deliberately behaves differently from the legacy app. Each row
has `Approval: pending`. None is approved.

- "Legacy" behaviour comes from reading the code and the library source. Nothing was executed, so a row marked
  *(source-read)* still needs a characterization golden (V-0).
- Surfaces: `wire` = HTTP clients see it · `data` = rows or DB state · `operational` = operators or deploys.

## Pending divergences (current design)

| ID | Surface | Ledger | ADR | Legacy behaviour | New behaviour | Reason | Client / consumer impact | Approval |
|----|---------|--------|-----|------------------|---------------|--------|--------------------------|----------|
| DV-01 | wire | C-32a, M-02, R-27 | ADR-014 | Malformed JSON → 500 with the V8 `SyntaxError` text as a JSON string. Oversized body → 500 `"request entity too large"` *(source-read; the contract text says 413)* | Status follows V-0 characterization (500 by default). Malformed-JSON body is the generic 500 string. Deterministic messages are reproduced | The V8 text cannot be reproduced and already drifts with the unpinned `node:lts-alpine` image | Low: only clients that parse the parser error text. Status class unchanged | pending |
| DV-02 | wire | M-10, M-13, R-12, C-05 | ADR-008, ADR-003 | Register or slug **race loser** (both pre-checks pass, insert hits the unique index) → Prisma P2002 500 | Same 422 as the happy-path duplicate (`email: has already been taken`, `title: must be unique`) via `unique_constraint(name: ...)` | Correct field error. Removes a 500 that leaks constraint names | Improvement. Visible only under concurrent duplicate submits | pending |
| DV-03 | wire | C-19a, M-06, R-28 | ADR-008 | Unhandled errors → 500 with the Prisma, V8 or slugify message as a JSON string | 500, `application/json`, fixed `"Internal Server Error"` JSON string. Real error logged server-side with the request id | Prisma text cannot be reproduced by Ecto. The legacy text leaks model and field names (CWE-209) | Low: clients branch on status (C-19). Anyone parsing the text loses it | pending |
| DV-04 | data | M-14, M-15, C-27 | ADR-012 | Article update wipes tag links, then updates in a **separate** statement, so a failure in between loses the tags. No row lock. Concurrent creates with the same new tag can 500 on `Tag_name_key` | One `Ecto.Multi` with `FOR UPDATE`: a failure rolls back and the tags survive. Concurrent PUTs serialise. Tag upsert with `on_conflict: :nothing` makes concurrent creates succeed | Removes silent data loss and a race 500. Successful-path results are identical, including the wipe on omit | Improvement. None on success paths | pending |
| DV-05 | wire (timing) | M-09, C-18a | ADR-005 | Unknown email at login → fast 403 with no bcrypt work, so response time enumerates accounts | Unknown email costs one bcrypt-10 (`Bcrypt.no_user_verify/1`). Same 403 status and body | Closes the cheapest user-enumeration oracle | None on status or body. Login p95 for unknown emails rises to the wrong-password cost | pending |
| DV-06 | wire | C-12, M-08 | ADR-004 | Token payload serialised `{"user":{...},"iat":..,"exp":..}` (jsonwebtoken key order) | Jason serialises the claims in `exp, iat, user` order. Claims, header, algorithm and signature validity are identical. Bytes differ | Library serialisation. Verification is unaffected on both runtimes | None for clients that verify or decode. Anyone comparing token strings byte-for-byte (none known) | pending |
| DV-07 | wire | C-12, C-14, M-08 | ADR-004 | A correctly signed token **without `exp`** is accepted forever | 401 with the legacy body | No legitimate token lacks `exp`. Deny-only hardening (security consult Q1) | Only forged or hand-made tokens. Legacy never mints one | pending |
| DV-08 | wire | C-32, M-02 | ADR-006 | body-parser strict JSON: a top-level scalar → 500 (SyntaxError). A top-level array stays an array. Only exactly `application/json` is parsed *(source-read)* | Plug wraps non-object JSON as `%{"_json" => v}`, which takes the endpoint's missing-envelope path (register 422; login and comment 500 per C-19a). `application/*+json` may also be parsed (verify) | Plug.Parsers semantics. Matching strict mode needs extra code with no known consumer | Low: malformed client requests only. Register with a scalar body gets 422 instead of 500 | pending |
| DV-09 | operational | C-40, R-24 | ADR-013, ADR-000 | One `console.info` boot line. No request logs | `Logger` + `Plug.Telemetry` request logs. `password`, `token` and `authorization` filtered | Operability. No consumer depends on silence | Operators and log pipelines see new volume. No client impact. Already listed as an ASSUMED relax in ADR-000 | pending |
| DV-10 | wire | C-32, M-02 | ADR-006, ADR-014 | qs 6.11 extended parsing: `a=1&a=2` → array, `a[0]=x` → array, more than 1000 params → 500 `"too many parameters"` *(source-read)* | `Plug.Conn.Query`: last value wins, `a[0]` → `%{"0" => ..}`, no parameter limit | Porting qs costs a lot. Every divergent input already ends in a legacy Prisma 500 | Low: form-encoded clients sending duplicate or indexed keys (V-5 access logs) | pending |
| DV-11 | wire | C-34, M-04, R-15, R-21 | ADR-006 | `express.static` (serve-static) headers: `Cache-Control: public, max-age=0`, `Last-Modified`, weak ETag from size and mtime, `Accept-Ranges` *(source-read, verify)* | `Plug.Static` headers (its own ETag and cache-control). Same bytes, paths and content type | Byte and content-type parity is the contract. Header parity on static files has no known consumer | Low: browser cache revalidation behaviour for two avatar images | pending |
| DV-12 | operational | C-38, R-02, R-04, R-05, M-25 | ADR-013, ADR-003 | `node api`, `npx prisma migrate deploy`, `npx prisma db seed` | `bin/realworld start`, `bin/realworld eval "Realworld.Release.migrate()"` (refuses until `ECTO_DDL_OWNER=true`), `bin/realworld eval "Realworld.Release.seed()"` | The Node toolchain leaves the image. DDL is frozen during the window | Operators: deploy scripts and runbooks must change at cutover | pending |
| DV-13 | operational | C-37, M-27 | ADR-013 | `NODE_ENV` and `HOST` read (no prod effect). Prisma reads `DATABASE_URL` query params (`connection_limit`, `schema`, ...) | `NODE_ENV` and `HOST` ignored. `Compat.DatabaseUrl` translates `connection_limit` → `pool_size`, refuses a non-`public` `schema`, strips unknown params with a warning. New vars: `POOL_SIZE`, `ECTO_DDL_OWNER`, plus Phoenix release vars (verify in S1) | Ecto/Postgrex do not understand Prisma params | Operators: env manifests gain vars. A non-`public` schema now fails boot instead of working | pending |
| DV-14 | data / operational | C-10, M-25, R-11 | ADR-003 | Prisma Migrate owns DDL via `_prisma_migrations` | Frozen during the window. After rollback retires, the Ecto baseline creates `ecto_schema_migrations`, and the Prisma CLI must never run against the DB again. `_prisma_migrations` kept until later retirement | One DDL owner after Node is gone | Operators. Once the baseline runs, Node rollback is no longer cheap (last reversible point) | pending |
| DV-15 | data / wire | C-11, M-13 | ADR-007 | Slugs from slugify 1.6.6 on the Node ICU Unicode tables | Port on OTP's `:unicode` NFC. Byte-equal on the golden corpus. Exotic code points whose NFC differs between ICU and OTP versions may slug differently | No Node runtime in the target | Authors using rare scripts. A differing slug changes a new article's URL. Existing slugs are stored and unaffected | pending |
| DV-16 | data | C-04, R-13, M-17 | ADR-003 | `createdAt`/`updatedAt` filled by Prisma or the DB default `CURRENT_TIMESTAMP` (session timezone) | Phoenix always sends app-clock UTC values floored to the ms, with Repo session `timezone: "UTC"` | Deterministic ms precision regardless of DB timezone | None if V-2 confirms the DB session timezone is UTC. Otherwise new rows are UTC while legacy rows are local time (to be resolved by V-2 before cutover) | pending |
| DV-17 | wire | C-12, C-19a, M-07 | ADR-004 | A validly signed token whose `user.id` is not an integer → Prisma 500 on use | 401 with the legacy body | Fail closed on a malformed identity | None legitimate: producing such a token requires the secret | pending |

**Pending count: 17** (wire 10, data 3, operational 3, data/operational 1. DV-15 counts as data).

## Candidate divergences (only if an UNDECIDED row resolves to "change")

These do not exist in the current `--auto` design, which keeps legacy behaviour. Each becomes a `DV-` row when the user
approves the change.

| ID | Ledger | ADR | Change under consideration | Consumers |
|----|--------|-----|----------------------------|-----------|
| CDV-01 | C-21, M-20 | ADR-009 | Strip `email`, `password` and `demo` from `favoritedBy`, or return the standard `ArticleJSON` (recommended) | Clients reading `favoritedBy`, `id` or `authorId` |
| CDV-02 | C-23, M-11 | ADR-010 | Drop or make configurable the demo-only visibility rule | Every viewer of list, comments and tags |
| CDV-03 | C-37a | ADR-011 | Refuse to boot in prod without a strong `JWT_SECRET`. Rotate if prod uses `superSecret` | Operators. Rotation would log out users on Node rollback |
| CDV-04 | C-18a | ADR-008 | Bad login 403 → 401 or 422 | Client error handling |
| CDV-05 | C-26 | ADR-008 | Comment POST 201, unknown-slug list 404, DELETE checks `:slug` | Client status checks |
| CDV-06 | C-27 | ADR-008, ADR-012 | Omitting `tagList` keeps existing tags | Editors that omit `tagList` |
| CDV-07 | C-30 | ADR-005, ADR-008 | Trim the password on `PUT /user`. Duplicate email or username → 422 instead of 500 | Settings page |
| CDV-08 | C-15, C-19a | ADR-004 | Token of a deleted user → 401 instead of 500 (user load per request) | Clients of deleted accounts |
| CDV-09 | C-18 (new) | ADR-005 | Rate limit login and register (429 is new on the wire) | Clients, attackers |
