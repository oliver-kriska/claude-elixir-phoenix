# ADR-016: Abuse controls without Redis — Hammer login limit, DB-backed banned-IP check, Rails-equivalent client IP

**Status**: ASSUMED (auto; needs approval). Behavior change DV-10.
**Date**: 2026-10-09 · **Bar**: ADR-000 C-42 "keep (BEAM-native store)"

## Context

- Login: `rate_limit to: 10, within: 3.minutes, only: :create` in `Rails.cache` (non-persistent Redis), key = `remote_ip`, counter increments on every `POST /session` including successes, fixed window starting at the first hit, 429 rendering the login page (M-47, R-23, T-19).
- Banned IPs: any non-GET/HEAD request from a banned `remote_ip` → 429; GETs work (M-17, C-42). `bans` stores public IPs only.
- `remote_ip` trusts loopback and private proxies and takes the rightmost untrusted `X-Forwarded-For`. Behind Thruster (ADR-019), every client otherwise appears as 127.0.0.1 (security consult Q3.11, otp consult R5).

## Decision

- **`CampfireWeb.Plugs.RemoteIp`**: mirrors Rails' trusted-proxy list (loopback, RFC 1918, ULA, link-local) and rightmost-untrusted selection; IP strings normalized to Rails' textual form (IPv6 compression, IPv4-mapped). Used by bans, rate limit and `sessions.ip_address`.
- **Login limit**: `Campfire.RateLimit` = `use Hammer, backend: :ets` (Hammer 7.5.0, KB verified 2026-10-09), algorithm `:fix_window`, 10 per 180 s per client IP, a plug on `POST /session` only, counting before the action, 429 with the login page and flash "Too many requests or unauthorized." State lost on restart (parity with non-persistent Redis).
- **Banned IPs**: `Moderation.ip_banned?/1` = indexed `SELECT 1 FROM bans WHERE ip_address = ? LIMIT 1` on the reader Repo, run only on non-GET/HEAD. No cache until measured (ADR-017).

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| 10 login attempts per 3 min per IP → 429 | **changed** (DV-10): Hammer's fixed windows are clock-aligned, so up to 20 attempts can land across one window edge; legacy windows start at the first hit | abuse protection |
| Banned IP: writes 429, reads allowed | kept | operators |
| Client IP resolution identical to Rails behind the proxy | kept (vector table) | bans, limits, sessions |

## Alternatives

- A 40-line ETS limiter reproducing the first-hit window exactly (security consult Q4). Kept as the fallback if DV-10 is rejected; it is a hand-rolled component and needs this ADR amended.
- ETS cache of banned IPs. Deferred until the write-path profile shows the indexed lookup matters.

## Consequences

- Hammer runs one ETS table and one cleanup process under `Campfire.Services`.

## Validation

- 11th POST within the window → 429; successful logins count.
- `remote_ip` vector table from the pinned image (security consult vector 10), including spoofed XFF from an untrusted peer.
- Banned IP: POST → 429, GET → 200 (ported `block_banned_requests_test`).

## Ledger IDs

M-17, M-47, R-23, C-17, C-42
