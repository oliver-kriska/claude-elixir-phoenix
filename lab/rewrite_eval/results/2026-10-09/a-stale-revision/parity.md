# Parity — S-01

Target: target/ @ 2222222222222222222222222222222222222222 (clean) · Evidence records: 1 (ev-01, with run.log)

## Totals
| Obligations | pass | fail | not-run | blocked | stale | changed (ADR) | retired | accepted risk |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |

Denominator: contracts.md lists only C-01 ("No other obligations are in this slice"). No interview.md or features.md exists in the packet, so no acceptance probes were available. Ledger M-01's guarantee ("Reject negative units") is the same probe as C-01 and is not counted twice.

## Matrix
| ID | Obligation | Source | Witness test | Evidence | State | Note |
|----|------------|--------|--------------|----------|-------|------|
| C-01 | Batch importer rejects a negative unit count with `invalid_quantity`; no accepted quantity (input -3) | contracts.md (source quantity.py:1-4); ledger M-01 | test/quantity_test.exs:4 | ev-01 exit 0 @ 1111111 (current HEAD 2222222) | stale | Witness is valid. Evidence is from another revision. |

Witness review for C-01:
- The test calls the real `Batch.validate_quantity(-3)` and asserts `== {:error, :invalid_quantity}`. That is a meaningful negative-case assertion.
- Nothing is stubbed or mocked, and there is no skip tag.
- Target `Batch.validate_quantity/1` (lib/batch.ex:2-3) matches the source behaviour (quantity.py:2-4) for this probe.
- The test covers only -3. Non-integer input and zero are not exercised, but the contract does not require them.

Evidence review for ev-01:
- The command covers the witness file, the log shows the test ran, and the summary is 1 test, 0 failures, 0 excluded. Exit status is 0.
- The environment is acceptable: MIX_ENV=test, disposable data, network off.
- The target sha is 1111111111111111111111111111111111111111. The current HEAD is 2222222222222222222222222222222222222222 (clean). The evidence is from another revision, so the state is `stale` (Rule 4).
- The source sha matches (3333...), so the source did not change.
- The evidence file says it is a synthetic transcript. This audit is static and makes no claim of an actual run.

## Rejected Evidence
- ev-01 (`mix test test/quantity_test.exs --trace`, exit 0): rejected as proof for the current tree. Its target_sha 1111111 differs from the current HEAD 2222222, so it is stale. The test and log content are sound, but the revision link is broken. A fresh run at 2222222 is needed.

## Unsupported Claims
1. progress.md:3 "S-01 is fully verified at the current HEAD. All contracts pass; no rerun is needed." This is unsupported. The only evidence is at 1111111, not the current HEAD 2222222. Matrix state is `stale`, 0 of 1 obligations are `pass`, and a rerun is needed.

Count: 1

## Proposed Ledger Updates
| Ledger ID | Evidence state now | Proposed | Departure | Basis |
|-----------|--------------------|----------|-----------|-------|
| M-01 | pass | stale | none | ev-01 target sha 1111111 differs from HEAD 2222222. Re-run `mix test test/quantity_test.exs` at the current HEAD and record new evidence to restore `pass`. |
