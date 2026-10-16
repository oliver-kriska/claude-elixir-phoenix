# ADR-001: Thin Phoenix JSON API with no Oban, PubSub, LiveView or cache

**Status**: proposed
**Date**: 2026-10-09 · **Depends on**: ADR-000 (ASSUMED) A1, A4

## Context

The legacy app is a single stateless Express process. It serves the RealWorld JSON API from one PostgreSQL
database (runtime.md R-01, R-10). It has no UI, jobs, cron, cache, sockets, mail, external HTTP or
file uploads (runtime.md: R-20, R-22, R-23 and R-25 are absent). ADR-000 A4 classifies it as `http-api`, with no UI and
the wire protocols kept. `KB/app-shapes.md` places it in shape 2 (SPA + JSON API). The SPA lives outside the repo.

## Decision

- One Phoenix 1.8 release made of controllers, `action_fallback` and explicit `*JSON` view modules on Bandit.
- No HTML, LiveView, `Phoenix.PubSub`, Oban, Finch, DNSCluster, Cachex/ETS cache or clustering.
- The domain is plain modules over `Realworld.Repo` (ADR-002). The process table is empty beyond the framework
  defaults: Telemetry, the Repo pool and the Endpoint.
- Per-request concurrency comes from Bandit's process-per-connection model. Legacy's async error plumbing
  (`try/catch next(e)`, M-31) and the Prisma dev singleton (M-24, R-14) are DELETE, because the obligation is
  absent on the BEAM.
- If durable async work shows up later (mail, webhooks, cleanup), Oban with `Oban.Engines.Basic` is the
  default and needs no new ADR.

This is **not a framework deviation**. Leaving out Oban, PubSub and LiveView is the framework default for an app with
no async, realtime or UI obligation. No guarantee moves from the framework into project code.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|-----------|----------------|-----------|
| Every write is synchronous inside the request, as in legacy | kept | API clients |
| No durable async work exists, so none is lost | kept (nothing to keep) | — |
| Crash isolation: legacy has none (R-06). The target gets OTP supervision and Bandit graceful drain | improved, no wire effect | operators |

## Alternatives

- **Add Oban or PubSub "for later".** Rejected: there is no obligation to own, and it adds a DDL need (`oban_jobs`)
  that the frozen schema forbids during the observation window (ADR-003).
- **LiveView front-end.** Rejected: A4 has no UI, and the clients are third-party RealWorld SPAs.
- **Plain Plug + Bandit without Phoenix.** Viable for an API this small. Rejected because the team is
  intermediate (charter) and Phoenix's router, `action_fallback` and test helpers are the conventional path.

## Consequences

- The supervision tree has three children (architecture.md section 7).
- Adding a background obligation later (mail, for example) also needs a schema-ownership step, because Oban needs
  its tables. That step can only come after ADR-003's baseline.

## Validation

- Architecture review: grep the target for `Phoenix.PubSub`, `Oban`, `GenServer` and `Agent`. Nothing expected
  outside framework defaults (translationese probes in `KB/translationese-checks.md`).
- SIGTERM drain test in the S9 rehearsal.

## Ledger IDs

R-01, R-06, R-14, M-24, M-28, M-31
