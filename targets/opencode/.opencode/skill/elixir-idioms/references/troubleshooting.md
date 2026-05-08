# BEAM Troubleshooting Playbook

Production debugging for Phoenix/BEAM applications. For code bugs, see `deep-bug-investigator` agent.

## Quick Diagnosis

| Symptom | Likely Cause | Section |
|---------|--------------|---------|
| High memory, growing | Process leak, ETS bloat | Memory Issues |
| Slow responses | N+1, GenServer bottleneck | Performance |
| Random crashes | Unhandled errors, supervisor | Crashes |
| Timeouts | DB pool, GenServer call | Timeouts |
| Node unresponsive | Scheduler block, long GC | BEAM Issues |

## Memory Issues

### With Tidewave

```elixir
# Top memory processes
mcp__tidewave__project_eval """
Process.list()
|> Enum.map(fn pid -> {pid, Process.info(pid, :memory)} end)
|> Enum.filter(fn {_, mem} -> mem != nil end)
|> Enum.map(fn {pid, {:memory, mem}} -> {pid, mem} end)
|> Enum.sort_by(&elem(&1, 1), :desc)
|> Enum.take(10)
|> Enum.map(fn {pid, mem} ->
  info = Process.info(pid, [:registered_name, :current_function])
  {info[:registered_name] || pid, div(mem, 1024), info[:current_function]}
end)
"""

# ETS table sizes
mcp__tidewave__project_eval """
:ets.all()
|> Enum.map(fn t -> {t, :ets.info(t, :memory) * :erlang.system_info(:wordsize)} end)
|> Enum.sort_by(&elem(&1, 1), :desc)
|> Enum.take(10)
|> Enum.map(fn {t, mem} -> {t, div(mem, 1024)} end)
"""
```

### Without Tidewave

```bash
# Attach to running node
iex --sname debug --remsh myapp@hostname

# In IEx
:observer.start()
```

### Common Causes

1. **LiveView socket assigns** - Use `temporary_assigns` or streams
2. **ETS table growth** - Check for missing cleanup
3. **Process mailbox** - GenServer not keeping up
4. **Binary memory** - Large binaries not GC'd (use `:binary.copy/1`)

## Performance Issues

### N+1 Query Detection

```elixir
# config/dev.exs - log slow queries
config :my_app, MyApp.Repo,
  log: :debug,
  stacktrace: true
```

### GenServer Bottleneck

```elixir
mcp__tidewave__project_eval """
pid = Process.whereis(MyApp.SomeServer)
{:message_queue_len, len} = Process.info(pid, :message_queue_len)
IO.puts("Queue length: \#{len}")  # >100 = problem
"""
```

**Signs:**

- Message queue growing
- Call timeouts
- Single process high CPU

**Solutions:**

- Pool of workers (Poolboy)
- ETS for read-heavy (GenServer writes, ETS reads)
- Partition by key (Registry + DynamicSupervisor)

### Slow Ecto Queries

```sql
-- With Tidewave
mcp__tidewave__execute_sql_query """
SELECT query, calls, mean_time, total_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10
"""

-- Missing indexes
mcp__tidewave__execute_sql_query """
SELECT relname, seq_scan, idx_scan
FROM pg_stat_user_tables
WHERE seq_scan > idx_scan
ORDER BY seq_scan DESC
"""
```

## Crashes

### Common Crash Patterns

| Error | Cause | Fix |
|-------|-------|-----|
| `noproc` | Process died/not started | Check supervisor, handle `{:error, _}` |
| `timeout` | GenServer.call timeout | Increase timeout or use cast |
| `badmatch` | Pattern match failed | Add catch-all clause |
| `function_clause` | No matching function | Check guards, add fallback |
| `badarg` | Wrong argument type | Validate input |

### Supervisor Tree Analysis

```elixir
mcp__tidewave__project_eval """
Supervisor.which_children(MyApp.Supervisor)
|> Enum.map(fn {id, pid, type, _} ->
  %{id: id, pid: pid, type: type}
end)
"""
```

## Timeouts

### DB Pool Exhaustion

**Symptoms:** Random timeouts, "connection not available"

**Check:**

```elixir
# Current pool size
Application.get_env(:my_app, MyApp.Repo)[:pool_size]
```

**Solutions:**

- Increase `pool_size`
- Add `queue_target` and `queue_interval`
- Find long-running queries
- Use `Repo.checkout/1` properly for transactions

### GenServer Call Timeout

```elixir
# Default is 5000ms
GenServer.call(pid, :request, 10_000)  # Increase if needed

# Or use cast + handle_info for async
GenServer.cast(pid, {:request, self()})
```

## BEAM Issues

### Scheduler Utilization

```elixir
mcp__tidewave__project_eval """
:scheduler.utilization(1000)  # Sample for 1 second
"""
```

### Long GC Pauses

```elixir
# Enable GC logging
:erlang.system_flag(:long_gc, 50)  # Log GC > 50ms
```

### Dirty Schedulers Blocked

```elixir
mcp__tidewave__project_eval """
:erlang.statistics(:dirty_cpu_run_queue_lengths)
"""
```

## Quick Checklist

```markdown
## Troubleshooting: [Issue]

### Symptoms
- [ ] High memory?
- [ ] Slow responses?
- [ ] Timeouts?
- [ ] Crashes?

### Checked
- [ ] Logs: `mcp__tidewave__get_logs level: :error`
- [ ] Memory: Top processes
- [ ] Queries: Slow query log
- [ ] Processes: GenServer queue lengths

### Root Cause
[...]

### Fix
[...]
```
