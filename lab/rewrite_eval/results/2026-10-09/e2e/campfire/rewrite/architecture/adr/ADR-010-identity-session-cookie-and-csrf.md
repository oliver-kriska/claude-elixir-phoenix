# ADR-010: Identity — Rails-format `session_token` as the only auth cookie; Plug CSRF; `_campfire_session` not read

**Status**: ASSUMED (auto; needs approval). Changes kept contract C-21 (DV-06); tightenings DV-08 and DV-09.
**Date**: 2026-10-09

## Context

- ADR-000 Identity: no forced logout; the port reads the legacy `session_token` and mints new sessions in the same format so a rollback keeps users logged in. The `sessions` table is the revocation authority (C-08, C-20).
- C-21 `_campfire_session` (AES-256-GCM encrypted cookie store) carries only the CSRF secret and `return_to`. Losing it costs one stale-form 422 and a lost post-login redirect, not a logout.
- Crypto parameters (PBKDF2 digest, cookie HMAC digest, envelope shape) are `needs-vector` (security consult Q1).

## Decision

1. **`Campfire.Compat.Rails.SessionCookie`** verifies and mints `session_token` in Rails' format (signed, not encrypted: `<b64 envelope>--<hex HMAC>`, purpose `cookie.session_token`, 20-year expiry, JSON-quoted token). It is built on a private `Compat.Rails.MessageVerifier` that requires an explicit purpose. Keys are derived once at boot into `:persistent_term`. The DB row is the authority: `Accounts.fetch_session(token)`.
2. **No parallel phx.gen.auth token.** HTTP and the `/cable` shim share one `CampfireWeb.Auth.fetch_current_scope/2`. Attributes: HttpOnly, SameSite=Lax, path `/`, Secure unless `DISABLE_SSL`. Session tokens are `has_secure_token`-shaped (length `verify` on real rows), generated without modulo bias. `last_active_at`, IP and UA refresh at most hourly.
3. **`_campfire_session` is neither read nor written.** The port's Plug session uses a separate cookie (`_campfire_px`) for CSRF, flash and `return_to`. The browser keeps the Rails cookie untouched, so after a rollback Rails' CSRF state is intact.
4. **CSRF** is `Plug.CSRFProtection`. The layout renders `<meta name="csrf-token">` (read by `file_uploader.js` and `@rails/request.js` via `X-CSRF-Token`). A failure maps to **422** with a reload prompt, matching Rails. Exempt: bot-key routes, `/service-worker`, `/webmanifest` only. Whether Rails 8.2 adds a `Sec-Fetch-Site` check under `load_defaults 8.2` is `verify`.
5. **Passwords**: `Bcrypt.verify_pass` on `$2a$` digests; `Bcrypt.no_user_verify/0` when the user is missing, inactive or a bot (NULL digest). The 72-byte truncation is kept. No rehash (no cost change).
6. **`return_to`** stores path + query only and redirects only to local paths (DV-09).
7. **Bot keys**: strict `"<positive int>-<[A-Za-z0-9]{12}>"` parse, load the active bot by id, `Plug.Crypto.secure_compare/2` on the token (DV-08). Keys stay in the URL (T-20).
8. **Endpoint secret**: the raw `SECRET_KEY_BASE` feeds the compat codecs. The Plug session gets it raw when ≥ 64 bytes, or a 64-byte PBKDF2 expansion otherwise. Boot fails if it is missing. Port salts are `campfire/px/<purpose>` and never reuse Rails salts.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| C-20 legacy cookies log in; tampered, expired or wrong-purpose cookies are anonymous | kept (vector-gated) | every logged-in browser and PWA |
| Rails reads port-minted `session_token` after rollback | kept (reverse vectors) | rollback |
| C-08 sessions table is the authority; hourly refresh | kept | ban, logout |
| C-21 CSRF and `return_to` continuity across cutover | **changed** (DV-06): forms rendered by Rails before cutover fail once with 422 and a reload prompt; an in-flight `return_to` is lost | browsers with open forms at cutover |
| C-22 CSRF semantics: token required on non-GET; bots and PWA exempt; 422 | kept (Plug token format, same header and meta tag) | bundled JS, bots |
| C-07 bcrypt hashes verify | kept | every user |
| C-26 bot key format and auth | kept; malformed-but-Rails-accepted keys rejected (DV-08) | bots |

## Alternatives

- Decrypt `_campfire_session` (AES-GCM + session hash parser) to keep CSRF continuity. Rejected: costs a second crypto codec for one stale-form 422 per open tab.
- phx.gen.auth tokens plus a one-way legacy reader. Rejected by the bar: rollback would log everyone out.

## Consequences

- The identity slice is gated on vectors 1, 2, 4, 5, 6 and 7 from the security consult, in both directions (Rails→port and port→Rails).
- SECURITY.md documents kept weak behaviors: permanent avatar and blob capabilities, reusable 4 h transfer links, tolerated unsigned User mentions, the bot key in the path.

## Validation

- Known-answer vectors from the pinned image: valid, tampered, expired, wrong purpose, rotated key, short secret; HTTP and `/cable` agree.
- POST without a token → 422; with the `X-CSRF-Token` header → accepted; bot POST without a token → 201.
- Login timing: unknown email and wrong password take equal bcrypt work.
- CI greps: no `MessageVerifier`/`KeyGenerator` outside `compat/`; no `binary_to_term`/Marshal decode anywhere.

## Ledger IDs

M-09, M-18, M-36, R-29, C-07, C-08, C-20, C-21, C-22, C-26, C-43
