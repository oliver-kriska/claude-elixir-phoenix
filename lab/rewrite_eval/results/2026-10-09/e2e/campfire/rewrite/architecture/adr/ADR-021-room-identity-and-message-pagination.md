# ADR-021: Direct-room identity inside one IMMEDIATE transaction; `(created_at, id)` keyset pagination

**Status**: proposed (auto; needs approval). DV-14 (pagination tie-break) and DV-17 (DM race closed) pending.
**Date**: 2026-10-09

## Context

- `Rooms::Direct.find_or_create_for` scans every DM comparing user sets (FIXME); no constraint, so concurrent creates can duplicate (M-12, T-10).
- Pagination uses strict `created_at <`/`>` with no tie-breaker; messages sharing a timestamp at a page edge can be skipped (M-60, T-08). Triage for both is `preserve` (ASSUMED) with a suggested redesign.
- Single writer with `BEGIN IMMEDIATE` serializes all writers (ADR-003); no DDL is allowed that Rails cannot tolerate during the rollback window.

## Decision

- **DM lookup**: a membership-group query scoped to the first user's DMs (`GROUP BY room_id HAVING count(*) = n AND sum(user_id IN (...)) = n ORDER BY room_id LIMIT 1`), run inside the writer transaction that also creates the room if absent. No schema change. A `direct_member_key` column is deferred unless measured (ecto consult Q5).
- **Pagination**: keyset on `(created_at, id)` for `before`/`after`/`page_around` and the bot API. The client still sends a message id; the wire is unchanged. Optional additive index `port_messages_room_id_created_at_index` only if the baseline shows a room-load benefit (ADR-004 port-only DDL).
- **Room type invariants**: `Rooms.get_room!(scope, id, types: [...])` per route namespace; changeset rejects any type change of a direct room; closed→open grants every active user (M-13, C-05).

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| One DM per exact user set | **changed (strengthened)** (DV-17): concurrent creates no longer duplicate | members |
| Page boundaries | **changed** (DV-14): ties no longer skipped; pending approval, fallback is the strict legacy predicate | room page, bot API |
| Direct rooms never change type; scoped lookups per namespace | kept | security |

## Alternatives

- Unique member-set key column + partial index. Deferred: second source of truth that Rails does not maintain.

## Consequences

- `ORDER BY room_id` picks the lowest id if legacy duplicates exist, matching Rails' `detect` in practice.

## Validation

- Concurrent DM create test (two tasks) → one room.
- 41 messages with identical `created_at` paginate without loss (port), and the strict predicate test documents the legacy behavior.
- Ported directs/opens/closeds controller tests including "a direct room can't be promoted to open".

## Ledger IDs

M-12, M-13, M-60, C-05
