# ADR-015: Outbound HTTP through `Req` on named Finch pools; `Campfire.Net.Guard` ports surfguard

**Status**: proposed (auto; needs approval)
**Date**: 2026-10-09

## Context

- Three outbound flows: bot webhooks (admin-chosen URL, **no SSRF guard by design**, 7 s open and read timeouts, C-35/C-36), push delivery (vendor hosts, pinned IP, M-23), and link unfurl (any public URL, pinned IP, ≤10 redirects each re-resolved, 200 + exactly `text/html`, ≤5 MB, og image HEAD check, twitter/x → fxtwitter.com, M-42).
- One shared "what is internal" policy (`RestrictedHTTP::PrivateNetworkGuard` → surfguard), deliberately shared across 37signals apps (M-43). Its Elixir owner is open (mechanisms Q6).

## Decision

- **`Campfire.Http`**: a project-owned module over `Req` 0.7.5 and `Finch` 0.24.0 (KB, verified 2026-10-09). Three named Finch instances under `Campfire.Services`: `Finch.Webhook` and `Finch.Unfurl` (with `pool_max_idle_time` because origins are arbitrary) and `Finch.Push`. A stuck bot endpoint cannot starve push.
- **Pinned connections**: `Campfire.Http.pinned_request/3` connects to a resolved IP with `hostname:` for SNI and certificate verification, no proxy, `redirect: false`. Unfurl follows redirects manually (≤10), re-resolving and re-checking each hop, and caps the body with a streaming `into:` collector.
- **`Campfire.Net.Guard`** (pure): `resolve_public_ips/1` and `public_ip?/1` porting surfguard's ranges and test vectors. **Owner**: the `Campfire.Unfurl` maintainer, who tracks surfguard releases (an UNDECIDED owner question surfaced to the user; the module ships regardless).
- **Webhooks** use plain `Req` with `connect_options: [timeout: 7_000]` and `receive_timeout: 7_000` and **no** Net.Guard (SECURITY.md intentional behavior, C-35).
- Unfurl stays synchronous in the request (`POST /unfurl_link`, R-34).

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| Unfurl and push never reach private, loopback or link-local addresses, incl. via DNS rebinding and redirects | kept (vectors) | security |
| Webhook reaches admin-chosen internal URLs | kept (intentional) | bot operators |
| 7 s webhook connect and read budgets; timeout → "Failed to respond within 7 seconds" | kept | bots |
| Pool isolation per flow | new, internal | — |

## Alternatives

- One shared Finch pool. Rejected: a slow webhook origin can exhaust it.
- Apply Net.Guard to webhooks. Rejected: breaks the documented contract (needs its own ADR and approval).

## Consequences

- `receive_timeout` in Req/Mint is per receive like Net::HTTP `read_timeout`; a slow-drip body can exceed 14 s total, as in legacy. The worker `timeout/1` is 30 s (ADR-006).

## Validation

- surfguard vector table ported (IPv4, IPv6, IPv4-mapped, NAT64, CGNAT, multicast).
- Unfurl: redirect to 127.0.0.1 rejected; 6 MB body aborted; non-`text/html` → 204.
- Webhook stub server: 8 s sleep → timeout message; `http://10.0.0.5` allowed.

## Ledger IDs

M-20, M-23, M-42, M-43, R-30, C-35, C-36, C-38, C-48
