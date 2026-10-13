# ADR-006: Token authentication — Joken HS256 with a new env secret, legacy header scheme kept

**Status**: ASSUMED (inherits ADR-000's ASSUMED security dispositions for C-14, C-15; pending user approval) · **Date**: 2026-10-09

## Context
Legacy: `Authorization: Token <jwt>` (C-10), HS256 `{id, exp}` 60-day tokens (C-11), stateless with a fresh token on four responses (C-12), signed with
the committed `SECRET_KEY` (C-14, security defect), decoded without an algorithm pin (C-15). Auth failures are 403 and bad tokens fail public endpoints (C-16, UNDECIDED).
Security consult Q2, Q3.

## Decision
- `Conduit.Accounts.Token` over Joken 2.7.0 with `Joken.Signer.create("HS256", secret)`; **no** `use Joken.Config` default claims. Claims exactly
  `%{"id" => id, "exp" => now_s + 5_184_000}`.
- Verify: `Joken.verify/2` (algorithm pinned, VO-02) with `JWT_SECRET`, then `JWT_SECRET_PREVIOUS` if set → claim match (positive integer `id`;
  `exp` integer and `> now`, leeway 0) → `Repo.get(User, id)` → `is_active`. Messages kept verbatim (C-12, C-15 single decode message).
- Missing `exp`: legacy accepted it. Rejecting is **proposed** (DV-P5), not adopted; until approved the claim match does not require `exp`.
- `ConduitWeb.Plugs.TokenAuth` parses the header per C-10 and assigns `:anonymous | {:ok, scope} | {:error, message}`. Pipelines decide what
  `{:error, _}` means on public routes and which status a refusal gets. **C-16 stays UNDECIDED**; both options are a pipeline policy:
  (a) legacy: 403 and label-wrapped `detail`, bad token refused on public routes; (b) spec: 401 and bad token treated as anonymous on public routes.
- The legacy key is never configured; an optional boot guard compares `sha256(JWT_SECRET)` against the leaked key's fingerprint.

## Guarantees
- Kept: C-10, C-11 shape and lifetime, C-12 statelessness and per-request `is_active` check.
- Changed: C-14 key rotated → legacy-signed tokens rejected, every client logs in once (DV-01; ADR-000 Changed table). C-15 HS256 only (DV-02).
  Consumers: every logged-in client (re-login once); no client is known to use HS384/HS512.

## Alternatives
- Reuse the leaked key for one token lifetime: keeps sessions but keeps forgery open; ADR-000 rejects it (an AR record by the user would be required).
- Hand-rolled HS256 (~40 lines): acceptable but more places to get padding and compare wrong; not preferred.
- phx.gen.auth DB tokens: changes C-12 revocation semantics (OD-8).

## Consequences
Rotation runbook: set `JWT_SECRET_PREVIOUS` to the old secret for 60 days, then remove it.

## Validation
VO-02; C-11 witness (exp past → rejected; flipped signature → rejected; `alg:none` → rejected; payload without `id` → rejected, not 500);
legacy-key token → rejected; `token <t>` lowercase → 200; `Bearer <t>` and `Token a b` → anonymous.

## Ledger IDs
M-04, C-10, R-34, M-05, C-11, M-06, C-14, R-32, C-15, C-12, M-39, M-10, C-16
