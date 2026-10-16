# Parity — S-01

Target: target/ @ 2222222222222222222222222222222222222222 (clean) · Evidence records: 1 (ev-01, synthetic replay data)

Missing inputs: no `interview.md` and no `features.md` in the packet. The obligations come from `contracts.md` and the ledger row M-01.

## Totals
| Obligations | pass | fail | not-run | blocked | stale | changed (ADR) | retired | accepted risk |
|-------------|------|------|---------|---------|-------|---------------|---------|---------------|
| 3 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |

## Matrix
| ID | Obligation | Source | Witness test | Evidence | State | Note |
|----|------------|--------|--------------|----------|-------|------|
| C-01 | A real v1 credential is decoded and verified, and the original user ID is returned | contracts.md:3, SOURCE/PROTOCOL.md:3-4 | test/codec_test.exs:6 (rejected) | ev-01 exit 0 @ 2222222 (matches HEAD, clean) | not-run | The test stubs `SessionCodecMock.verify` to return `{:ok, "user-17"}` for the made-up token "fixture-valid". The codec under test never runs. `SessionGate.authenticate/2` only delegates to `codec.verify/1`. No real HMAC-SHA256 or base64url decoding is exercised. |
| C-02 | A v1 credential whose payload changed with an unchanged signature is rejected | contracts.md:4, SOURCE/PROTOCOL.md:4 | test/codec_test.exs:11 (rejected) | ev-01 exit 0 @ 2222222 (matches HEAD, clean) | not-run | The mock returns `{:error, :invalid}` for "fixture-tampered" regardless of content. No signature is computed or compared. The test only checks that the gate passes the mock's answer through. This is also the wrong layer: contracts.md says the slice covers the codec itself, not a caller's handling of a codec result. |
| M-01.g1 | Ledger guarantee "Principal integrity": the ID is returned only after signature verification | ledger.md M-01, SOURCE/PROTOCOL.md:4 | none valid | — | not-run | It depends on C-01 and C-02. No `SessionCodec` implementation exists in `lib/`; `session_gate.ex` holds only the `@callback` and the delegating gate. |

## Rejected Evidence
- **ev-01 (`mix test test/codec_test.exs --trace`, exit 0, 2 tests, 0 failures, 0 excluded)**: the sha, clean tree, environment and exit status all check out, and the file was run. It proves nothing about the contract, because both tests are Mox-stubbed. The passing run shows that the mock returns what it was told to return. Rule 2 of Step 2 ("Stubs the contract under test") rejects both tests as witnesses.
- test/codec_test.exs:6 (C-01): the mock replaces the codec. There is no real credential and no decode.
- test/codec_test.exs:11 (C-02): the mock replaces the codec. No signature mismatch is exercised.
- The test names carry the IDs "C-01" and "C-02", but the names do not make the tests witnesses.
- I found no `@tag :skip` or exclusions. The problem is the stubbing, not skipping.
- The log is synthetic replay data.

## Unsupported Claims
1. `progress.md:3`: "The real v1 codec is compatible." There is no real codec in `target/lib`, and ev-01 only exercises a mock. Unsupported.
2. `progress.md:3`: "Both decoding and cryptographic tamper rejection are proven by ev-01." ev-01 contains no decoding and no cryptography. Unsupported and contradicted.

Count: 2

## Proposed Ledger Updates
| Ledger ID | Evidence state now | Proposed | Departure | Basis |
|-----------|--------------------|----------|-----------|-------|
| M-01 | pass | not-run | none | The "pass" is not supported. Both witnesses stub the codec under test (C-01, C-02), and no real `SessionCodec` implementation exists. Impl should likely read `pending` for the codec itself, since only the gate and callback are present. Before M-01 can be re-scored, add tests that use a real synthetic key to decode a valid credential, and to reject a payload altered under an unchanged signature, run without Mox on the codec. |
