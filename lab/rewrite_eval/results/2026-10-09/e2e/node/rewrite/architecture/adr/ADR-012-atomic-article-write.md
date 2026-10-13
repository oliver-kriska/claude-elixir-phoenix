# ADR-012: Article create and update as one `Ecto.Multi`, wipe-on-omit kept

**Status**: ASSUMED (`--auto`; adds atomicity, which changes failure-path data outcomes)
**Date**: 2026-10-09 · **Depends on**: ADR-000 A5, ADR-003, ADR-008

## Context

Legacy article update (`article.service.ts:276-357`, M-14) runs **two separate statements with no transaction**:

1. `tagList: {set: []}` wipes every tag link.
2. A second update sets the truthy `title`, `body` and `description`, plus the new `slug`, `updatedAt = now` and
   `connectOrCreate` for the tags.

If statement 2 fails (slug race, DB error), the article loses its tags. A PUT without `tagList`, or with an empty or
non-array value, leaves zero tags (C-27, UNDECIDED, default keep). Every successful PUT bumps `updatedAt` (M-33).

Create (M-15) uses a Prisma nested write, which is atomic. Two concurrent creates that introduce the same new tag can
500 on `Tag_name_key`. Source: ecto-schema-designer Q1 and Q4.

## Decision

- **Update:** one `Ecto.Multi` with these steps, in order:
  1. Lock the article by slug `FOR UPDATE`, then run the 404 and 403 checks.
  2. Slug pre-check → the legacy 422.
  3. **Always** `delete_all` the `_ArticleToTag` links (C-27).
  4. Upsert the tags with `insert_all("Tag", on_conflict: :nothing, conflict_target: :name)`, then re-select them by name.
  5. `insert_all` the links.
  6. Update the truthy fields with `force_change(:updated_at, Compat.Time.now_ms())` and
     `unique_constraint(:slug, name: "Article_slug_key")`.
  7. Reload for the view.
- **Create:** the same Multi without the lock and without the wipe.
- Tag names are stored raw: no trim, no downcase, `Enum.uniq` per request. Non-string tag entries take a named
  `:legacy_500` path (ADR-008).

## Guarantees

| Guarantee | Kept / changed | Consumers |
|-----------|----------------|-----------|
| End state on every successful PUT, including the wipe when `tagList` is omitted | kept | editor UIs |
| `updatedAt` bumped on every successful PUT, `createdAt` unchanged | kept | clients |
| 404 → 403 → 422 order | kept | clients |
| A failure after the wipe leaves tags intact | **changed** (legacy loses them; DV-04) | authors (improvement) |
| Concurrent PUTs to one article serialise | **changed** (legacy has no lock; DV-04) | none observable on success |
| Concurrent creates with the same new tag | **changed**: 500 → success (DV-04) | authors (improvement) |

## Alternatives

- **Reproduce the non-atomic two-statement shape.** Rejected: it re-implements silent data loss, and no consumer can
  depend on the failure outcome.
- **`put_assoc(:tags, ..., on_replace: :delete)`.** The end state is identical, but it needs a preload and hides the
  wipe. The Multi mirrors the legacy steps visibly.
- **Stop wiping when `tagList` is omitted** (the spec-correct behaviour). This is a candidate change under C-27,
  UNDECIDED.

## Consequences

- One extra row lock per update. Update throughput is measured in the perf plan, not claimed.

## Validation

- Golden: `PUT {article:{}}` gives `tagList: []`, `updatedAt` changed and `createdAt` unchanged.
- Fault injection: force the slug unique violation after the wipe, then assert the tags survive.
- Concurrency test: two creates with the same new tag both succeed, leaving one `Tag` row.

## Ledger IDs

M-14, M-15, M-33, C-27
