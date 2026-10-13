# Rewrite Charter

Source: `node-express-realworld` (Express + Prisma + JWT, RealWorld "Conduit" API)
Created: 2026-10-09 by `/rewrite:analyze --auto`

## Goals

- ASSUMED: maintainability (single idiomatic Phoenix codebase replacing Express/Nx/Prisma)
- ASSUMED: preserve the public HTTP API so existing RealWorld front-ends keep working

## Constraints

- ASSUMED: no hard deadline
- ASSUMED: team Elixir experience — intermediate
- ASSUMED: must-keep integrations — the RealWorld API contract (JSON shapes, `Authorization: Token <jwt>` header) and the existing PostgreSQL schema/data

## Scope

- Whole app (66 files, ~2.4k TS LOC — under the 1,500-file threshold, no domain split needed)

## Steering files

- none found in SOURCE or TARGET

## Assumptions

Every value marked `ASSUMED:` above was written by `--auto` and needs approval:

1. Goal: maintainability
2. Goal: preserve the public HTTP API for existing clients
3. No hard deadline
4. Team Elixir experience: intermediate
5. Must-keep: RealWorld API contract + existing PostgreSQL schema/data
