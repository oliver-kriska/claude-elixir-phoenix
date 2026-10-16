# Inventory: $S/testbeds/node-express-realworld

- git: `30b68e1e8814` on `master`, 1 commits, 2024-01-04 → 2024-01-04, 1 contributors
- tree fingerprint: `655048838749423d`
- stacks: express/koa/hapi (dep:express)
- shape hints (confirm in code): http-api
- size: 66 files; LOC typescript 2371, sql 163, javascript 3

## Infrastructure signals

- **auth** (auth): jsonwebtoken
- **orm** (data): @prisma/client, prisma

## Entry points

- controllers: 4 — src/app/routes/article/article.controller.ts, src/app/routes/auth/auth.controller.ts, src/app/routes/profile/profile.controller.ts, src/app/routes/tag/tag.controller.ts
- deployment: 1 — Dockerfile
- migrations: 5 — src/prisma/migrations/migration_lock.toml, src/prisma/migrations/20210924225358_initial/migration.sql, src/prisma/migrations/20211001143221_implicit_tags/migration.sql, src/prisma/migrations/20211105153605_api_url/migration.sql, src/prisma/migrations/20211221184529_deprecated_preview/migration.sql
- models: 1 — src/prisma/schema.prisma
- routes: 1 — src/app/routes/routes.ts
- tests: 16 — tsconfig.spec.json, e2e/.eslintrc.json, e2e/jest.config.ts, e2e/project.json, e2e/tsconfig.json …

## Mechanism hints (pattern counts — leads, not conclusions)

- crypto-contracts: 1 in 1 files — src/app/routes/auth/token.utils.ts

## Agent-steering files

- none found

## Git hotspots (top 10)

- e2e/jest.config.ts: 1 changes, 1 fix commits
- e2e/src/server/server.spec.ts: 1 changes, 1 fix commits
- e2e/src/support/global-setup.ts: 1 changes, 1 fix commits
- e2e/src/support/global-teardown.ts: 1 changes, 1 fix commits
- e2e/src/support/test-setup.ts: 1 changes, 1 fix commits
- jest.config.ts: 1 changes, 1 fix commits
- jest.preset.js: 1 changes, 1 fix commits
- src/app/models/http-exception.model.ts: 1 changes, 1 fix commits
- src/app/routes/article/article.controller.ts: 1 changes, 1 fix commits
- src/app/routes/article/article.mapper.ts: 1 changes, 1 fix commits

## Coverage and limits

- files walked: 66; skipped oversized/binary source files: 0
- why-comments: returned 0 of 0 (round-robin by file); TODO/FIXME/HACK: 0
- git commits scanned: 1
- regex hints are leads; absence of a hint is not absence of the mechanism
- tests, SQL, triggers and stored procedures are not scanned for mechanism hints
- dynamic dispatch, metaprogramming and generated routes need manual tracing
