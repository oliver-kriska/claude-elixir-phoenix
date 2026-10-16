# ADR-006: Express HTTP semantics live in named edge SHIMs

**Status**: ASSUMED (`--auto`; permanent wire adapters with a real cost)
**Date**: 2026-10-09 · **Depends on**: ADR-000 A4, A5

## Context

ADR-000 keeps the wire byte-compatible. Express 4.18.2 and its middleware behave in ways Phoenix and Plug do not by
default:

- `cors()` 2.8.5 treats every `OPTIONS` as a preflight → 204, and sends `Access-Control-Allow-Origin: *`
  everywhere (C-31).
- body-parser 1.20.2 parses JSON and qs-extended urlencoded bodies up to 100 kb (C-32). Its errors go to the legacy
  500 path, covered separately in ADR-014.
- `res.send` adds a weak SHA-1 ETag to every body, answers 304 on a fresh GET or HEAD, and sends
  `X-Powered-By: Express` (C-35).
- Literal path segments match case-insensitively, and a trailing slash is optional (C-36a, M-03).
- Unknown paths and wrong methods get the HTML page `Cannot <METHOD> <path>` with status 404 (C-33).

The hex-library-researcher consult checked `cors_plug`, `corsica` and `etag_plug`. None of them matches.

## Decision

Project-owned plugs under `RealworldWeb.Compat`, in the endpoint order from architecture.md section 4:

| Module | Behaviour | Approx. size |
|--------|-----------|--------------|
| `ExpressHeaders` | `register_before_send`: weak ETag `W/"<len hex>-<base64(sha1)[0..26]>"` on every body. 304 for fresh GET/HEAD 2xx. `X-Powered-By: Express`. Drops Plug's default `cache-control` and `x-request-id` | ~40 lines |
| `ExpressCors` | Every `OPTIONS` → 204 with Allow-Origin `*`, Allow-Methods `GET,HEAD,PUT,PATCH,POST,DELETE`, `Vary: Access-Control-Request-Headers`, and the requested headers reflected when present; then halt. Every other method gets only ACAO `*` | ~25 lines |
| `ExpressBodyParser` | Wraps `Plug.Parsers` `[:urlencoded, :json]` with `length: 102_400` and `pass: ["*/*"]`. Error mapping per ADR-014. A `_json`-wrapped non-object body follows the missing-envelope path | ~30 lines |
| `ExpressPathCase` | Lowercases literal segments only, at the positions where the route table has literals. Param values keep their case | ~40 lines |
| `NotFound` | Catch-all `match :*` → Express HTML 404 body | ~10 lines |

`Plug.Head` handles HEAD for GET routes. `Plug.MethodOverride`, `Plug.Session` and `:accepts` are deliberately
left out, because each would create behaviour legacy does not have (a 406, for example).

**Owner:** the `Web` owner. **Support policy:** permanent while any third-party RealWorld client is supported.
Each SHIM can be retired on its own through a later ADR, once access logs (V-5) show no client depends on it.
`ExpressHeaders` (ETag/304) is the first candidate. Dropping it only costs bandwidth.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|-----------|----------------|-----------|
| CORS headers byte-equal, preflight 204 | kept | browser SPAs |
| A 401 or error response still carries ACAO `*` (CORS runs first) | kept | browser SPAs |
| JSON and form bodies up to 102,400 bytes | kept | clients, form login |
| qs edge cases (duplicate keys → array, `a[0]` → array, 1000-param limit) | **changed** (DV-10) | none known (legacy then 500s in Prisma) |
| Non-object top-level JSON, `+json` content types | **changed** (DV-08) | none known |
| Weak ETag and 304 | kept | caches, proxies |
| `/API/Articles` matches | kept | clients with odd casing (V-5) |
| Static file cache headers (`Plug.Static` vs serve-static) | **changed** (DV-11) | browsers caching avatars |

## Alternatives

- **`cors_plug` or `corsica`.** Rejected: neither reproduces the preflight (status, `Vary`, `Max-Age`, the
  OPTIONS-without-ACRM case).
- **`etag_plug`.** Rejected: it is stale and uses strong hex tags.
- **Port `qs` exactly.** Rejected: the cost is high, and every divergent input already ends in a legacy 500.
- **Drop the Express headers and accept the diffs.** A valid future choice. Under A5 the default is keep.

## Consequences

- Every response body is SHA-1 hashed. This is a profiled hotspot candidate (performance plan, P2).
- Router changes must keep `ExpressPathCase`'s literal table in sync. It is derived from the router at compile time
  so the two cannot drift.

## Validation

Header-diff harness against goldens captured from the pinned legacy build (needs V-0):

- `OPTIONS` with and without `Origin` and ACRM
- a 401 on a required route
- `If-None-Match` → 304
- `/API/ARTICLES`
- a trailing slash
- an unknown path and a wrong method
- a form-encoded login
- a 102,401-byte body

## Ledger IDs

M-01, M-02, M-03, M-04, R-21, R-26, R-27, C-31, C-32, C-33, C-34, C-35, C-36, C-36a
