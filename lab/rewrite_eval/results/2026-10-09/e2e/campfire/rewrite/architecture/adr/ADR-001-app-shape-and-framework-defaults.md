# ADR-001: App shape and framework defaults

**Status**: proposed (auto; needs approval)
**Date**: 2026-10-09 · **Bar**: ADR-000 (ASSUMED) · **Source**: reference @ `90b330024dec`

## Context

- `kb/app-shapes.md` is missing (plugin defect, `status.md`). The shape is classified from `inventory.md` ("web-ui, web-app, realtime, worker/consumer, cli") and `features.md` header ("mixed").
- Classification: a **single-node web appliance**. It is a single-tenant server-rendered web app with realtime fan-out, in-process background work and an operator CLI, shipped as one container over one SQLite file (C-50, C-52). It is not an API product, a pipeline, or a device.
- ADR-000 keeps the Hotwire/Stimulus UI, the Action Cable wire (C-41), SQLite (charter) and every operator contract. LiveView is not allowed as a UI replacement under the bar.

## Decision

Framework defaults apply, with the bar's UI constraint:

| Concern | Choice | Note |
|---|---|---|
| HTTP | Phoenix 1.8 controllers + HEEx on Bandit | Reproduces the HTML, Turbo Stream responses (`text/vnd.turbo-stream.html`) and JSON the bundled JS expects |
| Data | Ecto over the legacy SQLite schema (ecto_sqlite3), writer + reader Repos | ADR-003 |
| Jobs | Oban, `Oban.Engines.Lite`, same SQLite file | ADR-006 |
| Fan-out | `Phoenix.PubSub` (local `:pg`) | Ephemeral. Never durable, never exactly-once |
| Browser realtime | Action Cable protocol SHIM on raw WebSock | ADR-008. No Phoenix Channels or LiveView on `/cable` |
| Bot API | Phoenix JSON controllers, byte-compatible | C-30..C-34 |
| HTTP client | `Req` over named `Finch` pools, behind project-owned modules | ADR-015 |
| Release | `mix release`, one BEAM process | ADR-018, ADR-019 |

Not adopted: LiveView (forbidden by the bar), Phoenix Channels (no client speaks them), Cachex (no measured need, ADR-017), Redis (retired, C-59).

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| UI HTML, DOM ids, data attributes, JSON endpoints (C-40, C-44, C-48, C-49, M-61) | kept | bundled JS, browsers |
| One container, all state under `/rails/storage` (C-50, C-52) | kept | ONCE, operators |

## Alternatives

- **LiveView UI now.** Rejected by the bar. A later ADR may retire C-41, C-48 and C-49 (open tabs only).
- **`<turbo-stream-source>` over a Phoenix endpoint** instead of the Cable shim. It changes the bundled JS, which the bar keeps unchanged. It is the shim's deletion path (ADR-008).

## Consequences

- The UI stays a Rails-shaped HTML contract, and the web layer carries Turbo-specific rendering. Core contexts stay framework-idiomatic and never see Turbo or Cable.
- Assets: the legacy JS, CSS and vendored libraries are served as static files with the same import map. Asset build is a slice decision. The source licence must be checked before copying (`verify`).

## Validation

- A route-parity table generated from `config/routes.rb` (every route: method, path, status, redirect target).
- Golden HTML fragments for DOM ids and data attributes read by Stimulus (M-61).
- No `phoenix_live_view` and no `Phoenix.Socket` in `mix.lock` (translationese check).

## Ledger IDs

M-26, M-31, M-61, R-04, C-40, C-41, C-48, C-49
