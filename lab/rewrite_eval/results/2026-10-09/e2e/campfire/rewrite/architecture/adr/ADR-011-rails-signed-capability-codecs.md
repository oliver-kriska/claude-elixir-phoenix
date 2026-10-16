# ADR-011: Rails-format signed capabilities in `Campfire.Compat.Rails` (avatar, transfer, blob, sgid, Turbo stream names)

**Status**: ASSUMED (auto; needs approval). Kept contracts with a real cost.
**Date**: 2026-10-09 · **Bar**: ADR-000 (ASSUMED) Identity and Data sections

## Context

- ADR-000 keeps every signed URL and stored mention: avatar URLs with no expiry (C-23), 4 h transfer links (C-24), unauthenticated blob redirect URLs with no expiry (C-27), sgid mentions inside stored Action Text HTML including Rails 7 Marshal-wrapped ones (C-10, M-38), and signed Turbo stream names held by open tabs (M-29, C-41).
- Rollback is "restore the pre-upgrade backup", but the pinned Rails image must still boot on and read a port-written DB (ADR-000 Cutover). Durable capabilities minted by the port must therefore verify in Rails.
- Every parameter (PBKDF2 digest, HMAC digest, envelope shape, purpose strings, url-safety) is `needs-vector` (security consult Q1). The same KDF as Plug means salt collisions are possible (security consult R4).

## Decision

1. One private codec `Campfire.Compat.Rails.MessageVerifier` (HMAC envelope `<b64>--<hex>`, `_rails` metadata, exact `pur` match, `exp` check, strict base64, size cap, `Plug.Crypto.secure_compare/2`). Purpose is a required argument with no default. There is no public "verify anything" function.
2. Thin public modules, one per purpose, each with its own key derived once at boot into `:persistent_term`:

| Module | Verifies legacy | Mints | Why |
|---|---|---|---|
| `SignedId.Avatar` | yes | Rails format (deterministic, no expiry) | stored by bots (`avatar_url`), caches, maybe Lexxy markup |
| `SignedId.Transfer` | yes | Rails format (4 h) | same codec; reusable within 4 h (T-02 preserve) |
| `SignedId.Blob` | yes | Rails format (no expiry) | shared download links never expire; Rails must read port-rendered ones |
| `GlobalId.Attachable` | User: extract `gid://campfire/User/(\d+)` without verifying (legacy tolerance, T-17); others: verify or render as missing | Rails 7.1+ JSON sgid, signed | stored bodies, Rails tolerant reader after rollback |
| `Turbo.StreamName` | yes | Rails format | open tabs at cutover; port-rendered `turbo_stream_from` tags |
| `ActiveStorage.VariationKey` | best effort; a Marshal payload → 404/re-render | Rails format if the vector shows JSON, else port-owned | URLs are per-render, not stored |
| `ActiveStorage.VariationDigest` | n/a | Marshal **encoder** of the transformation hash only | find existing `variant_records` rows |

3. Transient port-only capabilities (disk-service URLs, 5 min) use `Phoenix.Token` with `campfire/px/<purpose>` salts, never a Rails salt.
4. **Never decode Marshal.** Never `String.to_atom`/`Module.concat` on a GID model name; allowlist `"User"`.
5. Mention chips render from the DB user found by id; push and webhook recipients stay room-scoped (`room.users ∩ mentioned`), so a forged unsigned mention cannot notify a non-member (security consult Q3.3).

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| C-23 avatar URLs valid forever; tampered or wrong purpose → 404 | kept (vector-gated) | bots, caches, stored HTML |
| C-24 transfer links valid 4 h, reusable; avatar token on transfer route → 400 | kept | users moving devices |
| C-27 blob redirect URLs work without a session, no expiry | kept | shared links |
| C-10 User mentions resolve with invalid signatures, incl. Rails 7 Marshal form; non-User bad signature → missing | kept (permanent adapter, owner: Chat/Content maintainer) | every stored message |
| C-28 harvested stream name cannot subscribe after revocation | kept (membership check after signature, ADR-008) | members |

## Alternatives

- Port-owned `Phoenix.Token` for everything, redirecting legacy URLs. Rejected: Rails cannot read port-minted capabilities after rollback, and stored avatar URLs and blob links break.
- A general Rails `MessageVerifier` library with a purpose option. Rejected: purpose confusion turns an avatar token into a login (security consult R2).

## Consequences

- These modules are effectively permanent (avatar, blob and sgid have no expiry). Retirement needs an ADR that rewrites stored HTML and accepts breaking shared links.
- SECURITY.md documents the kept weak behaviors: permanent bearer capabilities, reusable transfer links, tolerated unsigned User mentions.

## Validation

- Known-answer vectors 1, 4, 5, 6, 7, 8 from the security consult, generated in the pinned image, in both directions (Rails→port verify, port→Rails verify), stored under `test/fixtures/compat/rails/`.
- Wrong-purpose tests for every pair (avatar↔transfer↔blob).
- A disjoint-salt unit test (Rails salts vs `campfire/px/*`).
- CI greps: no `binary_to_term`, no Marshal decoder, no `MessageVerifier`/`KeyGenerator` outside `lib/campfire/compat/`.

## Ledger IDs

M-29, M-37, M-38, M-44, C-10, C-23, C-24, C-27
