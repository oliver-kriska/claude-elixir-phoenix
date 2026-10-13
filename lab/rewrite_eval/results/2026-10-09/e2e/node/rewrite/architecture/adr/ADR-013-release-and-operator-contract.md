# ADR-013: Mix release, env translation and operator command mapping

**Status**: ASSUMED (`--auto`; changes operator commands and env handling)
**Date**: 2026-10-09 · **Depends on**: ADR-000 A1, ADR-003, ADR-011

## Context

Operators currently work like this (C-37, C-38, M-27, M-28, R-01..R-05, R-24):

- Build with Nx and esbuild, then run `node api` in a non-root `node:lts-alpine` container on port 3000.
- Apply DDL with `npx prisma migrate deploy` and seed with `npx prisma db seed`.
- Set `DATABASE_URL`, `JWT_SECRET`, `PORT` (default 3000) and `NODE_ENV`.
  - `DATABASE_URL` may carry Prisma-only query params (`connection_limit`, `schema`, ...) (runtime.md).
  - `NODE_ENV` only toggles a Prisma dev singleton.
  - The Dockerfile sets `HOST`, which the app never reads.
- Logging is one `console.info` boot line (C-40).

## Decision

- **Packaging:** `mix release` and a Dockerfile from `phx.gen.release --docker`, with a non-root user and port 3000.
  The Elixir, OTP and base-image versions are marked `verify` (not in KB).
- **Env (`config/runtime.exs`):**
  - `DATABASE_URL`, `JWT_SECRET` (ADR-011) and `PORT` (default 3000) keep their names.
  - `Realworld.Compat.DatabaseUrl` translates the Prisma params:
    - `connection_limit` becomes `pool_size`, unless `POOL_SIZE` is set
    - `schema` must be `public` or absent, and the release refuses to boot otherwise
    - `sslmode` maps to Postgrex `ssl` options
    - other Prisma-only params are stripped with a boot warning
  - New: `POOL_SIZE` and `ECTO_DDL_OWNER` (ADR-003), plus whatever the generated release config requires
    (`PHX_SERVER`, `SECRET_KEY_BASE`, `PHX_HOST`; verify in S1).
  - `NODE_ENV` and `HOST` are dropped.
- **Command mapping:**

  | Legacy | Elixir |
  |--------|--------|
  | `node api` / `node dist/api/main.js` | `bin/realworld start` (`PHX_SERVER=true`) |
  | `npx prisma migrate deploy` | `bin/realworld eval "Realworld.Release.migrate()"`. Refuses until `ECTO_DDL_OWNER=true` (ADR-003). During the window, DDL is nobody's job |
  | `npx prisma db seed` | `bin/realworld eval "Realworld.Release.seed()"` (non-idempotent, like legacy) |
  | `GET /` probe | unchanged |

- **Logging:** `Logger` and `Plug.Telemetry` request logs replace the single boot line. `password`, `token` and
  `authorization` are filtered (C-40 relax, DV-09).
- The seed goes through context functions, so passwords, slugs and timestamps keep the legacy format. `demo = true`
  and the demo avatar are set through a seed-only path (C-39).

## Guarantees

| Guarantee | Kept / changed | Consumers |
|-----------|----------------|-----------|
| Env names `DATABASE_URL`, `JWT_SECRET`, `PORT`, port 3000 | kept | operators, host config |
| Non-root container | kept | security |
| Operator commands | **changed** (DV-12) | operators, deploy scripts |
| `NODE_ENV` and `HOST` honoured | **dropped**. Neither had a runtime effect in prod (DV-13) | none |
| Prisma URL params | **translated**. Unknown params are stripped with a warning (DV-13) | operators |
| Log output | **changed** to per-request logs (DV-09) | operators, log pipelines |

## Alternatives

- **Keep a `prisma` CLI in the image for migrations.** Rejected: it brings Node back into operations, and no DDL runs
  during the window anyway.
- **Run migrations automatically at boot.** Rejected: that is DDL during the window (ADR-003).

## Consequences

- Deploy scripts and runbooks must be updated at cutover. The command table is the migration guide.
- A `DATABASE_URL` with a non-`public` `schema` fails the boot loudly instead of being silently ignored.

## Validation

- `Compat.DatabaseUrl` unit tests over sample Prisma URLs (with `connection_limit`, `schema=public`, `sslmode=require`,
  and an unknown param).
- S8 smoke test: the release boots with only the legacy env names (plus the required Phoenix ones). `GET /` → 200.
- Log check: no `authorization` header value or password appears in request logs.

## Ledger IDs

M-26, M-27, M-28, R-01, R-02, R-03, R-04, R-05, R-24, C-37, C-38, C-39, C-40
