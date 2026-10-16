# ADR-004: Two-way legacy JWT compatibility and a fail-closed auth plug

**Status**: ASSUMED (`--auto`; identity, no forced logout, two deny-only wire deviations)
**Date**: 2026-10-09 · **Depends on**: ADR-000 A3 (keep sessions and hashes)

## Context

Legacy mints `jwt.sign({user:{id}}, JWT_SECRET || 'superSecret', {expiresIn:'60d'})` with jsonwebtoken 9.0.2
(M-08). It verifies with express-jwt 8.4.1: HS256 only, zero leeway, and `iat` is not checked (M-07). Tokens come
from `Authorization: Token|Bearer <jwt>`. The split is JS `split(' ')`, the scheme is case-sensitive, and only the
first header counts (C-13). A present token is always verified, on optional routes too, and every failure returns the
exact 401 `{"status":"error","message":"missing authorization credentials"}` (C-14). There is no revocation (C-15). Register, login and
`GET/PUT /user` mint a fresh token (C-16). ADR-000 requires Node and Phoenix to accept each other's tokens so that
rollback keeps sessions. Source: security-analyzer consult Q1, Q2 and Q4.

## Decision

- **`Realworld.Accounts.Token`** is an explicit Joken config. It does not use `default_claims`.
  - Signer: `Joken.Signer.create("HS256", secret)`, with the secret as raw UTF-8 bytes. HS256 is the only algorithm.
  - Claims: `iat = Joken.current_time()` and `exp = iat + 5_184_000`, validated as `exp > now`.
  - No `iss`, `aud`, `jti` or `nbf`. No `iat` validator. Zero leeway.
  - After verification, `claims["user"]["id"]` must be an integer. Otherwise the result is 401.
  - A token **without `exp` is rejected** (DV-07).
  - The secret is read in `runtime.exs`. The fallback policy belongs to ADR-011.
- **`RealworldWeb.Plugs.Auth`** takes `mode: :optional | :required`.
  - It reads the first `authorization` header and splits on `" "` the way JS does. Only `Token` and `Bearer` count.
  - A present token is always verified. Every failure halts with the prebuilt 401 body, in that key order.
  - On success it assigns `current_scope = %Scope{user_id: id}`. **It does not look the user up** (C-15 parity).
  - Register and login are mounted in a `:public` pipeline with no auth plug, as in Express.
- **Sliding renewal**: `Accounts.issue_token/1` runs in the four legacy actions.
- **No revocation** is added. The C-15 risk is stated in the consult and left to the user.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|-----------|----------------|-----------|
| Node-minted tokens verify in Phoenix, and the reverse | kept | every logged-in client, rollback |
| `alg:none`, other HS or RS algorithms, a tampered signature, or `exp <= now` → 401 | kept | security |
| A bad token on an optional route → 401, never silently anonymous | kept (fail-closed) | clients |
| Token string bytes | **changed**: Jason orders the claims `exp, iat, user`. The claims are equal (DV-06) | anyone comparing token strings (none known) |
| A token with no `exp` | **changed**: legacy 200 → port 401 (DV-07). Only forged or hand-made tokens are affected | none legitimate |
| A non-integer `user.id` claim | **changed**: legacy 500 → port 401 (DV-17). Needs the secret to produce | none legitimate |
| A deleted user's valid token | kept as the legacy 500 path (C-19a, ADR-008) | clients |

## Alternatives

- **Guardian.** Rejected: its cookie and claim conventions (`sub`, `typ`) do not match C-12, and it adds nothing.
- **JOSE directly.** Equally exact, but claim validation would be hand-written. Joken is thinner to review.
- **Load the user in the plug and 401 deleted users.** Safer (security consult Q4), but it changes a 500 path and
  costs one query per request. It is left as a candidate change under ADR-008.
- **A `pv` claim for password-change revocation.** Node ignores extra claims, so it is two-way compatible. Deferred:
  it is a security improvement that needs approval and a user load per request.

## Consequences

- The production `JWT_SECRET` must be confirmed and carried over before cutover (V-4). Without it, every user
  is logged out.
- A stolen token stays valid indefinitely while it is used, because of sliding renewal. That is a kept legacy risk.
- Golden tests compare decoded claims, never token strings.

## Validation

Two-way matrix, using jsonwebtoken 9.0.2 fixtures generated offline as data:

- A Node-minted token works on the port, and a port-minted token works on pinned Node: `GET /api/user` → 200.
- Each of these → 401 on both runtimes: tampered signature, `alg:none`, HS512 with the same secret, `exp = now`,
  `exp = now - 1`, and a `superSecret`-signed token when the real secret differs.
- A token with no `exp`: Node 200, port 401. This is recorded as DV-07.
- Header parsing cases: `token x`, `Token  x`, `Token`, `Bearer a b`, and duplicate headers.

## Ledger IDs

M-07, M-08, M-32, R-29, C-12, C-13, C-14, C-15, C-16, C-17
