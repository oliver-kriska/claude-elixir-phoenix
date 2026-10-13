# ADR-007: In-memory room presence (Registry) replaces DB connection counters

**Status**: ASSUMED (auto; needs approval). Behavior change recorded as DV-05.
**Date**: 2026-10-09

## Context

- Legacy presence lives in `memberships.connections` and `connected_at` (60 s TTL). The JS sends `present` and `absent` on visibility, with a 5 s delay, and `refresh` every 50 s. `Membership.disconnect_all` runs at Puma boot (M-28, R-05).
- Readers: unread marking (at commit) and push recipients (at job run). Nothing external, no admin script and no contract reads the columns (otp consult Q1).
- Platform reason: Puma workers share no memory, so the DB was the shared store. The cost under one SQLite writer is one write per visible room tab every 50 s. Counter updates are read-modify-write in Ruby and lose updates across tabs.
- Business reason (kept): "if you are looking at the room, it is not unread and you get no push". `present` also marks the membership read and broadcasts `user_<id>_reads`.

## Decision

- `Campfire.Rooms.Presence` is a facade over a `Registry` (`keys: :duplicate`, partitioned by scheduler count). Key `{:room, room_id}`, value `{user_id, identifier}`, registered by the Action Cable connection process that holds the `PresenceChannel` subscription.
- The 60 s window is kept in memory: a per-subscription `Process.send_after` timer is reset on `present` and `refresh` and unregisters on expiry. This covers half-open sockets after a laptop sleeps.
- Unregister uses `Registry.unregister_match/4` on the identifier. Process death removes the entries.
- `Rooms.Presence.user_ids(room_id) :: MapSet` is read by `Chat.create_message` inside the transaction (unread) and by `Push.Fanout` at run time (push). This matches legacy sampling times.
- `present` still performs the business write (`unread_at = nil`) and broadcasts `{:room_read, room_id}`. The write runs in a `Task.Supervisor` child, so the socket process never blocks on the writer.
- The port never reads or writes `memberships.connections` and `connected_at`. The columns stay (no destructive DDL during the rollback window) and are ledgered for retirement after it closes.
- No boot reset: the registry starts empty.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| Present member is not marked unread and gets no push | kept | members |
| Liveness window 60 s after the last refresh | kept (in memory) | members with sleeping laptops |
| Restart → nobody present until clients resubscribe | kept | members |
| Exact multi-tab counting | **changed (strengthened)**: no lost updates (DV-05) | members |
| A crashed or closed connection stops counting immediately instead of after up to 60 s | **changed** (DV-05) | members, push |
| `memberships.connections` / `connected_at` stay current | **changed**: no longer written (DV-05). Rails resets them at boot after a rollback (`config/puma.rb:51`) | Rails after rollback only |

## Alternatives

- **Keep the DB counters** (MAP). Rejected: about 10 writer transactions per second of bookkeeping per 500 visible tabs on the single writer, plus a boot reset child.
- **`Phoenix.Presence`**. Acceptable, not chosen: CRDT diffs that no client consumes, and an asynchronous propagation window. The facade allows a swap if the app is ever clustered (SQLite pins it to one node).

## Consequences

- Presence is per node. Fine for the single-node ONCE appliance; documented.
- The registry is the only presence state. Losing it (VM restart) equals legacy `disconnect_all`.

## Validation

- F-12 probes: two tabs and one closed → still present; a tab dead 61 s without unsubscribe → unread; restart → nobody present; membership removed → entries gone.
- Rollback probe: after the port runs, boot the pinned Rails image; no membership claims to be connected.

## Ledger IDs

M-28, M-27, R-05, C-13
