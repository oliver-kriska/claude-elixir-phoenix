# ADR-002: Context map from invariants — Accounts, Social, Articles; Profile kept as a schema

**Status**: proposed · **Date**: 2026-10-09

## Context
Django splits code into `authentication`, `profiles`, `articles`, `core`. The invariants cut differently: "every user has exactly one profile"
(C-05) ties User and Profile; the follow graph has its own invariants (directed, unique pair, self-follow refusal, C-28, C-38); favorites, tags and
comments only matter through the article (favoritesCount, tagList, scoped comment delete, C-20, C-23, C-33). `articles_article.author_id`,
`articles_comment.author_id` and the pair tables reference **profile** ids, not user ids (contracts "Data Schema Notes"; consult Q1, Q8).

## Decision
| Context | Owns | Enforces |
|---------|------|----------|
| `Conduit.Accounts` | User, Profile, Password, Token, Scope | uniqueness (C-04), one profile per user atomically (C-05), credentials (C-02, C-13), tokens (C-11, C-14, C-15), is_active (C-12) |
| `Conduit.Social` | Follow | directed idempotent follow (C-28), self-follow policy (C-38, UNDECIDED) |
| `Conduit.Articles` | Article, Tag, ArticleTag, Favorite, Comment | slugs (C-06), tags (C-07), authorship (C-32, C-33), favorites (C-28), ordering and paging (C-23, C-24) |

- Profile stays a real schema; it is **not** folded into User (folding needs destructive DDL and breaks the rollback hand-back, consult Q1).
- `%Accounts.Scope{user, profile}` is built once per request (one join) and passed explicitly; contexts use `scope.profile.id`.
- Cross-context calls are named: `Articles` → `Social.followed_profiles_query/1`, `Social.following_ids/2`; `Social` → `Accounts.get_profile_by_username/1`.

## Guarantees
Kept: C-01, C-04, C-05 (strengthened, ADR-010), C-28. Changed: none here.

## Alternatives
- One context per Django app (Authentication, Profiles, Articles): mirrors the legacy tree and splits the C-05 invariant across two owners; rejected.
- A single `Conduit.Blog` context: hides the auth boundary that carries the security changes; rejected.

## Consequences
Controllers never handle profile vs user ids. Favorites live in `Articles` even though the table is `profiles_profile_favorites` (names are data, ownership is behaviour).

## Validation
Context tests per invariant (architecture.md section 2); no controller calls `Repo`.

## Ledger IDs
M-39, M-40, C-01, M-22, M-24, M-30
