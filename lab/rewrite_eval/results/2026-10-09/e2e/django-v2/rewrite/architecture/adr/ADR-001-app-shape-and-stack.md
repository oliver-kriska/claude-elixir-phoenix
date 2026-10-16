# ADR-001: App shape and stack — Phoenix JSON API on the kept SQLite file, no Oban, no PubSub

**Status**: proposed · **Date**: 2026-10-09 · **Depends on**: ADR-000 (ASSUMED)

## Context
Shape is SPA + JSON API (features.md "Shape"; runtime.md R-01 "http-api confirmed"). One process (`runserver`), one SQLite file (R-10), no
jobs, cron, sockets, caches or mail (runtime.md "Scheduled and Background Work: None"; R-13). Consumers are RealWorld frontends (C-10..C-31).
Charter: team Elixir experience unknown, so prefer conventional Phoenix/Ecto.

## Decision
- One Phoenix 1.8 release (`mix phx.new conduit --no-html --no-assets --no-live --no-mailer --no-dashboard --no-gettext --database sqlite3`),
  Bandit endpoint, controllers plus explicit `*JSON` modules, Ecto with ecto_sqlite3.
- Three contexts (ADR-002); one web edge that owns the legacy wire format (ADR-009).
- **No Oban and no Phoenix.PubSub.** No legacy mechanism needs durable background work or fan-out. R-20/R-21 are in-request signals and stay in-request
  as explicit transaction steps (ADR-010). This applies "framework by default, where it applies"; it is not a deviation.
- No LiveView, no HTML (ADR-000 "Clients and UI").
- Versions from KB (hex.pm, checked 2026-10-09; re-check before pinning): phoenix 1.8.15, bandit 1.12.5, ecto_sql 3.14.0, ecto_sqlite3 0.25.0, jason 1.4.5,
  joken 2.7.0, pbkdf2_elixir 2.3.1, corsica 2.1.3. Elixir/OTP: verify.

## Guarantees
- Kept: every kept contract in ADR-000 (wire and data). No guarantee is owned by a hand-rolled framework replacement.
- Changed: none by this ADR.

## Alternatives
- Bare `Plug.Router` on Bandit: smaller, but the route table, pipelines and fallback controller would be rebuilt by hand; rejected for team convention.
- Absinthe/GraphQL or LiveView: no consumer; rejected.
- Adding Oban "for later": an unused durable queue adds writer contention on SQLite (sqlite-on-beam "Writer contention"); rejected until a job exists.

## Consequences
- If a background need appears (mail, cleanup), add Oban with `Oban.Engines.Lite` on the writer Repo in the same file, inserted transactionally.
- The supervision tree has no domain processes (architecture.md section 7).

## Validation
- `mix phx.routes` lists exactly the C-17 route set plus decided UNDECIDED rows.
- Translationese probes (kb/translationese-checks.md): no GenServer around Repo, no `Process.put`, no mirrored `apps/*/models` tree.

## Ledger IDs
R-01, R-02, M-03, M-35, M-41
