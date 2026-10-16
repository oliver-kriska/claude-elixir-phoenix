# ADR-009: Forced socket disconnect moves after commit

**Status**: ASSUMED (auto; needs approval). Deliberate improvement recorded as DV-04.
**Date**: 2026-10-09

## Context

Action Cable authorizes only at handshake, so revocation is a forced reconnect (M-07, R-21). Callers: membership destroy (after commit, reconnect true), sign-out (best effort, after the session row is gone), deactivate and ban (**inside** their transaction, so a rollback has already disconnected the user, and a fast client could reconnect before the commit lands while its session row still exists).

## Decision

- Every revocation broadcasts `{:sockets_revoked, reconnect: boolean}` on `"user:<id>"` **after** the owning transaction returns `{:ok, _}`:
  - membership revoke and room revise: `reconnect: true`;
  - logout: `reconnect: true` for all of the user's connections (legacy parity); other devices re-authenticate with their own cookies;
  - deactivate and ban: `reconnect: false`.
- The shim (ADR-008) turns it into an Action Cable `disconnect` frame and stops the process. Reconnect re-authenticates and re-authorizes every subscription.
- A local `PubSub.broadcast` cannot fail like the Redis call, so C-43 "logout succeeds when realtime is unreachable" holds trivially.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| Revoked membership, session or user stops receiving | kept | members, admins |
| Disconnect for deactivate and ban happens after the DB state is final | **changed** (DV-04): never on a rolled-back transaction, and no reconnect race against an uncommitted delete | admins, banned users |
| Logout completes even if realtime fails | kept | users |

## Alternatives

- Keep the in-transaction disconnect (parity). Rejected: it is the race the legacy ordering creates. Post-commit is strictly safer.
- Per-event membership re-checks in the shim instead of disconnects. Not adopted now; it adds DB reads on every fan-out. A future tightening.

## Consequences

- Between commit and message processing there is a sub-millisecond local window, as in legacy.

## Validation

- Revise a closed room from {A, B} to {A, C} → B's socket closes, and B's resubscribe with the old signed name is rejected (F-06 probe, C-28 witness).
- Ban rolled back by an injected failure → no disconnect frame was sent.

## Ledger IDs

M-07, M-16, M-17, R-21, C-28, C-43
