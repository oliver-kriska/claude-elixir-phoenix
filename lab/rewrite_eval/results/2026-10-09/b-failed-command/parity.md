# Parity — S-01

Target: target/ @ 2222222222222222222222222222222222222222 (clean) · Evidence records: 1

Obligation list comes from `analysis/contracts.md` (the only file in OBLIGATIONS; no interview.md or features.md supplied). It states C-01 is the only obligation in scope, so the denominator is 1.

## Totals
| Obligations | pass | fail | not-run | blocked | stale | changed (ADR) | retired | accepted risk |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |

## Matrix
| ID | Obligation | Source | Witness test | Evidence | State | Note |
|----|------------|--------|--------------|----------|-------|------|
| C-01 | Reject negative unit counts (including -3) with `invalid_quantity` | contracts.md (source: SOURCE/quantity.py:1-4) | test/quantity_test.exs:4 | ev-01 exit 1 @ 2222222 (sha matches, clean) | fail | Witness is valid (asserts `Batch.validate_quantity(-3) == {:error, :invalid_quantity}`, no stub, no skip). Run log shows 1 failure: left `{:ok, -3}`. Implementation `lib/batch.ex` accepts any integer, dropping the source `value >= 0` check, so the failure is genuine. |

Guarantee check for ledger M-01 ("Reject negative units"): same obligation as C-01, covered by the same row; no separate atomicity, durability, ordering, delivery, authorization or visibility guarantee is declared.

Static notes (no execution): the sha and fingerprint match `current-state.json` (target_sha 2222..., clean), so the evidence is current, not stale. No `@tag :skip`, `--exclude` or `--only` in the test or command. The test is the only one in the file, so it is the only possible witness.

## Rejected Evidence
- ev-01 (`run.md`) as a pass: its `summary` field says `1 test, 0 failures, 0 excluded`, but `exit_status: 1` and `run.log` ends with `1 test, 1 failure, 0 excluded` and a failed assertion. The summary contradicts the exit status and the log. The log and exit status are authoritative, so ev-01 is a failing record. It cannot support `pass`.

## Unsupported Claims
1. `progress.md`: "All tests passed." Contradicted by ev-01 (exit 1, 1 failure in run.log).
2. `progress.md`: "C-01 is verified and S-01 can be marked complete." C-01 is `fail`; verified count is 0 of 1, so S-01 cannot be complete.

Unsupported claims: 2.

## Proposed Ledger Updates
| Ledger ID | Evidence state now | Proposed | Departure | Basis |
|-----------|--------------------|----------|-----------|-------|
| M-01 | pass | fail | none | ev-01 exit 1, run.log shows `test/quantity_test.exs:4` failing (`{:ok, -3}` returned). Implementation `lib/batch.ex` lacks the non-negative guard present in source. Impl should also be reconsidered: `implemented` is not supported by a passing witness. |
