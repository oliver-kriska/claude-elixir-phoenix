---
name: oban
description: Oban jobs — workers, perform/1, process/1, queues, cron, retries, unique
  jobs, idempotency, Oban Pro, testing. Use when writing workers, queue config, or
  debugging jobs.
metadata:
  effort: medium
  user-invocable: false
  paths:
  - '**/workers/**/*.ex'
  - '**/*_worker.ex'
  - '**/*_worker_test.exs'
  - '**/*_job.ex'
---

# Oban Background Jobs Reference

Quick reference for Elixir Oban patterns.

## Oban Pro Detection

**Before applying patterns, check for Oban Pro:**

```bash
grep -E "oban_pro|oban_web" mix.exs
grep -r "use Oban.Pro.Worker" lib/
grep -r "Oban.Pro.Engines.Smart" config/
```

**If Oban Pro detected**, use Pro patterns for ALL new workers:

| Standard Oban | Oban Pro |
|---------------|----------|
| `use Oban.Worker` | `use Oban.Pro.Worker` |
| `def perform(%Job{})` | `def process(%Job{})` |
| `Oban.Testing` | `Oban.Pro.Testing` |
| Advisory lock engine | `Oban.Pro.Engines.Smart` |

**Pro features** (all optional): `args_schema` (typed args), Workflows, Batches, Chunks,
Relay, hooks, encryption, deadlines, chaining, Smart Engine (global concurrency + rate limiting).
Pro plugins (DynamicCron, DynamicLifeline, DynamicPruner) **enhance** OSS equivalents — swap module, don't run both.
See `references/oban-pro-basics.md` for all patterns and migration guide.

---

## Iron Laws — Never Violate These

1. **JOBS MUST BE IDEMPOTENT** — Safe to retry. Use idempotency keys for payments
2. **JOBS MUST STORE IDs, NOT STRUCTS** — JSON serialization. `%{user_id: 1}` not `%{user: %User{}}`
3. **JOBS MUST HANDLE ALL RETURN VALUES** — `:ok`, `{:error, _}`, `{:cancel, _}`, `{:snooze, _}`
4. **ARGS USE STRING KEYS** — Pattern match `%{"user_id" => id}` not `%{user_id: id}`
5. **UNIQUE CONSTRAINTS FOR USER ACTIONS** — Prevent double-click duplicates
6. **NEVER STORE LARGE DATA IN ARGS** — Store references (IDs, paths), not content
7. **SMART ENGINE: NEVER USE `attempt` TO LIMIT SNOOZES** — Snooze rolls back attempt counter. Use `meta["snoozed"]` instead. Causes infinite loops

## Quick Worker Template

```elixir
defmodule MyApp.Workers.ExampleWorker do
  use Oban.Worker,
    queue: :default,
    max_attempts: 5,
    unique: [period: {5, :minutes}, keys: [:entity_id]]

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"entity_id" => id}}) do
    case process(id) do
      {:ok, _} -> :ok
      {:error, :not_found} -> {:cancel, "Entity not found"}
      {:error, :rate_limited} -> {:snooze, {5, :minutes}}
      {:error, reason} -> {:error, reason}
    end
  end
end
```

## Return Value Meanings

| Return | State | Behavior |
|--------|-------|----------|
| `:ok` | `completed` | Success |
| `{:ok, value}` | `completed` | Success with value |
| `{:error, reason}` | `retryable` | Retry with backoff |
| `{:cancel, reason}` | `cancelled` | Stop permanently |
| `{:snooze, seconds}` | `scheduled` | Delay and retry |

## Quick Decisions

### Which Queue?

- **Critical operations** → High concurrency (20+)
- **Mailers/Webhooks (I/O)** → Medium concurrency (30-50)
- **CPU-intensive** → Low concurrency (3-5)
- **External APIs** → Use `dispatch_cooldown` for rate limiting

### Testing Pattern

```elixir
use Oban.Testing, repo: MyApp.Repo

# Assert enqueued
assert_enqueued worker: MyApp.Worker, args: %{id: 1}

# Execute and verify
assert :ok = perform_job(MyApp.Worker, %{id: 1})
```

## Common Anti-patterns

| Wrong | Right |
|-------|-------|
| `%{user_id: id}` pattern match | `%{"user_id" => id}` (string keys) |
| `%{user: %User{}}` in args | `%{user_id: 1}` (IDs only) |
| No idempotency for payments | Use idempotency keys |
| Ignoring return values | Handle all outcomes explicitly |

## References

For detailed patterns, see:

- `references/worker-patterns.md` - Worker options, backoff, timeout
- `references/queue-config.md` - Queue design, pool sizing, cron, Smart Engine
- `references/testing-patterns.md` - Testing, assertions, drain (OSS + Pro)
- `references/oban-pro-basics.md` - Pro.Worker, Workflow, Batch, Chunk, Relay, plugins

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
