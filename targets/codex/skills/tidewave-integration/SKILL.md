---
name: tidewave-integration
description: Tidewave MCP runtime tools — debugging, smoke testing, live state inspection,
  SQL queries, hex docs. Use when evaluating code in a running Phoenix app.
metadata:
  effort: low
  user-invocable: false
---

# Tidewave MCP Integration

Runtime intelligence for Phoenix apps via MCP. Prefer Tidewave tools over Bash when available.

## Iron Laws — Never Violate These

1. **DEV ONLY** — Never use Tidewave tools in production contexts. Avoid on shared dev servers with production data copies
2. **PREFER TIDEWAVE OVER BASH** — `mcp__tidewave__get_docs` > `web_fetch`, `execute_sql_query` > `psql`
3. **CHECK AVAILABILITY FIRST** — Use `/mcp` command or detect `mcp__tidewave__` tools
4. **SQL IS READ-HEAVY** — Use `execute_sql_query` for SELECT, be careful with mutations
5. **EXACT VERSIONS** — `get_docs` returns docs for YOUR mix.lock versions, not latest

## Quick Reference

| Task | Tidewave Tool | Fallback |
|------|---------------|----------|
| Get docs | `mcp__tidewave__get_docs Module.func/3` | `web_fetch hexdocs.pm/...` |
| Run code | `mcp__tidewave__project_eval` | `mix run -e "code"` |
| SQL query | `mcp__tidewave__execute_sql_query` | `psql $DATABASE_URL` |
| Find source | `mcp__tidewave__get_source_location` | `grep -rn "defmodule"` |
| Inspect DOM | `mcp__Tidewave-Web__browser_eval` | Manual browser inspection |
| List schemas | `mcp__tidewave__get_ecto_schemas` | Read `lib/*/schemas/` |
| Read logs | `mcp__tidewave__get_logs level: :error` | `tail -f log/dev.log` |

## Detection

```bash
# Check endpoint
curl -s http://localhost:4000/tidewave/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'
```

Or use `/mcp` in Claude Code to see connected servers.

## Essential Patterns

### Test Function Immediately

```elixir
# mcp__tidewave__project_eval
MyApp.Accounts.create_user(%{email: "test@example.com"})
```

### Verify Migration

```sql
-- mcp__tidewave__execute_sql_query
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'users';
```

### Debug LiveView (with PID from browser)

```elixir
# mcp__tidewave__project_eval
pid = pid("0.1234.0")
:sys.get_state(pid) |> Map.get(:socket) |> Map.get(:assigns) |> Map.keys()
```

## Setup Requirements

```elixir
# mix.exs
{:tidewave, "~> 0.1", only: :dev}

# endpoint.ex (in dev block)
plug Tidewave

# config/dev.exs (for LiveView source mapping)
config :phoenix_live_view,
  debug_heex_annotations: true,
  debug_attributes: true
```

## Proactive Runtime Checks

Don't just use Tidewave reactively. **Query runtime state at
workflow checkpoints** automatically:

- **After code edits**: `get_logs level: :error` (catch runtime crashes)
- **After features complete**: `project_eval` smoke test (behavioral check)
- **Before planning**: `get_ecto_schemas` + routes eval (concrete context)
- **When investigating**: Auto-capture errors before asking user
- **LiveView UI bugs**: `browser_eval` to inspect DOM state before editing components

See `references/proactive-patterns.md` for full integration points.

## References

For detailed patterns, see:

- `references/proactive-patterns.md` - Push-like runtime patterns at workflow checkpoints
- `references/tool-examples.md` - Complete tool usage examples
- `references/validation-checklist.md` - Runtime validation patterns

## Iron Laws (Inlined)

- **NO unconditional DB queries in mount** — Mount runs twice. Default: `assign_async`. SEO routes: `connected?` + cache-backed disconnected branch (dead-render IS the crawler-indexed HTML)
- **ALWAYS use streams for lists >100 items** — Regular assigns = O(n) memory per user
- **CHECK `connected?/1` before PubSub subscribe** — Prevents double subscriptions
- **NEVER use `:float` for money** — Use `:decimal` or `:integer` (cents)
- **ALWAYS pin values with `^` in queries** — Never interpolate user input
- **SEPARATE QUERIES for `has_many`, JOIN for `belongs_to`** — Avoids row multiplication
- **Jobs MUST be idempotent** — Safe to retry
- **Args use STRING keys, not atoms** — Pattern match `%{"user_id" => id}`
- **NEVER store structs in args** — Store IDs, not `%User{}`
- **NO `String.to_atom` with user input** — Atom exhaustion DoS
- **AUTHORIZE in EVERY LiveView `handle_event`** — Don't trust mount authorization
- **NEVER use `raw/1` with untrusted content** — XSS vulnerability
- **NO process without runtime reason** — Processes model concurrency/state/isolation, NOT code structure
- **SUPERVISE ALL LONG-LIVED PROCESSES** — Never bare `GenServer.start_link`/`Agent.start_link` in production. Use supervision trees
- **NO IMPLICIT CROSS JOINS** — `from(a in A, b in B)` without `on:` creates Cartesian product
- **@external_resource FOR COMPILE-TIME FILES** — Modules reading files at compile time MUST declare `@external_resource`
- **DEDUP BEFORE `cast_assoc` WITH SHARED DATA** — Deduplicate shared child records before building changesets, not inside them
- **CHECK CHANGESET ERRORS BEFORE UI DEBUGGING** — When a form save produces no visible error but no expected side effect, check `{:error, changeset}` first
- **HIDDEN INPUTS FOR ALL REQUIRED EMBEDDED FIELDS** — Every required field in an embedded schema MUST have a `hidden_input` if not directly editable
- **WRAP THIRD-PARTY LIBRARY APIs** — Always facade external dependency APIs behind a project-owned module. Enables swapping libraries without touching callers
- **NEVER use `assign_new` for values refreshed every mount** — `assign_new` skips the function if the key exists. Use `assign/3` for locale, current user, or any value that must be set on every mount
- **VERIFY BEFORE CLAIMING DONE** — Never say "should work" or "this fixes it." Run `mix compile && mix test` and show the result. If you can't verify, explicitly state what remains unverified
