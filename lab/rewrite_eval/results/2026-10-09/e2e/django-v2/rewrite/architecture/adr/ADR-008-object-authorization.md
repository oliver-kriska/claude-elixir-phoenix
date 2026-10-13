# ADR-008: Object authorization for article update and comment delete

**Status**: ASSUMED (inherits ADR-000's ASSUMED security dispositions for C-32, C-33; pending user approval) · **Date**: 2026-10-09

## Context
Legacy has only `IsAuthenticatedOrReadOnly` (M-27): any signed-in user can rewrite any article, slug included (C-32), and delete any comment by id
through any article's URL (C-33). Both are security defects that ADR-000 changes toward safe behaviour. Security consult Q4.

## Decision
- Checks live in the context against `scope.profile.id` (author FKs are profile ids).
- `Articles.update_article(scope, slug, attrs)`: unknown slug → `{:error, :not_found}` (404, legacy body); `author_id != scope.profile.id` →
  `{:error, :forbidden}` → 403. The changeset never casts `author_id`.
- `Articles.delete_comment(scope, slug, id)`: one query joining the article by URL slug and comment id (`Integer.parse` must consume the whole string);
  nil → 404 `{"errors":{"comment":"A comment with this ID does not exist."}}`; author mismatch → 403. Not-found before forbidden.
- Whether the **article author** may also delete comments on their article: UNDECIDED (features.md T-02 note); the design allows only the comment author.
- 403 body: **proposed** (DV-P6) — DRF's default text "You do not have permission to perform this action.", label-wrapped on article update
  (`{"article":{"detail":…}}`) and bare on comment delete (`{"detail":…}`). Frozen only after approval.
- Unauthenticated callers keep the C-16 status quo at the pipeline (UNDECIDED, ADR-006).

## Guarantees
- Changed: C-32, C-33 (DV-03, DV-04). Consumers: only non-authors lose access; a client that relied on editing others' articles has no legitimate use.
- Kept: C-25 statuses for the success paths, C-26 not-found bodies.

## Alternatives
Bodyguard policies: one more abstraction for two checks; plain context functions suffice.

## Consequences
Controllers stay thin; the FallbackController maps `:forbidden` through `LegacyErrors`.

## Validation
B updates A's article → 403, row unchanged; B deletes A's comment → 403, row exists; A deletes own comment via another article's slug → 404;
PUT with an `author` key → ignored.

## Ledger IDs
M-27, C-32, C-33, C-29
