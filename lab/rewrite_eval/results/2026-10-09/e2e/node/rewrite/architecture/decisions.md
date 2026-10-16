# Decisions Index

**Source:** `node-express-realworld` @ `30b68e1e8814` · **Date:** 2026-10-09 · **Mode:** `--auto`
No ADR is `accepted`. `ASSUMED` means `--auto` took a consequential trade-off that needs the user's approval.
`proposed` means a conventional choice with no wire, security, identity or schema-ownership trade-off.

| ADR | Status | Decision (one line) | Governs (ledger IDs) | Divergences |
|-----|--------|---------------------|----------------------|-------------|
| [ADR-000](ADR-000-compatibility-bar.md) | ASSUMED | Replacement cutover, schema kept, sessions and hashes kept, no UI, keep every wire contract, no-regression perf goal | every C- row's disposition | DV-09 (C-40 relax) |
| [ADR-001](adr/ADR-001-thin-phoenix-json-api.md) | proposed | One Phoenix JSON release. No Oban, PubSub, LiveView or cache. Empty process table | R-01, R-06, R-14, M-24, M-28, M-31 | — |
| [ADR-002](adr/ADR-002-context-boundaries.md) | proposed | Three contexts by invariant: Accounts, Profiles (follow graph), Articles (articles, comments, tags, favorites) | M-12, M-16, M-23, M-32, C-03, C-24, C-28 | — |
| [ADR-003](adr/ADR-003-keep-prisma-schema-ddl-authority.md) | ASSUMED | Map the Prisma schema unchanged. Zero DDL in the observation window. Assert-don't-create Ecto baseline afterwards | M-16, M-17, M-18, M-25, M-33, R-04, R-10, R-11, R-12, R-13, C-01, C-03..C-10 | DV-14, DV-16 |
| [ADR-004](adr/ADR-004-legacy-jwt-and-auth-plug.md) | ASSUMED | Joken HS256 `{user:{id}}` 60-day tokens, valid on both runtimes. Fail-closed `Plugs.Auth` with no user lookup | M-07, M-08, M-32, R-29, C-12..C-17 | DV-06, DV-07, DV-17 |
| [ADR-005](adr/ADR-005-bcryptjs-compatible-passwords.md) | ASSUMED | `bcrypt_elixir` `$2a$10$` (`legacy: true`), JS trim on register and login only, `no_user_verify` on unknown email, no rehash | M-09, M-10, C-02, C-18a, C-30 | DV-05 |
| [ADR-006](adr/ADR-006-express-http-edge-shims.md) | ASSUMED | Permanent `RealworldWeb.Compat` SHIMs: ExpressHeaders, ExpressCors, ExpressBodyParser, ExpressPathCase, NotFound | M-01..M-04, R-21, R-26, R-27, C-31..C-36, C-36a | DV-08, DV-10, DV-11 |
| [ADR-007](adr/ADR-007-slugify-port.md) | proposed | In-repo, golden-tested port of slugify 1.6.6. No Hex slug library | M-13, C-11, C-25 | DV-15 |
| [ADR-008](adr/ADR-008-bug-for-bug-error-policy.md) | ASSUMED | Every kept quirk is a named `LegacyErrors` clause. Legacy 500s keep the status with a generic JSON string. Unique race loser → 422 | M-06, M-10, M-12, M-30, R-28, C-14, C-18, C-18a, C-19, C-19a, C-26, C-27, C-30 | DV-02, DV-03 |
| [ADR-009](adr/ADR-009-favorite-response-leak.md) | ASSUMED | **UNDECIDED.** Favorite response: keep the leak (default), strip credentials, or standard `ArticleJSON` (recommended) | M-20, C-21 | candidate CDV-01 |
| [ADR-010](adr/ADR-010-demo-visibility-rule.md) | ASSUMED | **UNDECIDED.** Demo visibility rule: keep (default) in one `Visibility.visible_to/2`, drop, or make configurable | M-11, M-22, M-26, C-08, C-23, C-29, C-39 | candidate CDV-02 |
| [ADR-011](adr/ADR-011-jwt-secret-fallback.md) | ASSUMED | **UNDECIDED.** `superSecret` fallback: keep (default) or fail to boot in prod (recommended). Rotate if prod uses it | M-08, M-27, C-37, C-37a | candidate CDV-03 |
| [ADR-012](adr/ADR-012-atomic-article-write.md) | ASSUMED | Article create and update in one `Ecto.Multi` with `FOR UPDATE`. Wipe-on-omit kept. `updatedAt` always bumped | M-14, M-15, M-33, C-27 | DV-04 |
| [ADR-013](adr/ADR-013-release-and-operator-contract.md) | ASSUMED | `mix release` on port 3000. Same env names via `Compat.DatabaseUrl`. Release tasks replace `npx prisma`. Request logs | M-26, M-27, M-28, R-01..R-05, R-24, C-37, C-38, C-39, C-40 | DV-09, DV-12, DV-13 |
| [ADR-014](adr/ADR-014-body-parser-error-status.md) | ASSUMED | **UNDECIDED.** Characterize body-parser errors (413 vs 500), correct C-32, then map Plug errors to the observed status | M-02, R-27, C-32, C-32a | DV-01 |

## Review order (most consequential first)

1. **ADR-009** (C-21): the default ships a High-severity credential leak.
2. **ADR-011** (C-37a) together with V-4: the default allows token forgery if the env var is unset. The production
   secret also decides whether anyone is logged out.
3. **ADR-010** (C-23): the default hides every real user's content on list, comments and tags.
4. ADR-000 A1 and ADR-003: Replacement cutover and the frozen schema decide rollback.
5. ADR-008: the bug-for-bug policy and the generic 500 body.

## Status counts

ASSUMED: 12 (ADR-000, 003, 004, 005, 006, 008, 009, 010, 011, 012, 013, 014) · proposed: 3 (ADR-001, 002, 007) ·
accepted: 0
