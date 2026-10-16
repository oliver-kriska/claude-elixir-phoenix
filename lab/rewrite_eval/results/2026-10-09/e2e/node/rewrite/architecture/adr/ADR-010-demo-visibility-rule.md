# ADR-010: Demo-only visibility rule (UNDECIDED)

**Status**: ASSUMED (`--auto` default = keep; product rule unconfirmed; blocks S4 and S7 acceptance)
**Date**: 2026-10-09 · **Depends on**: ADR-000 A5, consequential assumption 4

## Context

Three read paths filter by the `User.demo` flag (M-11, C-23): list articles, list comments, and popular tags
(`article.service.ts:8-67, 416-431`, `tag.service.ts:4-14`). Anonymous viewers see only demo content. A logged-in
viewer sees demo content plus their own. Feed, single article and profile are **not** filtered. The rule hides every
real user's content from everyone else. That contradicts the RealWorld spec, and it looks like containment for the
public demo host (inferred, with no comment explaining it). Registration forces `demo = false` (C-08). Only the seed
sets it to true (C-39).

## Decision

If kept (the `--auto` default):

- `Realworld.Articles.Visibility.visible_to(query, scope)` is one composable query function.
- It is applied **exactly** in `list_articles/2`, `list_comments/2` and `popular_tags/1`.
- `feed/2`, `get_article/2` and `Profiles.get_profile/2` do not call it.
- The predicate is written once: `author.demo == true OR author.id == ^scope.user_id`, with an anonymous scope
  matching demo authors only. The exact predicate per path is confirmed against the legacy source in slice S4.

If dropped: the function and its three call sites are deleted, and behaviour follows the RealWorld spec. The
divergence becomes pending.

If made configurable: a runtime flag (`DEMO_VISIBILITY=true|false`) chooses between the two. This is the option for
a product that needs both the demo host and real instances.

## Guarantees

| Guarantee | Keep | Drop |
|-----------|------|------|
| Same results per viewer on list, comments and tags | kept | **changed**: every user sees all content |
| Unfiltered feed, single article and profile | kept | kept |
| `demo` never client-set | kept | kept |

## Alternatives

Keep, drop or make configurable, as above. A rule spread over three services (the legacy shape) is rejected: one
function owns the predicate (ADR-002).

## Consequences

- If kept, a real deployment with real users shows them nothing but demo content on the home page. The product owner
  must confirm this is intended.
- Seed relevance in production (S8) follows from this decision.

## Validation

- Evidence needed: the product owner's answer, plus counts of `demo = false` users and articles in prod.
- Goldens per viewer class (anonymous, demo user, real user with their own content) on all six read paths, three
  filtered and three unfiltered.

## Ledger IDs

M-11, M-22, M-26, C-08, C-23, C-29, C-39
