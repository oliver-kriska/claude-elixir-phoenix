# Runtime Validation Checklist

Validate implementations before marking complete. Prefer Tidewave when available.

## Schema & Migration

### With Tidewave

```elixir
# Verify schema loaded
mcp__tidewave__get_ecto_schemas User

# Check migration applied
mcp__tidewave__execute_sql_query """
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'users'
ORDER BY ordinal_position
"""

# Verify indexes
mcp__tidewave__execute_sql_query """
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'users'
"""

# Test changeset
mcp__tidewave__project_eval """
%MyApp.User{}
|> MyApp.User.changeset(%{email: "test@example.com"})
|> Map.take([:valid?, :errors])
"""
```

### Without Tidewave

```bash
mix ecto.migrations
mix ecto.migrate
psql $DATABASE_URL -c "\\d users"
```

## Context Functions

### With Tidewave

```elixir
# Test create
mcp__tidewave__project_eval """
MyApp.Accounts.create_user(%{
  email: "test-#{System.unique_integer()}@example.com",
  password: "password123456"
})
"""

# Verify in DB
mcp__tidewave__execute_sql_query """
SELECT id, email, inserted_at FROM users ORDER BY inserted_at DESC LIMIT 5
"""
```

### Without Tidewave

```bash
mix test test/my_app/accounts_test.exs
```

## LiveView

### With Tidewave

```elixir
# Find source
mcp__tidewave__get_source_location MyAppWeb.UserLive.Index

# Check errors
mcp__tidewave__get_logs level: :error

# Verify assigns (with PID)
mcp__tidewave__project_eval """
pid = pid("0.1234.0")
:sys.get_state(pid).socket.assigns |> Map.keys()
"""
```

### Without Tidewave

```bash
mix phx.server
mix test test/my_app_web/live/user_live_test.exs
```

## Oban Jobs

### With Tidewave

```elixir
# Check enqueued
mcp__tidewave__execute_sql_query """
SELECT id, worker, args, state
FROM oban_jobs
ORDER BY inserted_at DESC LIMIT 10
"""

# Test worker directly
mcp__tidewave__project_eval """
job = %Oban.Job{args: %{"user_id" => 1}}
MyApp.Workers.WelcomeEmailWorker.perform(job)
"""

# Check failures
mcp__tidewave__execute_sql_query """
SELECT worker, args, errors
FROM oban_jobs
WHERE state IN ('retryable', 'discarded')
"""
```

## GenServer / Processes

### With Tidewave

```elixir
# Check registered
mcp__tidewave__project_eval """
Process.whereis(MyApp.CacheServer) |> is_pid()
"""

# Inspect state
mcp__tidewave__project_eval """
pid = Process.whereis(MyApp.CacheServer)
:sys.get_state(pid)
"""

# Check supervision tree
mcp__tidewave__project_eval """
Supervisor.which_children(MyApp.Supervisor)
|> Enum.map(fn {id, _, _, _} -> id end)
"""
```

## Quick Validation Template

```markdown
## Validation: [Feature Name]

### Schema/Data
- [ ] Migration applied
- [ ] Schema fields correct
- [ ] Indexes created
- [ ] Changeset validates

### Context Functions
- [ ] create_* works
- [ ] get_* works
- [ ] list_* works
- [ ] update_* works

### Web Layer
- [ ] Routes configured
- [ ] Controller/LiveView responds
- [ ] Templates render

### Tests
- [ ] Unit tests pass
- [ ] No regressions

### Logs
- [ ] No errors
- [ ] No warnings
```

## Troubleshooting

### Module Not Found

```elixir
mcp__tidewave__project_eval """
Code.ensure_loaded?(MyApp.SomeModule)
"""

# Recompile
mcp__tidewave__project_eval """
IEx.Helpers.recompile()
"""
```

### Table/Column Not Found

```sql
SELECT EXISTS (
  SELECT FROM information_schema.tables
  WHERE table_name = 'users'
);

SELECT EXISTS (
  SELECT FROM information_schema.columns
  WHERE table_name = 'users' AND column_name = 'email'
);
```
