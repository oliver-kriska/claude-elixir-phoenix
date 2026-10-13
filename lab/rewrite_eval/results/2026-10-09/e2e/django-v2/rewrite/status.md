Phase: slicing (ASSUMED)
Source path: $S/testbeds/django-realworld
Target path: $S/e2e/django-v2
Plugin version: 0.1.0

- Date: 2026-10-09
- Source sha: 29c9d42831fa0cfc5a4aa7561f674396eacf20a2 (master); tree fingerprint de077c0df95ad117
- Target sha: HEAD
none
- Stack: django (Django 1.10.5, DRF 3.4.4, PyJWT 1.4.2); shape http-api; 48 files, 1,778 Python LOC
- Scope: whole app
- History: absent (1 commit, shallow repository; hotspots suppressed, no purpose inferred from history)
- Budget hits: none (cartographer ~46 files/65 KB; archaeologist ~47/75 KB; topologist ~15/120 KB; surveyor 47/64 KB)
- Mode: --auto (charter + triage defaults ASSUMED)

## Artifacts

| Artifact | State |
|----------|-------|
| charter.md | ok (ASSUMED) |
| inventory/inventory.{json,md} | ok |
| kb/ | ok |
| analysis/budget.md | ok |
| analysis/features.md | ok (15 capabilities, 20 triage items, decisions recorded) |
| analysis/mechanisms.md | ok (41 mechanisms) |
| analysis/runtime.md | ok |
| analysis/contracts.md | ok (29 contracts, 15 defects, 12 incidental) |

## Conflicts (step 7a cross-check)

- No hard conflicts. Status codes, envelopes, follow direction (from_profile_id → to_profile_id) and tag replacement on update agree across features, mechanisms and contracts.
- Open: `tagList` response order. features.md:157 marks it UNKNOWN; contracts.md C-20 says newest tag first (Tag Meta ordering). Verify with an isolated legacy run.

## Open questions

- Does a production db.sqlite3 exist (import vs start empty), and SQLite vs Postgres? (runtime Q1/Q2, contracts Q2)
- Which frontends consume the API, and which RealWorld spec revision is the target? (contracts Q4/Q5)
- Is `/admin/` used? (runtime Q5, M-33 unknown)
- Production CORS origins? (runtime Q4, C-31)
- May golden responses be recorded from an isolated legacy run? Several claims are (lib)/inferred, e.g. feed shadowing, non-HS256 acceptance (contracts Q7)
- Observability expectations (runtime Q6)

## Architect (2026-10-09, --auto)

- ADR-000: ASSUMED (Replacement cutover; schema as-is on SQLite; keep hashes, one forced re-login; no UI, keep wire API)
- Consults: ecto-schema-designer ok, security-analyzer ok
- Ledger: check OK — 74 rows; MAP 30, REPLACE 15, DELETE 18, KEEP 1, UNDECIDED 10; 0 verified
- ADRs: ADR-001..013 (proposed); divergences: DV-01..25 + DV-P1..P8, all pending
- Open decisions: C-16 403 vs 401; ADR-007 OD-2 PBKDF2 iterations; ADR-013 OD-6 rollback method + WAL backups; OD-5 admin use; possible C-42 reclassification (WAL vs file-copy backups)

## Roadmap (2026-10-09, --auto)

- roadmap.md: 13 slices (00a, 00b, 00c, 01, 02a, 02b, 02c, 03–09); 74/74 ledger rows assigned exactly once
- ready: 00b, 01, 04, 07, 08, 09 · seeded: 00a · blocked by UNDECIDED: 00c (C-41), 02a (C-16), 02b (C-40), 02c (C-37), 03 (C-38, C-39), 05 (C-08, C-09, C-36), 06 (C-35)
- Seed: .claude/plans/rewrite-00a-skeleton-config-repo/{interview.md,scratchpad.md} (IN_PROGRESS, 11/12, D-01..D-06, X-01..X-05)
- /phx:plan NOT invoked: ADR-000, charter, ADR-001/003/011 and DV-06/13/22 are ASSUMED/proposed/pending
