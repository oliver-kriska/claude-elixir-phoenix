# ADR-010: Atomic multi-write context operations (strengthening)

**Status**: proposed · **Date**: 2026-10-09

## Context
Legacy runs in autocommit with no `transaction.atomic` anywhere (M-21): registration can leave a user without a profile (M-01, C-05), article create
can commit with only some tags (M-20), user and profile updates commit separately (M-18). The legacy guarantee is "each statement commits alone";
the evidence does not show any consumer relying on partial state.

## Decision
`Repo.transact/2` (or `Ecto.Multi`) per multi-write context operation: register (user + profile), update user (user + profile), create article
(article + tags + article_tags), update article (article + article_tags replace), any parent delete (children first). Single-statement writes run alone.
The writer Repo uses `BEGIN IMMEDIATE` (ADR-003). Nothing slow runs inside a transaction.

## Guarantees
- Changed (strengthening): atomicity of the operations above (DV-20). Consumers: none observable except that partial-failure states disappear.
- Kept: visibility is synchronous at commit, as in legacy.

## Alternatives
Keep autocommit for parity: preserves a defect class with no consumer; rejected.

## Consequences
The C-09 slug retry (if approved) can retry inside the transaction (a failed statement does not abort an SQLite transaction; consult Q3).

## Validation
Fault-injection tests: profile insert failure → no user row; tag insert failure → no article row.

## Ledger IDs
M-01, R-20, C-05, M-18, M-21, M-20, C-07, M-02, R-21, C-06
