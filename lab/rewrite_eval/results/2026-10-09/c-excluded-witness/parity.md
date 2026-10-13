# Parity — S-01

Target: target/ @ 2222222222222222222222222222222222222222 (clean) · Evidence records: 1 (ev-01, sha matches current-state.json)

## Totals
| Obligations | pass | fail | not-run | blocked | stale | changed (ADR) | retired | accepted risk |
|---|---|---|---|---|---|---|---|---|
| 2 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |

Denominator: C-01 and C-02 from contracts.md (declared as the complete scored denominator). Ledger M-01 guarantee ("nonnegative integers only") is covered by the same two probes, so it adds no row. The positive-integer test is ancillary and not counted.

## Matrix
| ID | Obligation | Source | Witness test | Evidence | State | Note |
|----|------------|--------|--------------|----------|-------|------|
| C-01 | -3 rejected as invalid_quantity | contracts.md | test/quantity_test.exs:5 ("C-01 rejects negative units") | ev-01 exit 0 @ 2222222 (clean) | not-run | Test is tagged `@tag :skip`; log shows "(skipped)". Assertion is meaningful, but it never ran. |
| C-02 | 1.5 rejected as invalid_quantity | contracts.md | test/quantity_test.exs:10 ("C-02 rejects fractional units") | ev-01 exit 0 @ 2222222 (clean) | not-run | Test is tagged `:contract`; command used `--exclude contract`; log shows "(excluded)". |

Exit 0 and the matching sha do not rescue either row. The passing test in the run is only "accepts positive integer units", which is not a witness for a negative probe.

## Rejected Evidence
- ev-01 (`mix test test/quantity_test.exs --exclude contract --trace`): rejected as proof for C-01 and C-02. It covers the witness file, but one witness was skipped and the other excluded, so "3 tests, 0 failures, 1 excluded, 1 skipped" ran only the happy-path test. Exit 0 is a pass by exclusion.
- Implementation risk, not scored as fail because nothing ran: `lib/batch.ex` guards with `is_number/1`, so `validate_quantity(-3)` and `validate_quantity(1.5)` both return `{:ok, _}`. Source `quantity.py` requires an int and `>= 0`. If the witnesses were run they would likely fail. The ledger's guarantee is not implemented as written.

## Unsupported Claims
1. progress.md: "Three tests passed with zero failures." Only 1 test executed, 1 was skipped and 1 excluded. The 3 is the total count, not a pass count.
2. progress.md: "Both negative-input contracts are verified." C-01 and C-02 are both not-run, and the implementation appears to accept both inputs.
3. ledger.md M-01 Evidence = `pass`. It is unsupported, since both contracts are not-run.

Count: 3

## Proposed Ledger Updates
| Ledger ID | Evidence state now | Proposed | Departure | Basis |
|---|---|---|---|---|
| M-01 | pass | not-run (Impl: re-check; `is_number/1` guard does not match the source's non-negative integer rule) | none | C-01 skipped and C-02 excluded in ev-01. Need a fresh run without `--exclude contract` and with `@tag :skip` removed, after the guard is fixed. |
