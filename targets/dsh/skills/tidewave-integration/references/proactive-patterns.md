# Proactive Runtime Patterns

Push-like patterns using Tidewave within MCP's pull constraints.
Instead of waiting for the developer to ask, these patterns
**automatically query runtime state at workflow checkpoints**.

## Philosophy

From Jose Valim's vertical integration thesis: agents should
understand the relationship between code AND running behavior.
MCP is pull-only, but we simulate push by proactively querying
at the right moments.

**Shift from**: "Use Tidewave tools when you need to" (reactive)
**Shift to**: "Always check runtime state at checkpoints" (proactive)

## When to Proactively Query

### During Work Phase (per-task runtime check)

After editing `.ex` files, call `mcp__tidewave__get_logs level: :error`
to catch runtime errors that compile-time checks miss (supervision
tree failures, config issues, module loading problems).

If errors found, investigate immediately -- don't wait for
`mix test` to surface them.

### During Work Phase (per-feature smoke test)

After completing all tasks for a domain feature:

```elixir
# Ecto feature: create -> fetch -> verify (rolled back, no orphan records)
mcp__tidewave__project_eval """
alias MyApp.{Accounts, Repo}
Repo.transaction(fn ->
  {:ok, record} = Accounts.create_user(%{
    email: "smoke-#{System.unique_integer()}@test.com",
    password: "valid_password_123"
  })
  fetched = Accounts.get_user!(record.id)
  true = fetched.email == record.email
  Repo.rollback(:smoke_test_passed)
end)
# Returns {:error, :smoke_test_passed} = success
"""
```

```sql
-- Schema verification after migration
-- mcp__tidewave__execute_sql_query
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'target_table'
ORDER BY ordinal_position;
```

### During Planning Phase (context gathering)

Before spawning research agents:

```elixir
# Understand current data model
mcp__tidewave__get_ecto_schemas

# Understand current routes (auto-discovers router module)
mcp__tidewave__project_eval """
router = :code.all_loaded()
|> Enum.find(fn {mod, _} -> function_exported?(mod, :__routes__, 0) end)
|> elem(0)
Phoenix.Router.routes(router)
|> Enum.map(& {&1.verb, &1.path, &1.plug})
"""

# Check for existing warnings in planned area
mcp__tidewave__get_logs level: :warning
```

Pass gathered context to research agent prompts so they
work with concrete project state, not assumptions.

### During Investigation (auto-capture)

When investigating a bug, auto-capture BEFORE asking the user:

```elixir
# Step 1: Capture recent errors
mcp__tidewave__get_logs level: :error

# Step 2: Correlate with source
mcp__tidewave__get_source_location ModuleName

# Step 3: Inspect live state
mcp__tidewave__project_eval """
# Check process state, ETS tables, or query results
# relevant to the reported bug
"""
```

Present pre-populated investigation context rather than
asking the developer to copy-paste errors.

## Integration Points

| Workflow Phase | Checkpoint | Tidewave Query | Purpose |
|---------------|------------|----------------|---------|
| Plan | Before agents | `get_ecto_schemas`, routes eval | Concrete project context |
| Plan | Before agents | `get_logs :warning` | Existing issues in planned area |
| Work | Per-task | `get_logs :error` | Runtime error detection |
| Work | Per-feature | `project_eval` smoke test | Behavioral verification |
| Work | Per-feature | `execute_sql_query` | Schema/data verification |
| Investigate | Entry | `get_logs :error` | Auto-capture errors |
| Investigate | Hypothesis | `project_eval` | Test fix before applying |
| Review | Pre-review | `get_logs :error` | Catch runtime issues reviewers miss |

## Fallback Behavior

When Tidewave is NOT available, all proactive checks silently
skip. The workflow runs exactly as before -- static analysis,
`mix compile`, `mix test`. No functionality is lost.

When Tidewave IS available but the app is not running,
also silently skip. Tidewave tool calls will return errors
that the agent can safely ignore.
