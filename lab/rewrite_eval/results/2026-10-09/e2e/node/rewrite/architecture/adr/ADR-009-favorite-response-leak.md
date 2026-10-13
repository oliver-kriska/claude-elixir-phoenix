# ADR-009: Favorite and unfavorite response: credential leak (UNDECIDED)

**Status**: ASSUMED (`--auto` default = keep; security change recommended; blocks S6)
**Date**: 2026-10-09 · **Depends on**: ADR-000 A5, consequential assumption 3

## Context

`POST` and `DELETE /api/articles/:slug/favorite` spread the raw Prisma article row into the response
(`article.service.ts:597-603, 643-649`; M-20, C-21). Besides the normal article fields, the response includes `id`,
`authorId` and `favoritedBy[]`. Each `favoritedBy` entry carries the user's **`email`, bcrypt `password` hash and
`demo` flag**. Registration is open, so any account can collect the credentials of everyone who favorited an article.
The security consult rates it **High** (CWE-200, OWASP A01/A02). No consumer has a legitimate use for it (inferred).
ADR-000 keeps it under `--auto`, and every analyst recommends changing it.

## Decision

Three options are presented. The design implements **whichever the user approves**. Until then the ledger row stays
UNDECIDED and S6 is blocked.

| Option | Response | Wire change | Risk |
|--------|----------|-------------|------|
| **A: keep (the `--auto` default)** | Raw shape, re-implemented with an explicit key list | none | Re-implements a credential leak on purpose |
| **B: strip credentials (minimum safe)** | Same raw shape, with `email`, `password` and `demo` removed from each `favoritedBy` entry | Removes three keys per entry | Clients reading those keys break (none legitimate) |
| **C: standard `ArticleJSON` (recommended)** | The C-20 article object, as every other article endpoint returns | Removes `id`, `authorId` and `favoritedBy`, and adds the C-20 keys | Clients reading `favoritedBy`, `id` or `authorId` break |

Whichever option wins lives in a dedicated `ArticleJSON.favorite_response/1` clause, so it is a single, reviewable
place.

**Rollback caveat:** a Node rollback brings the leak back. If B or C is approved, patch the legacy app as well.

## Guarantees

| Guarantee | A | B | C |
|-----------|---|---|---|
| Response keys byte-compatible | kept | changed | changed |
| Credentials never on the wire | **violated** | kept | kept |

## Alternatives

Already covered in the table. Hiding the leak behind a feature flag is rejected, because it doubles the test surface
for a behaviour nobody needs.

## Consequences

- With A, the port knowingly ships a High-severity leak. `mix sobelow` will not catch it, because it lives in view
  logic. A dedicated test should assert the leak exists, so that removing it is a deliberate decision.
- With B or C, a divergence moves from candidate to pending (see divergences.md, "Candidate divergences").

## Validation

- Front-end evidence: does any client read `favoritedBy`, `id` or `authorId` from the favorite response?
- A golden test for the chosen option. For B or C, a negative test asserts that no `password` or `email` key appears
  anywhere in the body.

## Ledger IDs

M-20, C-21
