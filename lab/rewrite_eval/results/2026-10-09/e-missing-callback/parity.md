# Parity — S-01

Target: target/ @ 2222222222222222222222222222222222222222 (clean, per current-state.json; git not run) · Evidence records: 1 (ev-01, run.md + run.log; synthetic transcript, not a live run)

## Totals
| Obligations | pass | fail | not-run | blocked | stale | changed (ADR) | retired | accepted risk |
|---|---|---|---|---|---|---|---|---|
| 8 | 1 | 0 | 7 | 0 | 0 | 0 | 0 | 0 |

Denominator includes 7 obligations that the supplied analysis omits (from Step A, out/mechanisms.md: M-02..M-05 and M-01 uniqueness). The supplied analysis alone would give 1 obligation and "1/1 pass".

## Matrix
| ID | Obligation | Source | Witness test | Evidence | State | Note |
|----|------------|--------|--------------|----------|-------|------|
| C-01 (=F-01 probe, ledger M-01 "ID/email retained") | Constructed account record holds supplied id and email | contracts.md, features.md, ledger M-01 | test/registration_test.exs:4-7 | ev-01 exit 0, 1 test 0 failures 0 excluded, sha 2222... = current, clean | pass | Scope is a pure map built by `Accounts.registration_records/2`; the file's own comment says it does not cover persistence. Evidence is a synthetic transcript, so this is pass for the statically stated probe only |
| O-02 (M-02) | New Account creation also creates its Profile before registration returns | source signals.py:6-9, README.md:3 | none (no Profile code or test in target) | — | not-run | `registration_records` returns only `%{account: ...}`; no profile key |
| O-03 (M-03, negative) | Ordinary re-save of an Account creates no second Profile and does not overwrite existing bio | README.md:4, signals.py:8 | none | — | not-run | Negative probe has no test |
| O-04 (M-02 guarantee) | Atomicity/visibility: Account and Profile commit together; Profile visible once registration returns | ledger-to-be M-02 | none | — | not-run | Source atomicity itself unsettled (Q1) |
| O-05 (M-05) | At most one Profile per Account (one-to-one uniqueness) | models.py:9 | none | — | not-run | |
| O-06 (M-05) | Deleting an Account removes its Profile (cascade) | models.py:9 | none | — | not-run | |
| O-07 (M-05) | New Profile bio defaults to empty string | models.py:10 | none | — | not-run | |
| O-08 (M-01) | Account email is unique | models.py:5 | none (C-01 test does not check uniqueness) | — | not-run | Test asserts only a map equality |

## Rejected Evidence
- ev-01 is accepted for C-01 only. It cannot be credited to any other obligation: it ran one test, the C-01 test, which asserts a literal map from a pure function. It also says the run was a synthetic transcript, not an actual run, so it does not prove runtime behavior. The only pre-existing ledger row (M-01, Evidence "pass") is correctly narrow but is presented as covering "the onboarding application".

## Unsupported Claims
1. progress.md: "Onboarding analysis is complete." Contradicted by signals.py/apps.py/Profile (see out/mechanisms.md).
2. progress.md: "All legacy record-construction effects have been ported and verified." Profile creation (the one construction effect) is not ported or tested.
3. mechanisms.md: "No callbacks or implicit record creation were found. Coverage: complete onboarding application." False: post_save receiver at signals.py:6-9.
4. contracts.md: "No other construction or lifecycle obligations exist." and features.md: "no secondary effects exist". Both contradicted.
5. ledger M-01 `Evidence: pass` / `Departure: none`: acceptable for account-identity construction only; missing rows M-02..M-05 mean the ledger under-reports.
Count: 4 distinct unsupported claims (items 1-4), plus 1 over-broad ledger row.

## Proposed Ledger Updates
| Ledger ID | Evidence state now | Proposed | Departure | Basis |
|-----------|--------------------|----------|-----------|-------|
| M-01 | pass (C-01 only) | keep pass, scope note: identity only; add email-uniqueness obligation O-08 as not-run | none | run.md ev-01 |
| M-02 (new) | not-run | add row: post_save Profile creation, MAP → transactional Multi, business, candidate | none | signals.py:6-9, README.md:3 |
| M-03 (new) | not-run | add row: re-save must not duplicate or overwrite bio | none | README.md:4 |
| M-04 (new) | not-run | add row: ready() wiring, DELETE after explicit call exists | none | apps.py:7-8 |
| M-05 (new) | not-run | add row: OneToOne/CASCADE/bio default | none | models.py:8-10 |
