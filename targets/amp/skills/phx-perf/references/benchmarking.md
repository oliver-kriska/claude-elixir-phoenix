# Benchmarking and Profiling

## Benchee Patterns

### Basic Benchmark

```elixir
# In a script or IEx
Benchee.run(%{
  "current" => fn -> MyModule.current_impl(data) end,
  "optimized" => fn -> MyModule.optimized_impl(data) end
}, time: 10, memory_time: 2)
```

### Benchmark with Setup

```elixir
Benchee.run(%{
  "preload" => fn {posts, _} ->
    Repo.preload(posts, :comments)
  end,
  "join" => fn {_, query} ->
    Repo.all(query)
  end
}, before_each: fn _ ->
  posts = Repo.all(Post)
  query = from(p in Post, join: c in assoc(p, :comments), preload: [comments: c])
  {posts, query}
end)
```

### Comparing Query Strategies

```elixir
Benchee.run(%{
  "separate_queries" => fn ->
    posts = Repo.all(Post)
    Repo.preload(posts, :comments)
  end,
  "join_preload" => fn ->
    from(p in Post, join: c in assoc(p, :comments), preload: [comments: c])
    |> Repo.all()
  end,
  "subquery" => fn ->
    from(p in Post, preload: [comments: ^from(c in Comment, order_by: c.inserted_at)])
    |> Repo.all()
  end
})
```

## Ecto Query Analysis

### EXPLAIN ANALYZE via Tidewave

```elixir
# Check query plan for a specific query
Repo.query!("EXPLAIN ANALYZE SELECT * FROM users WHERE email = $1", ["test@example.com"])
```

### Missing Index Detection

```sql
-- Find sequential scans on large tables
SELECT schemaname, relname, seq_scan, seq_tup_read,
       idx_scan, idx_tup_fetch
FROM pg_stat_user_tables
WHERE seq_scan > 100
ORDER BY seq_tup_read DESC;
```

```sql
-- Find tables without indexes on foreign keys
SELECT c.conrelid::regclass AS table_name,
       a.attname AS column_name
FROM pg_constraint c
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
WHERE c.contype = 'f'
AND NOT EXISTS (
  SELECT 1 FROM pg_index i
  WHERE i.indrelid = c.conrelid
  AND a.attnum = ANY(i.indkey)
);
```

### N+1 Detection Patterns

Common patterns that indicate N+1 queries:

```elixir
# Pattern 1: Repo call inside Enum.map
users
|> Enum.map(fn user -> Repo.preload(user, :posts) end)
# Fix: Repo.preload(users, :posts)

# Pattern 2: Association access without preload
for post <- posts do
  length(post.comments)  # Triggers lazy load per post
end
# Fix: posts = Repo.preload(posts, :comments)

# Pattern 3: Repo.get inside comprehension
for id <- user_ids do
  Repo.get!(User, id)
end
# Fix: Repo.all(from u in User, where: u.id in ^user_ids)
```

## LiveView Memory Profiling

### Assign Size Estimation

```elixir
# Check socket assign sizes (in IEx with Tidewave)
socket.assigns
|> Enum.map(fn {key, val} -> {key, :erts_debug.size(val) * 8} end)
|> Enum.sort_by(&elem(&1, 1), :desc)
|> Enum.take(10)
```

### Process Memory Check

```elixir
# Check LiveView process memory
Process.info(pid, [:memory, :message_queue_len, :heap_size])
```

### Stream vs Assign Comparison

| Metric | Regular Assign | Stream |
|--------|---------------|--------|
| Memory per item | Full struct | DOM patch |
| Memory growth | O(n) items | O(1) patches |
| Reconnect cost | Full list | Full list |
| Append cost | Full list diff | Single item |

Rule of thumb: Use streams when list > 100 items OR items
are frequently updated.

## OTP Bottleneck Detection

### GenServer Mailbox

```elixir
# Check if GenServer has mailbox buildup
{:message_queue_len, len} = Process.info(pid, :message_queue_len)
# len > 100 indicates bottleneck
```

### Observer Patterns

```elixir
# Start observer for visual process tree
:observer.start()

# Or use runtime_tools for production
:sys.get_state(pid)       # Current state (careful with large state)
:sys.statistics(pid, :get) # Call/message statistics
```

### ETS vs GenServer Decision

| Access Pattern | Use |
|---------------|-----|
| Read-heavy, write-rare | ETS (concurrent reads) |
| Write-heavy | GenServer (serialized writes) |
| Mixed, small state | GenServer |
| Mixed, large state | ETS with GenServer for writes |

## Flame Graph Interpretation

### Generating Flame Graphs

```elixir
# Using eflambe
:eflambe.apply({MyModule, :my_function, [args]}, output_format: :brendan_gregg)

# Using eflame (simpler)
:eflame.apply(MyModule, :my_function, [args])
```

### Reading Flame Graphs

- **Width** = time spent (wider = slower)
- **Height** = call stack depth
- Look for wide bars at the top (leaf functions consuming time)
- Common culprits: `Enum.map`, `Jason.encode`, `Repo.query`

### Production-Safe Profiling

```elixir
# Use :recon for production systems
:recon.proc_count(:memory, 10)      # Top 10 by memory
:recon.proc_count(:reductions, 10)  # Top 10 by CPU
:recon.proc_count(:message_queue_len, 10)  # Top 10 by mailbox
```

## Performance Checklist

### Ecto

- [ ] No `Repo.` calls inside `Enum.map/each/reduce`
- [ ] Preloads use batch loading, not per-record
- [ ] Frequently queried columns have indexes
- [ ] Large result sets use `Repo.stream` or pagination
- [ ] Aggregations done in SQL, not Elixir

### LiveView

- [ ] Lists > 100 items use `stream/3`
- [ ] Expensive operations use `assign_async/3`
- [ ] No unbounded assign growth in `handle_info`
- [ ] PubSub messages are small (IDs, not full structs)

### OTP

- [ ] GenServers don't do heavy work in `handle_call`
- [ ] Long operations use `Task.async` or `handle_continue`
- [ ] No synchronous GenServer calls in request hot path
- [ ] ETS used for read-heavy shared state
