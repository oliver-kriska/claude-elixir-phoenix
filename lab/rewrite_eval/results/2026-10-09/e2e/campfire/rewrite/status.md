# Rewrite Status

- **Phase:** roadmapped (ASSUMED) — slice 00 seeded, handoff blocked
- **Date:** 2026-10-09
- **Mode:** `--auto` (all defaults recorded as ASSUMED; nothing approved)
- **SOURCE:** `~/Projects/campfire-bench/once-campfire-elixir/reference`
- **Source stack:** Rails (ONCE Campfire)
- **Source sha:** `90b330024dec3e757c79b6a7e6568f93da8e3148` (clean, 259 commits)
- **Source tree fingerprint:** `455ff1ef81a4f46d`
- **TARGET:** `$S/e2e/campfire`
- **Target sha:** none (no commits yet)
- **Scope:** whole app (694 files)

## Artifacts

| Artifact | State | Summary |
|----------|-------|---------|
| `charter.md` | ok | 4 ASSUMED values |
| `inventory/inventory.{json,md}` | ok | deterministic snapshot |
| `kb/` | ok, incomplete | `app-shapes.md` is referenced by the plugin but missing from the plugin's `elixir-way/references/`; agents classified shape from the inventory |
| `analysis/features.md` | ok | 28 capabilities, 10 actors, 20 triage questions (all ASSUMED preserve) |
| `analysis/mechanisms.md` | ok | 69 mechanisms; 1 unknown (M-51 `X-Version`/`X-Rev` headers) |
| `analysis/runtime.md` | ok | 10 processes, 10 datastore roles, 4 jobs, 9 operator duties |
| `analysis/contracts.md` | ok | 57 contracts (17 data, 29 wire, 11 operational), 11 ADR-000 decisions |

## Open questions (carried to `/rewrite:architect`)

- ADR-000 decisions 1–11 in `contracts.md` (cutover mode, rollback window, session continuity, `SECRET_KEY_BASE` reuse, bot API compat, rich-text format, Active Storage layout, realtime/UI protocol, Web Push continuity, operator surface, Redis removal)
- Retry policy for webhooks and push under Oban (at-most-once today; mechanisms Q3, runtime Q5, triage T-12)
- Presence: DB connection counters vs `Phoenix.Presence` (runtime Q6, mechanisms Q4)
- TLS: keep Thruster or move TLS/ACME into the release (runtime Q1, mechanisms Q5)
- Cookie crypto parameters need test vectors from the pinned Rails image (contracts)
- 20 triage questions in `features.md` (security-relevant: T-03, T-04, T-06, T-07)

## Coverage gaps

- ~60 Stimulus controllers and most of the 89 views/helpers were not fully audited
- Opengraph fetch internals, CI config, non-production environment configs not read in depth
- Thruster env vars, cert path and `/up` probing inferred from gem defaults, not confirmed
- No legacy test covers: login rate limit, service worker, ONCE hooks, admin scripts, env vars, auto-migration
- `has_json` definition and `Purchaser` usage not located
- Effective SQLite pragmas cannot be confirmed without running the app (not allowed)

## Architecture (2026-10-09, `--auto`, resumed)

| Artifact | State | Summary |
|----------|-------|---------|
| `architecture/ADR-000-compatibility-bar.md` | ASSUMED | Replacement cutover; keep schema, sessions, Hotwire UI, all 57 contracts |
| `architecture/adr/ADR-001..021` | ASSUMED/proposed | 21 ADRs |
| `architecture/consults/` | ok | ecto-schema-designer, oban-specialist, otp-advisor, security-analyzer |
| `architecture/architecture.md` | proposed | 8 contexts, `:rest_for_one` tree |
| `architecture/decisions.md` | proposed | decision index |
| `architecture/divergences.md` | 19 pending | none approved |
| `ledger.md` | check OK | 151 rows: KEEP 60, MAP 42, REPLACE 28, DELETE 12, SHIM 8, UNDECIDED 1 (M-69 `SCRIPT_NAME`) |

## Roadmap (2026-10-09, `--auto`)

- `roadmap.md`: 19 slices (00 Foundation … 18 Release rehearsal), all `blocked` on ASSUMED ADR-000 (+ per-slice ADRs/divergences); 28/28 F- caps and 151/151 ledger rows placed
- Slice 02 = post a message and deliver it live (F-08), the riskiest core path
- Seeded: `../plans/rewrite-00-foundation/{interview,scratchpad}.md` — Status IN_PROGRESS, 16 DECISION / 9 DEAD-END
- `/phx:plan` NOT invoked: ADR-000 cutover/data/identity/clients decisions are ASSUMED

## Next

Approve or revise ADR-000 (+ ADR-003, ADR-004, ADR-010 for slice 00), decide M-69, review DV-01..19; then
`/phx:plan .claude/plans/rewrite-00-foundation/interview.md`.
