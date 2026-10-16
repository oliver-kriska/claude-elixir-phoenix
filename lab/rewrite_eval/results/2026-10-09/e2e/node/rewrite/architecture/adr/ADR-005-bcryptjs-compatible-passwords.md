# ADR-005: bcryptjs-compatible password hashing with JS trim semantics

**Status**: ASSUMED (`--auto`; identity and security, rollback-dependent)
**Date**: 2026-10-09 · **Depends on**: ADR-000 A3, ADR-004

## Context

Legacy uses bcryptjs 2.4.3 at cost 10 and produces `$2a$10$` hashes (C-02). Register and login trim email, username and
password with JS `String.prototype.trim`. `PUT /user` hashes the password **untrimmed**, after a truthy check
(C-30, M-09). An unknown email at login returns 403 without doing any bcrypt work, so response time reveals which
emails are registered. JS trim and Elixir `String.trim/1` remove different characters: JS removes U+FEFF and
Elixir does not; Elixir removes U+0085 and JS does not. Source: security-analyzer consult Q3 and Q5.

## Decision

- Verify with `Bcrypt.verify_pass/2` from `bcrypt_elixir`, which reads the cost and prefix from the stored hash.
- Hash new passwords with `Bcrypt.hash_pwd_salt(pw, log_rounds: 10, legacy: true)`. The result is `$2a$10$`, the same
  family and cost as legacy.
- `Realworld.Compat.JsString.trim/1` uses the exact JS whitespace class. It is applied on register and login only.
  Update hashes the password untrimmed, as legacy does (C-30, UNDECIDED, default keep).
- On an unknown email, `Bcrypt.no_user_verify/1` runs so both login paths cost one bcrypt-10. Status and body are
  unchanged (DV-05).
- **No rehash on login and no algorithm upgrade** while Node rollback is possible.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|-----------|----------------|-----------|
| Every existing hash verifies | kept | every user |
| Every Phoenix-made hash verifies in bcryptjs | kept | Node rollback |
| Trim on register and login, no trim on update | kept (bug-for-bug, C-30 UNDECIDED) | users |
| 72-byte truncation and UTF-8 bytes | kept (golden-tested) | users with long or non-ASCII passwords |
| Login timing for an unknown email | **changed**: now as slow as a wrong password (DV-05). No status or body change | attackers lose the timing oracle |
| Login latency profile | changes (dirty NIF instead of pure JS). Measured in the A6 baseline, not claimed | performance gate |

## Alternatives

- **The default `$2b$` and cost 12.** Rejected: bcryptjs probably accepts `$2b$` (verify), but cost 12 changes
  latency and `legacy: true` removes any doubt.
- **`pbkdf2_elixir` or Argon2 with rehash on login.** Rejected during the window: it breaks Node rollback.
- **Trim on update as well** (fix C-30). Recommended by the security consult. It cannot break any working hash, but it
  is a wire change under A5 and needs approval. Listed as a candidate divergence.
- **Elixir `String.trim/1`.** Rejected: a password padded with NEL or BOM would verify differently on each runtime.

## Consequences

- The C-30 asymmetry stays: a password set via PUT with surrounding spaces can never log in.
- The fixed bcrypt cost makes login a CPU-DoS lever. A rate limit (Hammer or proxy) is a candidate change (429 is new
  on the wire).

## Validation

- Fixtures generated offline with bcryptjs 2.4.3: a legacy hash verifies in the port, a port hash verifies in bcryptjs,
  and cases for >72 bytes, non-ASCII, and NEL- and BOM-padded passwords.
- A property test checks `JsString.trim/1` against a table of JS outputs.
- Login timing check: unknown email and wrong password are within the same order of magnitude. Measured, not claimed.

## Ledger IDs

M-09, M-10, C-02, C-18a, C-30
