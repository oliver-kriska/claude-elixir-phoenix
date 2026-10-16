# ADR-017: No fragment or response cache; HTTP caching headers kept

**Status**: proposed (auto; needs approval). Behavior change DV-15.
**Date**: 2026-10-09

## Context

- Legacy caches rendered message, boost and membership fragments and jbuilder JSON in `redis_cache_store`, with a manual `presentation-v3` version (M-34, R-22). The cached HTML embeds per-request data (boost-form CSRF tokens, absolute hosts, host-dependent embed filtering) and the key lacks the creator, so name and avatar edits stay stale (the profile page says "up to 30 minutes").
- HTTP cache contracts are separate and kept: `fresh_when` ETag/Last-Modified on message pages, avatar 30 min + 1 week SWR, logo 5 min, QR 1 year, disk blobs 1 h public, versioned `?v=` URLs (M-35, C-46).
- Rule: ETS/Cachex only with a measured need; keys include every input; errors never cached.

## Decision

- **DELETE** fragment and JSON caching. HEEx renders per request.
- If the room-load baseline shows a regression attributable to rich-text rendering, the only allowed cache is the **filtered body HTML** keyed by `{message_id, updated_at, filter_version}` in a named ETS table owned by `Campfire.Content.Cache` (an ADR amendment, with measurements). Never per-request data, never `{:error, _}`.
- HTTP caching headers are reproduced by a small `CampfireWeb.Plugs.HttpCache` (`put_resp_header`, ETag from the record version, 304) with the exact legacy values; `?v=` URLs are kept.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| C-46 caching headers and versioned URLs | kept | browsers, proxies |
| Rendered HTML freshness | **changed (strengthened)** (DV-15): name and avatar edits show immediately; no other user's CSRF token or host appears in rendered HTML | members |

## Alternatives

- Port the fragment keys into Cachex. Rejected: ports the cross-user leak.

## Consequences

- Room load does more rendering work per request; measured against the baseline (P1/P2).

## Validation

- `curl -I` header comparison for avatar, logo, QR, blob, message page (C-46 witness).
- Translationese grep: no `Cachex`/`:ets.new` caching of rendered output without an amended ADR.

## Ledger IDs

M-34, M-35, R-22, C-46
