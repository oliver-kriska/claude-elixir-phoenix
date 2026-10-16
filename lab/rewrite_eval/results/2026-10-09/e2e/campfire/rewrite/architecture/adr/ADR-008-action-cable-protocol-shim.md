# ADR-008: Action Cable protocol SHIM at `/cable` over Phoenix.PubSub

**Status**: proposed (auto; needs approval). Kept contract with a real cost.
**Date**: 2026-10-09

## Context

ADR-000 keeps the bundled Hotwire JS unchanged, so `/cable` must speak `actioncable-v1-json` (C-41) with seven channels: Heartbeat, Presence, ReadRooms, UnreadRooms, TypingNotifications, RoomMessages and `Turbo::StreamsChannel`. Phoenix Channels and LiveView do not speak this protocol. `kb/ui-strategy.md` "Traps" allows a protocol shim only in one namespace, translating to and from PubSub, with frame-level conformance tests, an owner and a deletion trigger.

## Decision

- **Namespace**: `CampfireWeb.Compat.ActionCable.{Plug, Socket, Protocol, Channels.*, Encoder}`. Core contexts never reference it. It consumes core topics and calls context functions (`Rooms.fetch_membership/2`, `Rooms.mark_read/2`, `Rooms.Presence`).
- **Transport**: a plug at `/cable` inside `CampfireWeb.Endpoint` calls `WebSockAdapter.upgrade/4`. One process per WebSocket (Bandit supervises it); subscriptions are state in that process.
- **Handshake**: same-host Origin check; respond with subprotocol `actioncable-v1-json`; authenticate through the same session reader as HTTP (`Accounts.fetch_session/1` via the Rails-format `session_token`, ADR-010). If unauthenticated, upgrade, send `{"type":"disconnect","reason":"unauthorized","reconnect":false}`, then close. WebSock `timeout: :infinity`, bounded `max_frame_size`.
- **Protocol**: `welcome`; `ping` every 3 s; `subscribe`, `unsubscribe` and `message` commands. The identifier JSON string is kept verbatim and echoed byte-for-byte. A fixed channel-name map (no `String.to_atom`). Duplicate subscribes are ignored. PubSub topic subscriptions are refcounted.
- **Authorization per subscription**:
  - Presence and Typing: membership at subscribe.
  - RoomMessages: verify the signed stream name (ADR-011), parse the room, check membership.
  - `Turbo::StreamsChannel`: verify the signature and reject any `*:messages` name (C-28).
- **Revocation**: every connection subscribes to `"user:<id>"`. `{:sockets_revoked, reconnect: r}` → `{"type":"disconnect","reason":"remote","reconnect":r}` and stop (ADR-009). Reconnect re-runs authentication and every subscription check.
- **Encode once**: core broadcasts use `Phoenix.PubSub.broadcast/4` with a dispatcher that groups subscribers by the encoder module registered in their subscription metadata. It calls `encoder.encode(event)` once per dispatch (turbo-stream HTML rendered by HEEx once) and sends each subscriber the pre-encoded binary. Connections wrap it with their identifier as iodata. Core passes the dispatcher by config and never names the shim. Subscription `metadata:` support in phoenix_pubsub 2.4.1 is `verify`.
- **Back-pressure**: on each ping tick, a connection whose mailbox exceeds 1,000 messages closes with 1013 (DV-16). ThousandIsland `send_timeout` is set.
- **Typing**: `start` and `stop` broadcast on `"typing:room:<id>"` with the connection's cached `{id, name}`. Ephemeral; the client purges after 5 s.
- **Heartbeat**: confirm only.
- **Owner**: the web-layer maintainer of `CampfireWeb.Compat`. **Deletion trigger**: an approved ADR that moves the UI to LiveView or `<turbo-stream-source>` (retiring C-41, C-48, C-49), plus one release cycle for open tabs to reload.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| C-41 channel names, frames, identifiers | kept | bundled JS, open tabs |
| C-28 authorization at subscribe; a harvested stream name fails after revocation | kept | members |
| Delivery: at-most-once, ephemeral, catch-up via `/rooms/:id/refresh` | kept (PubSub is not durable) | viewers |
| Per-channel ordering from a single publisher | kept (PubSub preserves per-sender order); cross-channel order not guaranteed, as in Rails | viewers |

## Alternatives

- Phoenix Channels or LiveView on `/cable`. Impossible: different protocol.
- Change the JS to `<turbo-stream-source>` now. Rejected: the bar keeps the bundled JS unchanged.
- Shim backed by Redis (once-campfire-elixir). Rejected: Redis is retired (C-59) and was on the hot path.

## Consequences

- The project owns another framework's wire protocol until the deletion trigger. Security fixes in `@rails/actioncable` must be watched.
- Turbo-stream HTML rendering sits in the web layer. Context events stay domain-shaped.

## Validation

- Frame transcripts recorded from the pinned Rails image (welcome, ping, confirm and reject per channel, disconnect variants) replayed against the shim with `Mint.WebSocket`.
- Port the 8 `room_messages_channel_test` cases and the presence, unread and typing channel tests.
- Fan-out benchmark at 100, 500 and 1,000 clients (performance-gates P1-P4), with encode-once verified by call counts.

## Ledger IDs

M-26, M-27, M-29, M-30, M-31, M-33, R-20, C-28, C-41, C-49
