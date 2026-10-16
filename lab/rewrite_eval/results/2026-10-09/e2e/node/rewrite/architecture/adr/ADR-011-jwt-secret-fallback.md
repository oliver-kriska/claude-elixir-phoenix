# ADR-011: `superSecret` JWT fallback (UNDECIDED)

**Status**: ASSUMED (`--auto` default = keep the fallback; fail-to-boot recommended; blocks S1 config and S9 go/no-go)
**Date**: 2026-10-09 · **Depends on**: ADR-000 A3, consequential assumptions 2 and 5; ADR-004

## Context

Legacy signs and verifies with `JWT_SECRET || 'superSecret'` (`auth.ts:16,21`, `token.utils.ts:4`; M-08, C-37a). The
literal is public in the repo. If production runs without `JWT_SECRET`, anyone can forge `{user:{id:N}}` and take over
any account. The security consult rates this **Critical** if the variable is unset and Low if it is set. ADR-004 needs
the production secret carried over (V-4), or every user is logged out.

## Decision

The `--auto` default (keep) and the recommended change are both specified, so S1 can implement either one once the
user approves.

- **Keep (default):** `runtime.exs` reads `System.get_env("JWT_SECRET") || "superSecret"`, in every environment.
- **Recommended (fail-to-boot):**
  - In `:prod`, use `System.fetch_env!("JWT_SECRET")`.
  - Also refuse to boot when the value is `"superSecret"` or shorter than 32 bytes.
  - The fallback stays in dev and test only.
  - If prod sets a strong secret, nothing changes for clients.
- **If V-4 shows prod actually uses `superSecret`:** rotate.
  - Set a new `JWT_SECRET`.
  - The port mints with the new key and verifies against `[new, "superSecret"]` for 60 days.
  - The cost is that a Node rollback logs out holders of tokens signed with the new key. This needs explicit approval.

The secret is never placed in compile-time `config/*.exs` and never logged.

## Guarantees

| Guarantee | Keep | Fail-to-boot |
|-----------|------|--------------|
| Same env name `JWT_SECRET` | kept | kept |
| Boots without `JWT_SECRET` | kept (forgeable tokens) | **changed**: the prod release refuses to start |
| Existing tokens stay valid | kept | kept (if prod sets the variable) |

## Alternatives

- **Keep indefinitely.** Not defensible (security consult). It is still the `--auto` default because A5 keeps all
  contracts.
- **Generate a random secret at boot.** Rejected: it logs everyone out on every restart and breaks the two-way token
  contract.

## Consequences

- Fail-to-boot turns a silent misconfiguration into a deploy failure. Operators must set the variable before S9.

## Validation

- V-4: offline, check that a production token does **not** verify under `superSecret`. The token is never logged.
- A boot test of the prod release config with the variable unset, set to `superSecret`, set short, and set valid.

## Ledger IDs

M-08, M-27, C-37, C-37a
