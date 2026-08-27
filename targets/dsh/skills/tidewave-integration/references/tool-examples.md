# Tidewave Tool Examples

## project_eval - Execute Elixir Code

Best for: Testing functions, inspecting state, quick experiments

```elixir
# Test a context function
MyApp.Accounts.get_user!(1)

# Inspect process state
pid = Process.whereis(MyApp.SomeGenServer)
:sys.get_state(pid)

# Check application config
Application.get_env(:my_app, MyAppWeb.Endpoint)

# Test changeset
%MyApp.User{}
|> MyApp.User.changeset(%{email: "test@example.com"})
|> Map.get(:valid?)

# Inspect LiveView socket (requires PID from dev tools)
:sys.get_state(lv_pid) |> Map.get(:socket) |> Map.get(:assigns)

# Check module compiled
Code.ensure_loaded?(MyApp.SomeModule)

# Recompile if needed
IEx.Helpers.recompile()
```

## execute_sql_query - Database Operations

Best for: Verifying data, checking migrations, debugging queries

```sql
-- Check table structure
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'users';

-- Verify migration ran
SELECT * FROM schema_migrations ORDER BY inserted_at DESC LIMIT 5;

-- Check indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'users';

-- Debug query results
SELECT u.*, COUNT(p.id) as post_count
FROM users u
LEFT JOIN posts p ON p.user_id = u.id
GROUP BY u.id;

-- Check Oban jobs
SELECT id, worker, args, state, scheduled_at
FROM oban_jobs
ORDER BY inserted_at DESC
LIMIT 10;

-- Table exists?
SELECT EXISTS (
  SELECT FROM information_schema.tables
  WHERE table_name = 'users'
);
```

## get_docs - Fetch Documentation

Best for: Looking up function signatures, module docs, exact API

```
# Module documentation
Phoenix.LiveView

# Specific function
Ecto.Changeset.validate_required/3

# Callback documentation
Phoenix.LiveView.handle_event/3

# Type specifications
Ecto.Schema.belongs_to/3
```

**Advantage**: Returns docs for exact versions in your mix.lock

## get_source_location - Find Code

Best for: Locating modules, finding implementations

```
# Find module
MyApp.Accounts

# Find function
MyApp.Accounts.create_user/1

# Find LiveView
MyAppWeb.UserLive.Index

# Find component
MyAppWeb.CoreComponents.button/1
```

Returns: `{:ok, %{file: "lib/my_app/accounts.ex", line: 15}}`

## get_ecto_schemas - Introspect Data Model

Best for: Understanding existing schemas, checking fields/associations

```
# All schemas (no filter)

# Filter by name
User

# Filter by context
Accounts
```

Returns: Schema definitions including fields, types, associations, source table

## get_logs - Application Logs

Best for: Debugging errors, tracing requests

```
# All recent logs (no filter)

# Filter by level
level: :error

level: :warning
```

## Workflow Integration

### When Planning Features

1. Understand existing patterns: `get_ecto_schemas`
2. Check documentation: `get_docs` for relevant modules
3. Find similar code: `get_source_location`

### When Implementing

1. Test as you go: `project_eval` after each function
2. Verify queries: `execute_sql_query` for Ecto queries
3. Check for errors: `get_logs level: :error`

### When Debugging

1. Find the code: `get_source_location`
2. Read logs: `get_logs`
3. Test fix: `project_eval`
4. Verify data: `execute_sql_query`

### When Investigating Memory Leaks

Use `project_eval` to walk through a structured investigation:

```elixir
# 1. Find processes sorted by memory usage
Process.list()
|> Enum.map(fn pid ->
  info = Process.info(pid, [:memory, :message_queue_len, :registered_name])
  {pid, info}
end)
|> Enum.sort_by(fn {_, info} -> info[:memory] end, :desc)
|> Enum.take(10)

# 2. Inspect suspicious process (high memory or large message queue)
Process.info(pid, [:memory, :message_queue_len, :current_function, :initial_call, :dictionary])

# 3. Check supervision tree for the process
Process.info(pid, [:links, :monitors, :monitored_by])

# 4. If GenServer, inspect state size
:sys.get_state(pid) |> :erts_debug.size() |> Kernel.*(8)  # bytes
```

Flow: enumerate by memory → find outlier → check message queue → trace supervisor → propose fix
