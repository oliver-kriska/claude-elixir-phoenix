# ADR-019: TLS edge — keep a pinned Thruster binary in front of Bandit for the cutover release

**Status**: ASSUMED (auto; needs approval). Settles the C-56 mechanism left open by ADR-000.
**Date**: 2026-10-09

## Context

- Thruster provides Let's Encrypt TLS when `TLS_DOMAIN` is set, HTTP/2, compression, X-Sendfile and `HTTP_*_TIMEOUT` knobs; `DISABLE_SSL` turns off `assume_ssl`/`force_ssl` (M-56, R-02, C-56).
- Thruster's autocert cache is inferred to live at `/rails/storage/thruster` (not verified). An in-release ACME client cannot read it without an importer, and a boot loop could hit Let's Encrypt's 5-per-week duplicate limit (otp consult Q4, R4).
- Thruster is a standalone Go binary; it needs no Ruby.

## Decision

- Ship the same Thruster version as the pinned image (`verify` exact version and default `STORAGE_PATH` in the image) as a multi-arch binary. `CMD ["thrust", "/rails/bin/campfire", "start"]` under `tini`.
- Bandit binds `127.0.0.1:${PORT:-3000}`. `assume_ssl` is mirrored (scheme treated as https unless `DISABLE_SSL`); `Plug.SSL` with HSTS and redirect unless `DISABLE_SSL`. `X-Forwarded-For` trusted from loopback per ADR-016.
- `/cable` WebSockets pass through Thruster as today.
- A later ADR may move TLS into the release (Bandit on 80/443 + an ACME library) once a Thruster-cache importer and a staging-ACME rehearsal exist.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| C-56 TLS modes (`TLS_DOMAIN`, `DISABLE_SSL`, default force-SSL with HSTS) | kept, same binary | operators |
| Certificate reuse across upgrade (no re-issue) | kept | operators |
| Thruster env vars (`HTTP_*_TIMEOUT` and any ONCE-set ones) | kept, same binary | operators, ONCE |

## Alternatives

- Bandit TLS + `site_encrypt`. Deferred: certificate re-issue risk, small library user base, the team would own ACME edge cases.

## Consequences

- One non-BEAM binary remains in the image (owned as a pinned dependency with its upgrade policy).

## Validation

- Inspect the pinned image: Thruster version, `STORAGE_PATH` default, cert files present on a real volume.
- Staging ACME run with `TLS_DOMAIN`; `curl -I http://` → 301 in default mode, 200 with `DISABLE_SSL`.
- Upgrade test on a volume with existing certs: no new issuance logged.

## Ledger IDs

M-56, R-02, C-56
