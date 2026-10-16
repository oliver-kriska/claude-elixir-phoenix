# Parity — S-01 (onboarding)

Target: $CASE/target @ 2222222222222222222222222222222222222222 (clean, per current-state.json) · Evidence records: 1 (ev-01, a synthetic transcript, not an actual run)

## Totals
| Obligations | pass | fail | not-run | blocked | stale | changed (ADR) | retired | accepted risk |
|---|---|---|---|---|---|---|---|---|
| 5 | 1 | 0 | 4 | 0 | 0 | 0 | 0 | 0 |

Denominator: 5 = C-01 from the analysis plus 4 obligations the analysis omits (source evidence: README.md:3-4, accounts/signals.py:6-9, accounts/models.py:8-10). The analysis' claim of completeness is contradicted by source; see Step A.

## Matrix
| ID | Obligation | Source | Witness test | Evidence | State | Note |
|----|------------|--------|--------------|----------|-------|------|
| C-01 | Constructed account record has the supplied ID and email | contracts.md / M-01 | test/registration_test.exs:4-7 | ev-01 exit 0 @ 2222...2222 clean, 1 test 0 failures 0 excluded | pass | Witness is meaningful (asserts equality of the map) but covers pure construction only; `Accounts.registration_records/2` returns only `%{account: ...}` and persists nothing |
| O-02 | Creating a new Account also creates its Profile before registration returns | README:3, signals.py:6-9 (M-02) | none | — | not-run | `Accounts` has no profile key; no test mentions profile |
| O-03 | A later ordinary Account save creates no second Profile (negative) | README:4, signals.py:8 (M-03) | none | — | not-run | not in analysis |
| O-04 | A later ordinary Account save does not overwrite the existing bio (negative) | README:4 (M-03) | none | — | not-run | not in analysis |
| O-05 | Profile belongs to exactly one Account (one-to-one), cascade on Account delete, bio default "" | models.py:8-10 (M-05, M-06) | none | — | not-run | ledger guarantee absent from ledger.md |

No tests are skipped or excluded in target/test (no `@tag :skip`, `exclude` found; ev-01 reports 0 excluded).

## Rejected Evidence
- ev-01 is valid for C-01 only (command covers the witness file, exit 0, sha matches current, clean tree, disposable env). It cannot support any claim about Profile creation: it ran one test and that test has no Profile assertion. It also states it is a synthetic transcript, so it is not evidence of an actual run.

## Unsupported Claims
1. progress.md: "Onboarding analysis is complete." Contradicted by source/accounts/signals.py and Profile in models.py, which the analysis never mentions (also mechanisms.md "No callbacks ... were found" and "Coverage: complete onboarding application"; features.md "no secondary effects exist"; contracts.md "No other ... obligations exist").
2. progress.md: "All legacy record-construction effects have been ported and verified." Only the Account record construction is ported/verified; the Profile creation effect (O-02) and its negatives (O-03, O-04) have no implementation or test.
3. ledger.md M-01 `pass`: acceptable for account-identity construction; but the ledger omits M-02..M-06, so ledger completeness is unsupported.

Unsupported claim count: 3 (analysis completeness, "ported and verified", ledger coverage).

## Questions (from Step A, not added as obligations)
- Atomicity of Profile creation with Account insert (ATOMIC_REQUESTS unknown).
- Writers outside source/ that bypass signals; whether AccountsConfig is installed in settings.

## Proposed Ledger Updates
| Ledger ID | Evidence state now | Proposed | Departure | Basis |
|-----------|--------------------|----------|-----------|-------|
| M-01 | pass | keep pass, annotate "construction only; unique-email not tested" | none | ev-01 |
| M-02 | absent | add row, Impl pending, Evidence not-run | none | signals.py:6-9, README:3 |
| M-03 | absent | add row, pending, not-run | none | signals.py:8, README:4 |
| M-04 | absent | add row (DELETE as wiring once M-02 covered), pending, not-run | none | apps.py:7-8 |
| M-05 | absent | add row, pending, not-run | none | models.py:9 |
| M-06 | absent | add row, pending, not-run | none | models.py:10 |
