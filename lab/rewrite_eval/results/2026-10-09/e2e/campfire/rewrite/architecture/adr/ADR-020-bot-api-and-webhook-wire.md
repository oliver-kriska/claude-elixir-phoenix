# ADR-020: Bot HTTP API and outbound webhooks stay byte-compatible

**Status**: proposed (auto; needs approval). Kept contract with a real cost.
**Date**: 2026-10-09 · **Bar**: ADR-000 C-30..C-36 "keep, byte-compatible"; charter must-keep integration

## Context

- Inbound: `/rooms/:room_id/:bot_key/messages` (index, create, update, destroy) and `/messages/:id/boosts` (create, destroy); raw body text or multipart `attachment`; 201 + `Location` and empty body; 204; 404 for non-member rooms; 422 when blank; jbuilder JSON; `X-Total-Count`; `Link rel="next"`; JSON default format; bot keys on other routes → 403; CSRF skipped (M-18, M-19, M-60, C-30..C-34).
- Outbound: webhook JSON payload with no signature, 7 s timeouts, reply semantics including the T-06 quirk (non-200 with a recognized content type becomes an attachment), loop guard only for replies (T-07: API posts mentioning another bot still trigger it) (M-20, C-35, C-36).

## Decision

- `CampfireWeb.BotApi.*` controllers in a `:bot_api` pipeline (no session, no CSRF, `Bots.authenticate/1` per ADR-010, JSON default). Bot keys on any other pipeline → 403.
- JSON is built by explicit view functions that reproduce the jbuilder key order and formats (`created_at` UTC ISO8601 with ms and `Z`). Golden JSON fixtures recorded from the pinned image are the contract.
- Raw body read with `Plug.Conn.read_body/2` before parsers for the bot create routes, forced to UTF-8 like Rails.
- Paging per M-60 (40, `before`/`after`), absolute `Link` URLs built from the conn host.
- Webhook delivery per ADR-006 and ADR-015; reply handling reproduces C-36 including T-06 (ASSUMED preserve) and posts via `Chat.create_message(..., deliver_webhooks: false)`. API posts use `deliver_webhooks: true` (T-07 preserve).

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| C-30..C-34 status codes, headers, JSON shapes | kept (golden fixtures) | external bots |
| C-35/C-36 payload, no signature, at-most-once, reply semantics | kept | bot endpoints |
| T-06 / T-07 quirks | kept (ASSUMED triage) | bot authors |

## Alternatives

- Version the API (`/api/v2`). Rejected by the bar.

## Consequences

- JSON views must be maintained byte-for-byte; any change needs a contract ADR.

## Validation

- Replay the two curl recipes from `accounts/bots/_bot.html.erb`; port `by_bots_controller_test` and `boosts/by_bots_controller_test` cases; diff JSON against golden fixtures.
- Webhook stub receiver tests from `webhook_test` (text, attachment, 500 without type, timeout).

## Ledger IDs

M-18, M-19, M-20, M-60, C-26, C-30, C-31, C-32, C-33, C-34, C-35, C-36
