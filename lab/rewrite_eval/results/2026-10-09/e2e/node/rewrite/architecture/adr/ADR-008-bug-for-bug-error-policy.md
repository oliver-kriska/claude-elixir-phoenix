# ADR-008: Bug-for-bug policy: every kept quirk is a named compat behaviour

**Status**: ASSUMED (`--auto`; keeps wire quirks and changes the 500 body text)
**Date**: 2026-10-09 · **Depends on**: ADR-000 A5 (keep all contracts, including quirks)

## Context

Legacy's error envelope comes from one Express handler (`main.ts:26-47`, M-06):

- a thrown `HttpException` → its payload as-is, with its status
- an express-jwt error → the exact 401
- anything else → `res.status(500).json(err.message)`

The result is a set of observed quirks that clients may depend on:

- C-18: 422 messages, in order
- C-18a: bad login → **403** `{"errors":{"email or password":["is invalid"]}}`
- C-19: 404 `{}`, 404 article errors, and 403 `{message}` for non-authors
- C-19a: Prisma, TypeError and slugify failures → 500 with the error text as a JSON string
- C-26: comment POST returns 200, DELETE ignores `:slug`, a non-author gets 404, and an unknown slug on the list gives `200 {}`
- C-27: a PUT without `tagList` wipes the tags
- C-30: truthy-only `PUT /user`, untrimmed password, a duplicate → 500

ADR-000 keeps all of them, but lists the policy as a consequential assumption that blocks planning. The 500 text
comes from Prisma and V8 and **cannot be reproduced** by Ecto. Source: security-analyzer Q4,
ecto-schema-designer Q3 and Q4, hex-library-researcher Q3.

## Decision

1. **Contexts stay idiomatic.** They return `{:ok, _}`, `{:error, %Ecto.Changeset{}}`, `{:error, :not_found}`,
   `{:error, {:forbidden, msg}}` or `{:error, {:legacy, case_name}}`. They never build HTTP bodies.
2. **`RealworldWeb.Compat.LegacyErrors`** plus `FallbackController` turn those into the legacy status and body
   **per endpoint**:
   - every quirk has a named clause, for example `:comment_unknown_slug_200_empty` or `:login_invalid_403`
   - every named clause has one golden test
   - nothing quirky lives in a context or a changeset
3. **The legacy-500 family (C-19a).** Each 500 path legacy can reach is listed as a named `{:error, :legacy_500}`
   case. The list is in the C-19a row: P2025, P2002 on update, missing target on follow or favorite, negative offset,
   deleted-user token, missing envelope, non-string title or password. Each one returns status 500,
   `application/json; charset=utf-8`, and **a fixed generic JSON string** (`"Internal Server Error"`).
   - The real exception is logged server-side with the request id.
   - `debug_errors: false` is set in prod.
   - Exact text is impossible, so this is a recorded relaxation (DV-03), not a parity claim.
4. **Unexpected exceptions** (bugs in the port) also return 500 with the same generic JSON string. That keeps the
   status class legacy clients expect.
5. **Unique-constraint race losers.** The pre-check queries keep the legacy 422 messages on the happy path. The
   `unique_constraint` safety net turns the race loser's former Prisma 500 into the same 422 (DV-02).
6. **Defaults for the UNDECIDED rows, if they are confirmed:**
   - C-18a stays 403
   - C-26 is kept in full
   - C-27 keeps the wipe, made atomic by ADR-012
   - C-30 is kept in full
   - C-19a follows item 3

   Each default becomes a candidate divergence if the user chooses to change it.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|-----------|----------------|-----------|
| Status codes and 4xx bodies per endpoint | kept | every client |
| 500 status and JSON-string body type | kept | clients branching on status |
| 500 body text | **changed** to a generic string (DV-03) | anyone parsing Prisma messages (none known). Removes the CWE-209 leak |
| A duplicate on the race loser | **changed** 500 → 422 (DV-02) | clients (improvement) |
| Quirk set (403 login, comment quirks, tag wipe, truthy update) | kept by default, UNDECIDED | clients |

## Alternatives

- **Spec-correct statuses** (401 or 422 login, 201 comment, 404 for unknown slugs). Rejected under A5 until a client
  survey exists. Each one is listed as a candidate change.
- **Reproduce the Prisma 500 text.** Rejected: impossible, and it would re-create an information leak.
- **Quirks inside contexts or changesets.** Rejected: that is translationese, and it makes later retirement
  expensive.

## Consequences

- Retiring a quirk later is a one-clause change in `LegacyErrors`, plus a divergence record.
- The C-19a list must be complete. Any 500 path missing from it still returns the generic 500, so clients see the
  same status class.

## Validation

- One golden per named clause, captured from the pinned legacy build (V-0). 500 goldens compare status and
  content type only.
- A race test: two concurrent registers with the same email → one 200 and one 422.

## Ledger IDs

M-06, M-10, M-12, M-30, R-28, C-14, C-18, C-18a, C-19, C-19a, C-26, C-27, C-30
