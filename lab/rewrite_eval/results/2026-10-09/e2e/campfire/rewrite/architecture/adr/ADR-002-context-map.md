# ADR-002: Context map drawn from invariants

**Status**: proposed (auto; needs approval)
**Date**: 2026-10-09 · **Bar**: ADR-000 (ASSUMED)

## Context

The legacy app groups code by Rails model and controller (`app/models/user/*`, `app/models/room/*`, `messages_controller.rb`). Several invariants span models:

- "Access ends everywhere when revoked": `sessions`, `users.status`, socket disconnects (M-07, M-16, M-17).
- "A message commit implies unread, index, push and webhook intents": `messages`, `action_text_rich_texts`, `message_search_index`, `memberships.unread_at`, jobs (M-01, M-02, C-13).
- "Room audience": `rooms.type`, `memberships`, open-room auto-membership, DM set identity (M-06, M-12, M-13).

## Decision

Eight contexts plus four support namespaces. Each context owns the tables whose invariants it enforces. Every write to a table goes through its owner (a Repo-call boundary check enforces it).

| Context | Owns (tables) | Invariants enforced |
|---|---|---|
| `Campfire.Accounts` | `accounts`, `users` (human lifecycle), `sessions` | one account (singleton guard); only `active` users authenticate; a `sessions` row is the only proof of login (C-08); join code; first run; deactivation frees the email |
| `Campfire.Rooms` | `rooms`, `memberships`; in-memory presence (`Rooms.Presence`) | open rooms include every active user; one direct room per exact user set; direct rooms never change type; room access = membership; revocation closes sockets |
| `Campfire.Chat` | `messages`, `action_text_rich_texts`, `boosts`, `message_search_index`, `searches` | message + body + index + derived state commit together; unread marking for non-present members; FTS rowid = message id; only reachable messages are readable or searchable |
| `Campfire.Moderation` | `bans` | banned users lose access and content; banned public IPs cannot write |
| `Campfire.Bots` | `webhooks`; bot lifecycle on `users` (role `bot`, `bot_token`) | bot key format and authentication; webhook payload; replies never trigger webhooks |
| `Campfire.Push` | `push_subscriptions` | endpoints on allowed hosts and public IPs only; recipients by involvement and presence; dead subscriptions removed |
| `Campfire.Files` | `active_storage_blobs`, `active_storage_attachments`, `active_storage_variant_records`, files under `storage/files` | key layout and variants stay readable by Rails; dangerous decoders never run; files purged after their rows |
| `Campfire.Unfurl` | none | link previews only for public addresses |

Support namespaces (no tables, no processes unless listed in the process table):

- `Campfire.Content` (pure): sanitizer allow-list, plain text, mentions, opengraph embed filter, sounds, emoji-only check.
- `Campfire.Net.Guard` (pure): the shared private-network policy (port of surfguard).
- `Campfire.Compat.Rails` (pure): Rails crypto and format codecs, one module per purpose (ADR-010, ADR-011).
- `Campfire.Release`: boot migrator, admin commands, backup.

### Public functions (first cut; every one takes `%Scope{}` first where an actor exists)

- `Accounts`: `first_run(attrs)`, `register_via_join_code(code, attrs)`, `authenticate_by_password(email, password, conn_info)`, `fetch_session(token)`, `resume_session(session, conn_info)`, `end_session(scope, push_endpoint)`, `transfer_session(transfer_id, conn_info)`, `update_profile(scope, attrs)`, `update_account(scope, attrs)`, `set_role(scope, user, role)`, `deactivate_user(scope, user)`, `reset_join_code(scope)`, `reset_password(email, password)` (release only).
- `Rooms`: `list_sidebar(scope)`, `get_room!(scope, id, types: [...])`, `create_open(scope, attrs)`, `create_closed(scope, attrs, user_ids)`, `find_or_create_direct(scope, user_ids)`, `update_room(scope, room, attrs, user_ids)`, `delete_room(scope, room)`, `set_involvement(scope, room, involvement)`, `mark_read(user_id, room_id)`, `fetch_membership(user_id, room_id)`, `grant_open_rooms_multi(multi, user)`, `mark_unread_multi(multi, message, present_ids)`.
- `Chat`: `create_message(scope, room, attrs, deliver_webhooks: boolean)` (required keyword), `update_message(scope, message, attrs)`, `delete_message(scope, message)`, `page(scope, room, cursor)`, `page_around(scope, room, message_id)`, `refresh(scope, room, since)`, `boost(scope, message, content)`, `unboost(scope, boost_id)`, `search(scope, query)`, `recent_searches(scope)`, `clear_searches(scope)`.
- `Moderation`: `ban_user(scope, user)`, `unban_user(scope, user)`, `ip_banned?(ip)`.
- `Bots`: `authenticate(bot_key)`, `create_bot(scope, attrs)`, `update_bot(scope, bot, attrs)`, `reset_key(scope, bot)`, `deactivate_bot(scope, bot)`, `webhook_targets(message, room)`.
- `Push`: `subscribe(scope, attrs)`, `unsubscribe(scope, endpoint)`, `list_devices(scope)`, `send_test(scope, subscription)`.
- `Files`: `attach(record_ref, upload)`, `fetch_blob_by_signed_id(sid)`, `variant(blob, name)`, `purge_multi(multi, attachment)`.
- `Unfurl`: `fetch(url, our_host)`.

