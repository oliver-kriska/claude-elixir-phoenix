# ADR-002: Three contexts by invariant: Accounts, Profiles, Articles

**Status**: proposed
**Date**: 2026-10-09 · **Depends on**: ADR-000 (ASSUMED)

## Context

The legacy code is organised by route folder: `auth`, `profile`, `article`, `tag`. Each folder has its own
controller, service and mapper. Rule 1 asks for contexts drawn from shared invariants, not legacy directories.
The invariants found in analysis:

- Identity: unique email and username, the `demo` flag never client-set, bcryptjs hashes, the token format (C-02,
  C-05, C-08, C-12, C-16).
- The follow graph: the `_UserFollows` A/B direction (C-03, V-1). Three surfaces read it: the profile `following` flag,
  the author `following` flag inside articles, and the feed.
- Content: slug uniqueness and format (C-11), author-only edit and delete (M-12), the atomic tag set (ADR-012), DB
  cascades (C-09), the demo visibility rule over list, comments and tags (C-23), and `updatedAt` semantics (C-04).

## Decision

- **`Realworld.Accounts`** owns `"User"`, `Token` and `Scope`.
- **`Realworld.Profiles`** owns `"_UserFollows"`. It exposes composable queries (`followed_ids_query/1`,
  `following_flag/3`) that `Articles` uses read-only.
- **`Realworld.Articles`** owns `"Article"`, `"Comment"`, `"Tag"`, `"_ArticleToTag"` and `"_UserFavorites"`.
  Comments and tags stay in `Articles`, because the visibility rule, the ownership check and the cascade cover all
  three. Splitting them would spread one product rule over three owners.
- Identity travels as an explicit `%Accounts.Scope{user_id: id | nil}` argument, never through the process
  dictionary (M-32).

Public functions are listed in architecture.md section 2.

## Guarantees

No wire or data guarantee changes. This ADR only decides ownership.

| Guarantee | Owner |
|-----------|-------|
| Follow direction A = followed, B = follower (pending V-1) | Profiles, the single place to flip if V-1 says otherwise |
| Visibility applied on exactly list, comments and tags (if C-23 is kept) | Articles (`Articles.Visibility`) |
| Identity only from a verified token | Accounts plus the `RealworldWeb.Plugs.Auth` edge |

## Alternatives

- **Five contexts that mirror the route folders** (`Auth`, `Profiles`, `Articles`, `Comments`, `Tags`). Rejected:
  Comments and Tags would each wrap one table and would need to call back into Articles for visibility and ownership.
- **Fold Profiles into Accounts.** Viable, since Profiles is close to the "wraps one table" smell. Rejected because
  the follow graph has its own blocking verification (V-1) and three readers. One owner keeps the A/B mapping
  in a single module, so a V-1 surprise is a one-line `join_keys` swap.

## Consequences

- `Articles` depends on `Profiles` for query composition only. `Profiles` never calls `Articles`, so there is no cycle.
- Favorites live in `Articles` even though they are a user-to-article edge. They share the article's existence,
  the cascade and the `favoritesCount` read path.

## Validation

- `mix xref graph --label compile-connected` shows no cycles between contexts.
- The V-1 golden fixture (the follow row inserted by the pinned legacy build) passes against `Profiles` and `Articles.feed/2`.

## Ledger IDs

M-12, M-16, M-23, M-32, C-03, C-24, C-28
