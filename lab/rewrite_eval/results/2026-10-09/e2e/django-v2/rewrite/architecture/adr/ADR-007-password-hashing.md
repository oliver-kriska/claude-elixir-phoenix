# ADR-007: Password hashing — verify Django PBKDF2, write Django format; iteration count is an open decision

**Status**: proposed (format and verification); **iteration raise UNDECIDED (OD-2)** · **Date**: 2026-10-09

## Context
C-02: every stored hash is `pbkdf2_sha256$30000$<salt>$<b64>` (Django 1.10 default, no `PASSWORD_HASHERS` override); there is no reset flow, so a
verify failure locks a user out permanently. Django's `check_password` rehashes when iterations change (M-16). ADR-000 performance goal: no regression vs the
legacy baseline, login included. The security consult recommends raising iterations to ~600,000 (OWASP 2023), which it estimates would make login p95 ~20x slower.

## Decision
- `Conduit.Accounts.Password` gate: strict `\Apbkdf2_sha256\$(\d{1,7})\$([^$]+)\$([A-Za-z0-9+/]+=*)\z`; iteration ceiling 2,000,000;
  anything else (unusable `!…`, empty, other algorithms) → `false` after a dummy verify, never a raise. Then `Pbkdf2.verify_pass/2` (pbkdf2_elixir 2.3.1).
- New and changed passwords are hashed in **Django format** (`format: :django`, sha256), so a rollback hand-back to Django still verifies every password.
- Rounds come from app config `:conduit, :pbkdf2_rounds`. **Configured value: 30,000 (legacy) until OD-2 is decided.**
- Rehash-on-login is built: after a successful verify, if the stored count is below the configured one, update only the `password` column; a failed
  update is logged, not fatal. At 30,000 it never fires.
- Login: one path for unknown email, inactive user and wrong password (`Pbkdf2.no_user_verify/1` with the configured rounds), one message (C-13).
- `redact: true` on the field; `password` filtered from logs.

## OD-2 (open, needs the user)
| Option | Security | Perf vs ADR-000 goal | Needs |
|--------|----------|----------------------|-------|
| A. keep 30,000 | legacy strength (below current guidance) | no change | nothing |
| B. ~600,000 with rehash on login | OWASP 2023 | login p95 regression (estimate, unmeasured) | an explicit login carve-out in this ADR + likely DV-P4 rate limiting |
| C. intermediate value measured in slice 0 | between | bounded by measurement | carve-out sized by the measurement |
Not adopted silently: the design ships with A until the user picks.

## Guarantees
- Kept: C-02 (legacy hashes verify; format unchanged), C-13 messages.
- Changed: none under option A. Options B/C change hash cost and login latency (a perf-goal carve-out) — recorded as DV-P7 (proposed).

## Alternatives
Argon2id with a prefix dispatcher: stronger, but one-way (Django 1.10 cannot verify it), breaking the rollback hand-back; rejected while the rollback window is open.

## Consequences
Timing of `no_user_verify` matches the configured rounds; legacy rows at 30k match under option A.

## Validation
VO-01 fixture (`correct horse` → true, `wrong` → false, `!xyz` → false without raise); Django 1.10 verifies a port-written hash (offline);
login perf gate per architecture.md section 11.

## Ledger IDs
M-16, C-02, R-33, M-17, C-13
