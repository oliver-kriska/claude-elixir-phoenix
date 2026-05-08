---
name: testing
description: Elixir testing patterns — ExUnit, Mox, factories, LiveView test helpers.
  Use when working on *_test.exs, test/support/, factory files, or fixing test failures.
metadata:
  effort: medium
  user-invocable: false
  paths:
  - test/**/*_test.exs
  - test/support/**/*.ex
  - '**/*factory*.ex'
---

# Elixir Testing Reference

Quick reference for Elixir testing patterns.

## Iron Laws — Never Violate These

1. **ASYNC BY DEFAULT** — Use `async: true` unless tests modify global state
2. **SANDBOX ISOLATION** — All database tests use Ecto.Adapters.SQL.Sandbox
3. **MOCK ONLY AT BOUNDARIES** — Never mock database, internal modules, or stdlib
4. **BEHAVIOURS AS CONTRACTS** — All mocks must implement a defined `@callback` behaviour
5. **BUILD BY DEFAULT** — Use `build/2` in factories; `insert/2` only when DB needed
6. **NO PROCESS.SLEEP** — Use `assert_receive` with timeout for async operations
7. **VERIFY_ON_EXIT!** — Always call in Mox tests setup
8. **FACTORIES MATCH SCHEMA REQUIRED FIELDS** — Factory definitions must include all fields that have `validate_required` in the schema changeset. Missing fields cause cascading test failures

## Quick Decisions

### Which Test Case?

| Testing | Use |
|---------|-----|
| Controller/API | `use MyAppWeb.ConnCase` |
| Context/Schema | `use MyApp.DataCase` |
| LiveView | `use MyAppWeb.ConnCase` + `import Phoenix.LiveViewTest` |
| Pure logic | `use ExUnit.Case, async: true` |

### When to use async: true?

- ✅ Pure functions, no shared state
- ✅ Database tests with Sandbox (PostgreSQL)
- ❌ Tests modifying `Application.put_env`
- ❌ Tests using Mox global mode

### Mock or not?

- ✅ Mock: External APIs, email services, file storage
- ❌ Don't mock: Database, internal modules, stdlib

### build() or insert()?

- Use `build()` by default for speed
- Use `insert()` only when you need DB ID, constraints, or persisted associations

## Quick Patterns

```elixir
# Setup chain
setup [:create_user, :authenticate]

# Pattern matching assertion
assert {:ok, %User{name: name}} = create_user(attrs)

# Async message assertion
assert_receive {:user_created, _}, 5000

# Mox setup
setup :verify_on_exit!
expect(MockAPI, :call, fn _ -> {:ok, "data"} end)

# LiveView async
html = render_async(view)  # MUST call for assign_async
```

## Common Anti-patterns

| Wrong | Right |
|-------|-------|
| `Process.sleep(100)` | `assert_receive {:done, _}, 5000` |
| `insert(:user)` in factory | `build(:user)` in factory |
| `async: true` with `set_mox_global()` | `async: false` |
| Mock internal modules | Test through public API |

## References

For detailed patterns, see:

- `references/exunit-patterns.md` - Setup, assertions, tags
- `references/mox-patterns.md` - Behaviours, expect/stub, async
- `references/liveview-testing.md` - Forms, async, uploads
- `references/factory-patterns.md` - ExMachina, sequences, traits

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
