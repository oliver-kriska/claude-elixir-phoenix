# ADR-005: One transaction per message write; broadcasts after commit

**Status**: proposed (auto; needs approval). Behavior change recorded as DV-01, DV-12.
**Date**: 2026-10-09

## Context

Legacy (M-01, M-02, M-03): the message and its rich text commit together. After commit, separate statements write the FTS row, mark unread memberships and enqueue push to non-persistent Redis. The controller then broadcasts and enqueues webhooks. A crash between these steps loses unread state, the index row or the job. "Redis down" returned 500 for a saved message. Webhook replies skip the webhook trigger because it lives in the controller (the de facto loop guard).

## Decision

`Chat.create_message(scope, room, attrs, deliver_webhooks: boolean)` is the only message-insert path. `deliver_webhooks` is a required keyword with no default. One writer `Repo.transact/2` (or `Ecto.Multi`) holds, in order:

1. message row (`client_message_id` from the client, or a UUID for bots);
2. rich-text body row (`record_type = "Message"`, `name = "body"`); attachment rows (the blob file is written **before** the transaction);
3. FTS upsert: delete + insert for `rowid = message.id`, body = `Content.PlainText` (C-09);
4. room touch (`rooms.updated_at = now`);
5. unread: `memberships` of the room, visible, `user_id NOT IN ^present_ids`, `user_id != creator` → `unread_at = message.created_at, updated_at = now`. `present_ids` is read from `Rooms.Presence` inside the transaction (ADR-007);
6. `Oban.insert` one `Push.Fanout` job (`message_id`);
7. when `deliver_webhooks: true`, one `Bots.WebhookDelivery` job per eligible bot (DM: every active bot member with a webhook; otherwise mentioned active bots; never the author).

After `{:ok, _}`: broadcast `{:message_created, msg}` on `"room:<id>"` and `{:room_unread, room_id}` on every member's `"user:<id>"` (author included, the client filters).

Update, delete, boost and unboost follow the same rule (C-13 touches in the transaction, broadcasts after). Callers: browser controller (`deliver_webhooks: true`), bot API (`true`, T-07 kept), webhook reply (`false`), ban removal (delete path).

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| Atomicity: message, body, index, room touch, unread, job intents | **changed (strengthened)**: all-or-nothing; legacy after-commit gaps closed (DV-01) | sidebar, search, push, bots |
| Visibility: broadcasts only after commit | kept | viewers |
| Loop guard: webhook replies never enqueue webhooks | kept, now explicit and tested | bot endpoints |
| Callback order (FTS before unread before push) | kept (all in one transaction) | — |
| FTS index repair on update (legacy `UPDATE` no-op when the row is missing) | **changed**: delete+insert repairs the row (DV-12) | search users |
| Retried POST creates a duplicate (no `client_message_id` uniqueness) | kept (M-04) | bundled JS |

## Alternatives

- Port the callbacks as after-commit steps. Rejected: keeps the crash windows that an in-transaction Oban insert removes.
- SQLite triggers for FTS. Rejected while the rollback window is open: Rails also writes the index from app code, so a trigger would double-write after rollback.

## Consequences

- The transaction is short but does more statements than Rails' first transaction. Measure writer checkout queue time in the chat-burst baseline.
- `Content.PlainText` must match Rails `to_plain_text` (FTS, push body, webhook `plain`). Parity fixtures are a gate.

## Validation

- A rollback test: a failed FTS insert leaves no message, no unread change and no job.
- `assert_enqueued` inside the transaction (`testing: :manual`).
- The F-24 negative probe: a reply creates no webhook job.
- C-13 property test.

## Ledger IDs

M-01, M-02, M-03, M-04, R-27, C-09, C-13, C-35, C-37
