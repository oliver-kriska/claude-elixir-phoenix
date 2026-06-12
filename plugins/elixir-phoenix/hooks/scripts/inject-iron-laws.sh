#!/usr/bin/env bash
# SubagentStart hook: Inject Iron Laws into all spawned subagents via additionalContext.
# Addresses the #1 session analysis finding: zero skill auto-loading in subagents.

# Skip in non-Elixir projects (cross-project bleed guard — issue #55).
# Subagents in Rust/Python/etc. projects shouldn't get Phoenix Iron Laws.
proj="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -f "$proj/mix.exs" ] || exit 0

jq -n '{hookSpecificOutput: {hookEventName: "SubagentStart", additionalContext:
"Elixir/Phoenix Iron Laws (NON-NEGOTIABLE):
- NO unconditional DB queries in mount — use assign_async (or connected? + cache-backed branch for SEO routes)
- ALWAYS use streams for lists >100 items
- CHECK connected?/1 before PubSub subscribe
- NEVER use :float for money — use :decimal or :integer (cents)
- ALWAYS pin values with ^ in queries — never interpolate user input
- SEPARATE QUERIES for has_many, JOIN for belongs_to
- Jobs MUST be idempotent, args use STRING keys, never store structs in args
- NO String.to_atom with user input — atom exhaustion DoS
- AUTHORIZE in EVERY LiveView handle_event
- NEVER use raw/1 with untrusted content — XSS
- NO process without runtime reason — processes model concurrency/state/isolation
- SUPERVISE ALL LONG-LIVED PROCESSES
- NO IMPLICIT CROSS JOINS — from(a in A, b in B) without on: creates Cartesian product
- @external_resource FOR COMPILE-TIME FILES
- DEDUP BEFORE cast_assoc WITH SHARED DATA
- HIDDEN INPUTS FOR ALL REQUIRED EMBEDDED FIELDS
- WRAP THIRD-PARTY LIBRARY APIs behind project-owned modules
- NEVER use assign_new for values refreshed every mount
- VERIFY BEFORE CLAIMING DONE — run mix compile && mix test, never say should work"}}'
