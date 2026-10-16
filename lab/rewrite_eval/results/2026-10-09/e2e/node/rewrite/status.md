# Rewrite Status

- **Phase:** roadmapped (ASSUMED) — 10 slices, all blocked; no seeds written, `/phx:plan` not run
- **Date:** 2026-10-09
- **Mode:** `--auto` (all defaults recorded as ASSUMED)
- **SOURCE:** `$S/testbeds/node-express-realworld`
- **Source sha:** `30b68e1e881462b2f4164ea09ab4c4f5699c7b0b` (master, clean, 1 commit)
- **Source tree fingerprint:** `655048838749423d`
- **TARGET:** `$S/e2e/node`
- **Target sha:** none (git repo, no commits)
- **Stack:** Node / Express + Prisma (PostgreSQL) + jsonwebtoken + bcryptjs — RealWorld "Conduit" JSON API
- **Stack pack:** `kb/stacks/node.md`
- **Scope:** whole app (66 files, ~2.4k TS LOC)

## Artifacts

| Artifact | State |
|----------|-------|
| `charter.md` | ok (5 ASSUMED) |
| `inventory/inventory.json`, `inventory/inventory.md` | ok |
| `kb/` | ok |
| `analysis/features.md` | ok — 16 capabilities, 14 triage decisions (all ASSUMED) |
| `analysis/mechanisms.md` | ok — 34 mechanisms, 5 `unknown` |
| `analysis/runtime.md` | ok — 1 web process, PostgreSQL only |
| `analysis/contracts.md` | ok — 40 contracts (11 data, 25 wire, 4 operational), 9 ADR-000 decisions |
| `architecture/ADR-000-compatibility-bar.md` | ASSUMED (needs approval) |
| `architecture/architecture.md`, `adr/ADR-001…014`, `decisions.md` | ok — 3 proposed, 11 ASSUMED, 0 accepted |
| `architecture/divergences.md` | 17 pending (DV-01…17) + 9 candidates |
| `architecture/consults/` | ecto-schema-designer, hex-library-researcher, security-analyzer |
| `roadmap.md` | 10 slices (00–09), all `blocked`; every ledger ID placed |
| `ledger.md` | 97 rows · MAP 27, REPLACE 11, KEEP 34, SHIM 8, DELETE 6, UNDECIDED 11 · check clean only with a patched `ledger.py` (plugin script crashes on `C-18a` sub-IDs, escaped `\|`, and the UNDECIDED summary table) |

## Open Questions

1. Demo-only visibility filter (M-11 / C-23 / F-06,F-11,F-12): product rule or hosted-demo artefact?
2. Favorite/unfavorite response leaks emails + bcrypt hashes (M-20 / C-21): approve fix as a wire change?
3. `JWT_SECRET` fallback `superSecret` (C-37): does production set it? Fail to boot without it?
4. `_UserFollows` A/B column direction (M-16): must be confirmed on real rows.
5. Cutover mode and `_prisma_migrations` / schema ownership (C-01, C-10).
6. Bug-for-bug vs spec-correct policy (403 login, 500s, tag wipe, comment quirks).
7. Is this deployment `api.realworld.io`? Who serves `/images/*`?
8. Unverified without running legacy: CORS preflight headers, ETag/304, slugify special-char output, Prisma 500 text.

## Coverage Gaps

- Legacy app not executed (Iron Law), so behaviour comes from reading code. Legacy tests are weak: unit tests mock Prisma, and the e2e test is stale.
- Git history has 1 squashed commit, so purposes come from code and comments only.
- No production config: host, DB provider, backups, CI.

## Next

Approve or revise the ASSUMED decisions in `roadmap.md` → **Unblock Order**, starting with ADR-000 A1/A3 and ADR-011.
Then run `/rewrite:roadmap --next`, which hands off slice 00 (`rewrite-00-foundation`) to `/phx:plan`.
