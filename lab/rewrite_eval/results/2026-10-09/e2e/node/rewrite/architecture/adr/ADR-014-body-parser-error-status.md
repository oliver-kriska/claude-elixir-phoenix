# ADR-014: Body-parser error status: characterize, correct C-32, then choose (UNDECIDED)

**Status**: ASSUMED (`--auto`; the contract text and legacy evidence disagree; blocks the S1 parser probe only)
**Date**: 2026-10-09 · **Depends on**: ADR-000 A5, ADR-006, ADR-008

## Context

The contracts register (C-32) says an oversized body returns **413**, and the security consult repeats it. The
hex-library-researcher consult read body-parser 1.20.2 and the app's error handler (`main.ts:26-47`) and concluded
something different. body-parser errors are `http-errors` objects with no `errorCode`, and their `name` is not
`UnauthorizedError`, so the handler falls through to `res.status(500).json(err.message)`:

| Input | Legacy (from library source) | Plug default |
|-------|------------------------------|--------------|
| Body > 102,400 bytes | 500 `"request entity too large"` | 413 (`RequestTooLargeError`) |
| Malformed JSON | 500 with the V8 `SyntaxError` text, which varies with the unpinned Node image | 400 (`ParseError`) |
| > 1000 urlencoded params | 500 `"too many parameters"` | no limit |
| Non-UTF charset | 500 `unsupported charset "X"` | 415 |

Nothing has been executed, so neither claim is observed (Iron Law 10). This is C-32a.

## Decision

1. **V-0 / S0:** characterize the pinned legacy build under an isolation decision. Capture status, content type and
   body for each input above.
2. **Correct the C-32 contract text** to match what is observed.
3. **Default implementation, if the source reading is confirmed:** `ExpressBodyParser` rescues
   `Plug.Parsers.RequestTooLargeError`, `ParseError` and `UnsupportedMediaTypeError`. It responds 500 with
   `application/json; charset=utf-8` and a JSON-string body:
   - `"request entity too large"` for an oversized body (deterministic, so reproduced)
   - `unsupported charset "X"` for a bad charset
   - the generic 500 string from ADR-008 for malformed JSON, because the V8 text is not reproducible (DV-01)
   - no 1000-parameter limit (DV-10)

   CORS headers are still present, because `ExpressCors` runs first.
4. **If characterization shows 413:** keep Plug's 413 and align the body to the observed one.
5. **Spec-correct alternative** (413/400/415 with JSON bodies): this is a wire change and needs approval.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|-----------|----------------|-----------|
| 102,400-byte limit | kept | clients |
| Status for parser errors | kept as observed (pending V-0) | clients |
| Malformed-JSON body text | **changed** to the generic string (DV-01) | none known |

## Alternatives

Described in items 3 to 5.

## Consequences

- Until V-0 runs, the S1 parser probe has no acceptance target. Every other S1 probe is unaffected.

## Validation

- Goldens from the pinned legacy build for each input in the table. Status and content type are compared exactly.
  Body text is compared only where it is deterministic.

## Ledger IDs

M-02, R-27, C-32, C-32a
