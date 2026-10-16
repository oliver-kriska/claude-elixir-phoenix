# Rewrite Charter — ONCE Campfire → Elixir/Phoenix

- Source: `~/Projects/campfire-bench/once-campfire-elixir/reference` (Rails, git `90b330024dec`)
- Target: this workspace (empty, no commits yet)
- Written: 2026-10-09 by `/rewrite:analyze --auto`

## Goals

- ASSUMED: maintainability and consolidation of runtime (drop Redis/Resque/ActionCable in favour of BEAM-native equivalents)
- ASSUMED: feature parity with the reference app as the primary success criterion

## Constraints

- ASSUMED: no hard deadline
- ASSUMED: team is experienced in Elixir/Phoenix/LiveView
- ASSUMED: must-keep integrations — bot webhooks (outbound + inbound bot API), Web Push (VAPID), SQLite as the datastore

## Scope

- Whole app (694 files, under the 1,500-file threshold). No domain triage needed.

## Steering files

- None found in SOURCE or TARGET.

## Assumptions (pending approval)

1. ASSUMED: rewrite goals = maintainability + runtime consolidation
2. ASSUMED: no deadline; experienced Elixir team
3. ASSUMED: must-keep integrations = bot webhooks/API, Web Push, SQLite
4. ASSUMED: whole-app scope