### Cross-context calls

| Caller | Callee | Why |
|---|---|---|
| `Accounts.register_*`, `Bots.create_bot`, `Accounts.first_run` | `Rooms.grant_open_rooms_multi/2` | new users join all open rooms in the same transaction (M-06) |
| `Chat.create_message` | `Rooms.mark_unread_multi/3`, `Rooms.Presence.user_ids/1`, `Bots.webhook_targets/2`, `Files.attach/2` | unread, presence sampling at commit, webhook intents, attachment rows |
| `Moderation.ban_user` | `Accounts.revoke_access_multi/2`, `Chat` batch deletion (worker) | sessions deleted and status set in the ban transaction |
| `Accounts.deactivate_user` | `Rooms` (delete non-direct memberships), `Push`, `Chat` (searches) | one transaction (M-16) |
| `Bots.WebhookDelivery` worker | `Chat.create_message(..., deliver_webhooks: false)` | reply loop guard (M-20) |
| `Push.Fanout` worker | `Rooms.Presence.user_ids/1`, `Chat` unread counts | run-time sampling |

### Events (PubSub, after commit only)

| Topic (core-owned) | Events | Emitted by |
|---|---|---|
| `"room:<id>"` | `{:message_created, msg}`, `{:message_updated, msg}`, `{:message_deleted, msg}`, `{:boost_added, boost}`, `{:boost_removed, boost}` | Chat |
| `"user:<id>"` | `{:room_unread, room_id}`, `{:room_read, room_id}`, `{:sidebar, op, room}`, `{:sockets_revoked, reconnect: boolean}` | Chat, Rooms, Accounts, Moderation |
| `"rooms:open"` | `{:sidebar, op, room}` (global open-room list; room removals for any type, parity) | Rooms |
| `"typing:room:<id>"` | `{:typing, :start | :stop, %{id, name}}` | shim only (ephemeral) |

### Jobs (Oban, inserted in the owning transaction)

`Bots.WebhookDelivery`, `Push.Fanout`, `Moderation.RemoveBannedContent`, `Files.PurgeBlob` (ADR-006).

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| C-13 derived state on every write | kept, now atomic with the write (DV-01) | sidebar, unread, refresh, push |
| C-28 stream authorization | kept | members of closed and direct rooms |
| First run atomic (account, "All Talk", admin) | **changed (strengthened)** (DV-18) | first-run operators |
| Open-room grants in the user-create / room-convert transaction | **changed (strengthened)** (DV-19) | new users, bots |

## Alternatives

- One context per legacy model (`Users`, `Messages`, `Boosts`, `Webhooks`, ...). Rejected: it splits the access-revocation and message-commit invariants across owners and invites the Rails callback chain back as cross-context calls in the wrong order.
- A single `Campfire.Chat` mega-context. Rejected: room audience and identity have separate invariants and separate test surfaces.

## Consequences

- Admin scripts, the bot API, webhook replies and Oban workers call the same context functions as the browser controllers. No compat module writes tables.
- `users` is written by two contexts (Accounts for humans, Bots for bot-specific columns). Both use `Campfire.Accounts.User` changesets; Bots never writes `password_digest` or `status` except through `Accounts.deactivate_user/2`.

## Validation

- Boundary or Credo check: `Repo.insert*/update*/delete*/query*` only under `lib/campfire/<context>/` and `Campfire.Release`.
- Derived-state property test per public write function (C-13).
- Permission matrix generated from the legacy controller tests (M-48).

## Ledger IDs

M-01, M-05, M-06, M-11, M-13, M-16, M-17, M-48, C-13, C-28
