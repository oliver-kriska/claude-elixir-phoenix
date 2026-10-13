# ADR-007: In-repo port of slugify 1.6.6 for byte-equal slugs

**Status**: proposed
**Date**: 2026-10-09 · **Depends on**: ADR-000 (C-11 kept)

## Context

Slugs are `slugify(title) + "-" + authorId` with npm slugify 1.6.6 default options (M-13). The steps are: NFC
normalisation, the npm charMap (for example `&` → `and`, `$` → `dollar`), a hyphen-to-space rule, removal of anything
outside `[\w\s$*_+~.()'"!\-:@]` (ASCII `\w`, JS `\s`), JS trim, and whitespace runs collapsed to `-`. Case is preserved.
Slugs are public URLs and are stored in `Article.slug` (C-11, C-25). The hex-library-researcher consult checked
`slugify` (Hex), `slugger` and `slugy`. All three lowercase or strip the punctuation legacy keeps, and none uses the
npm charMap.

## Decision

- `Realworld.Compat.Slug.slugify/1` ports slugify 1.6.6 with default options.
- The charMap is built at compile time from a vendored copy of the npm table (`@external_resource`). It includes the
  multi-character values and the three empty-string mappings. The `locales` table is left out.
- Whitespace and trim use the explicit JS character class. PCRE `\s` and `String.trim/1` are never used.
- A non-binary title takes the legacy 500 path. Legacy body text: `"slugify: string argument expected"` (C-19a).
- Uniqueness: a pre-check query for the legacy 422 `title: must be unique`, plus
  `unique_constraint(:slug, name: "Article_slug_key")` mapped onto `:title`.
- Re-slug only on a truthy title. The old slug then returns 404, with no redirect (C-25).

**Owner:** `Compat`. **Support policy:** permanent while any stored slug may be regenerated or compared.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|-----------|----------------|-----------|
| Byte-equal slugs on the golden corpus | kept | public URLs, Node rollback (Node re-slugs titles the same way) |
| An all-stripped title gives `-<id>` | kept | — |
| Exotic code points where Node ICU and OTP Unicode tables differ in NFC | **possible change** (DV-15), bounded by the corpus | authors with rare scripts |

## Alternatives

- **A Hex slug library.** Rejected: none matches. Every one would change public URLs and the uniqueness space.
- **A NIF or port calling Node.** Rejected: it brings the Node runtime back for one function.

## Consequences

- About 1,000 charMap entries are vendored and must never be "cleaned up". A test pins the table's checksum.

## Validation

- Corpus generated **outside the legacy repo** with `npm i slugify@1.6.6 --ignore-scripts` and a ten-line script.
  It covers about 30 hand-picked cases (every charMap category, kept punctuation, NBSP, U+3000, U+FEFF, U+0085,
  CJK, emoji, ZWJ, NFD input, empty-after-strip, 2k-character titles) plus about 500 random charMap strings.
  Every case must be byte-equal.
- Optional: re-slug the stored titles from a prod snapshot and diff against stored slugs, ignoring the `-id`
  suffix.

## Ledger IDs

M-13, C-11, C-25
