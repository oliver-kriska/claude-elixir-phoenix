# ADR-011: Runtime configuration, secrets and CORS

**Status**: ASSUMED (env contract change inherited from ADR-000's Changed table) · **Date**: 2026-10-09

## Context
Legacy reads only `DJANGO_SETTINGS_MODULE`; `SECRET_KEY`, `DEBUG`, DB path and CORS origins are hard-coded (C-44, M-36). C-31 keeps the `:4000`
origins as runtime-configurable defaults. Security consult Q3, Q5.

## Decision
`config/runtime.exs` (prod) reads with `System.fetch_env!` and fails closed:

| Env | Rule |
|-----|------|
| `JWT_SECRET` | required, ≥32 bytes |
| `JWT_SECRET_PREVIOUS` | optional, verify-only |
| `SECRET_KEY_BASE` | required, ≥64 bytes, separate from `JWT_SECRET` |
| `DATABASE_PATH` | required; no relative default |
| `PHX_HOST`, `PORT` | both required, no default (legacy `runserver` used 8000; the operator picks the port, C-43 documents it) |
| `CORS_ORIGINS` | optional; comma list of full origins; `*` rejected; default `http(s)://localhost:4000`, `http(s)://0.0.0.0:4000` |

No secret via `Application.compile_env`. Dev/test configs hold obviously fake values. `debug_errors: false` and no `Plug.Debugger` outside dev.
Corsica 2.1.3 in the Endpoint before the router; `allow_credentials: false`; allow headers include `authorization`, `content-type`.

## Guarantees
- Kept: C-31 origins (as defaults).
- Changed: C-44 env contract (DV-06), C-34 debug pages (DV-05). Consumers: operators.

## Alternatives
Deriving the JWT key from `SECRET_KEY_BASE`: couples rotations; rejected.

## Consequences
A release with a missing secret does not boot. Observability (error tracker) stays open (OD-7).

## Validation
Boot tests with each required var missing; VO-09 preflight tests; `rg` finds no committed secret.

## Ledger IDs
C-44, M-36, C-34, M-31, C-31, R-30, M-06, C-14
