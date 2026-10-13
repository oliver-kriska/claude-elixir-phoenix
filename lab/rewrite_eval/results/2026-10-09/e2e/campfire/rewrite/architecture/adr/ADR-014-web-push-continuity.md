# ADR-014: Web Push continuity — same VAPID keys, rows, payload and service worker; SSRF guard kept

**Status**: proposed (auto; needs approval)
**Date**: 2026-10-09 · **Bar**: ADR-000 (ASSUMED) C-15, C-37..C-39; charter must-keep integration

## Context

- Subscriptions are bound to the VAPID public key and to the service worker at `/service-worker` (scope `/`) (C-15, C-39). Changing either orphans every subscription.
- Payload `{title, options:{body, icon:"/account/logo", data:{path, badge}}}`, `Urgency: high`, subject `mailto:support@37signals.com` (C-37, M-24).
- Endpoint guard: https:443 on five vendor suffixes, public resolved IP at save and re-resolved and pinned at delivery (M-23, C-38). Dead subscriptions (expired, crypto error) are deleted (M-22).
- Recipient rules (M-21): visible, not present, not the author, `everything` or (`mentions` and mentioned); badge = user's unread-room count.

## Decision

- `Campfire.Push` owns `push_subscriptions`. `Push.subscribe/2` keeps "find by (endpoint, p256dh, auth) → revalidate under current rules → touch, else create" (M-64). Logout deletes the device subscription scoped to `user_id` (C-43).
- Encryption: RFC 8291 `aes128gcm` with VAPID (RFC 8292). Candidate library `web_push_elixir` 0.8.0 (KB, verified 2026-10-09; small user base). Adoption is gated on RFC 8291 test vectors and real-browser receipt; otherwise a project-owned module over `:crypto` (≈150 lines) with the same vectors.
- Transport: delivery to the **pinned resolved IP** with SNI and certificate verification for the real host, no proxy, via `Campfire.Http` (ADR-015). `Campfire.Net.Guard` decides "public".
- Fan-out: `Push.Fanout` job per message (ADR-006), recipients and badge sampled at run time, presence from `Rooms.Presence` (ADR-007).
- PWA: `/service-worker` and `/webmanifest` served at the same URLs and content types, CSRF-exempt, unauthenticated (M-65). The service worker JS is the legacy file unchanged.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| Existing subscriptions keep receiving with the same keys | kept (vector + real browser gate) | push users |
| Payload shape and recipient rules | kept | service workers |
| SSRF/DNS-rebinding guard at save and delivery | kept | security |
| Dead subscriptions deleted on 404/410/crypto error | kept | storage |
| At most one notification per device per message | kept (ADR-006) | push users |

## Alternatives

- Per-subscription jobs with retries (T-12 strengthen). Not adopted (ADR-006).
- New VAPID keys. Rejected: every user must re-enable notifications.

## Consequences

- The project owns a small crypto surface if the library fails its vectors.

## Validation

- Decrypt a captured push with a test subscription key; JSON equals the legacy payload.
- Ported `push/subscription_test` (18 tests) and `persistent_request_test`; permitted host resolving to 10.x is skipped at delivery.
- A legacy-created subscription receives a port-sent test notification in Chrome, Firefox and Safari.

## Ledger IDs

M-21, M-22, M-23, M-24, M-64, M-65, R-09, R-31, C-15, C-37, C-38, C-39
