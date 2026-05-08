# OTP Patterns Reference

> **Official docs**: <https://hexdocs.pm/elixir/GenServer.html> | <https://hexdocs.pm/elixir/Supervisor.html>
> **Elixir guides**: <https://hexdocs.pm/elixir/introduction.html> (see OTP section)

## Contents

- [Core Rule](#core-rule-no-process-without-a-runtime-reason)
- [BEAM Architecture Context](#beam-architecture-context)
- [Decision Tree](#decision-tree)
- [Quick Reference Table](#quick-reference-table)
- [Plain Functions](#plain-functions-default-choice)
- [Agent: Simple State](#agent-simple-state)
- [ETS](#ets-shared-state-without-serialization)
- [GenServer](#genserver-complex-state-management)
- [Task](#task-one-off-async-work)
- [Supervisor](#supervisor-fault-tolerance)
- [DynamicSupervisor](#dynamicsupervisor-on-demand-children)
- [Registry](#registry-dynamic-process-naming)
- [Common Scenarios](#common-scenarios)
- [Resource Cleanup](#resource-cleanup-tryafter-not-tryrescue)
- [Anti-Patterns](#anti-patterns)

## Core Rule: NO PROCESS WITHOUT A RUNTIME REASON

Processes model **runtime properties**, not code organization:

- ✓ Concurrency needs
- ✓ Shared resources requiring serialized access
- ✓ Error isolation domains
- ✓ State that survives between operations
- ✗ Code organization (MAJOR ANTI-PATTERN)
- ✗ Stateless computation
- ✗ Namespacing

## BEAM Architecture Context

Understanding these fundamentals explains WHY patterns exist:

- **Processes are cheap**: 2.6KB each, ~134M possible per VM
- **Complete isolation**: Each has own stack/heap/mailbox
- **Messages are copied**: Keep messages small (except binaries >64 bytes)
- **Per-process GC**: No global GC pauses
- **Preemptive scheduling**: Fair CPU time via reductions
- **"Let it crash"**: Focus on happy path, supervisors restart to known-good state

## Decision Tree

```
Need to maintain state?
├─ No → Use plain functions
└─ Yes
    ├─ Simple get/update only? → Agent or ETS
    ├─ Complex message handling? → GenServer
    │   ├─ Need timeouts/monitors? → GenServer
    │   └─ Children started dynamically? → DynamicSupervisor
    └─ One-off async work? → Task
```

## Quick Reference Table

| Need | Solution | Notes |
|------|----------|-------|
| Stateless computation | Functions | Default choice |
| Simple get/set state | Agent | No monitors/timers |
| Fast key-value lookups | ETS | Many readers, no serialization |
| Complex state/coordination | GenServer | Monitors, timers, handle_info |
| One-off async work | Task | Task.Supervisor for production |
| Dynamic worker pool | DynamicSupervisor + Registry | Per-user/session processes |
| Connection pool | GenServer | Checkout/checkin with monitors |
| Fault tolerance | Supervisor | Always supervise! |

---

## Plain Functions (Default Choice)

```elixir
# DO: Stateless computation
defmodule Calculator do
  def add(a, b), do: a + b
  def multiply(a, b), do: a * b
end

# DON'T: GenServer for stateless work
defmodule Calculator do
  use GenServer
  def add(a, b), do: GenServer.call(__MODULE__, {:add, a, b})
  def handle_call({:add, a, b}, _from, state), do: {:reply, a + b, state}
end
```

## Agent: Simple State

**Use when**: Only get/update operations, no monitors/timers

**Don't use when**: Need handle_info, monitors, distributed system

```elixir
defmodule Counter do
  use Agent

  def start_link(initial) do
    Agent.start_link(fn -> initial end, name: __MODULE__)
  end

  def value, do: Agent.get(__MODULE__, & &1)
  def increment, do: Agent.update(__MODULE__, &(&1 + 1))
  def reset, do: Agent.update(__MODULE__, fn _ -> 0 end)
end
```

## ETS: Shared State Without Serialization

**Use when**: Many concurrent readers/writers, key-value pairs, performance critical

**Don't use when**: Need complex coordination, complex relationships

```elixir
# Create table (usually in Application.start/2)
:ets.new(:my_cache, [:named_table, :public, read_concurrency: true])

# Use from anywhere
:ets.insert(:my_cache, {:key, value})
[{:key, value}] = :ets.lookup(:my_cache, :key)
:ets.delete(:my_cache, :key)
```

## GenServer: Complex State Management

**Use for**: Complex coordination, serializing access, managing external resources, monitors/timers

**DO NOT use for**: Code organization, stateless computation, simple get/update

```elixir
defmodule ConnectionPool do
  use GenServer

  # Client API
  def start_link(opts) do
    GenServer.start_link(__MODULE__, opts, name: __MODULE__)
  end

  def checkout, do: GenServer.call(__MODULE__, :checkout)
  def checkin(conn), do: GenServer.cast(__MODULE__, {:checkin, conn})

  # Server callbacks
  @impl GenServer
  def init(opts) do
    {:ok, %{available: [], checked_out: %{}, max: opts[:max] || 10}}
  end

  @impl GenServer
  def handle_call(:checkout, {pid, _ref}, state) do
    ref = Process.monitor(pid)  # Clean up if caller crashes
    # ... checkout logic
    {:reply, conn, updated_state}
  end

  @impl GenServer
  def handle_info({:DOWN, _ref, :process, pid, _reason}, state) do
    # Clean up crashed process's connections
    {:noreply, cleanup_for_pid(state, pid)}
  end
end
```

### Expensive Initialization

```elixir
# DO: Use handle_continue (OTP 21+)
@impl GenServer
def init(args) do
  {:ok, initial_state, {:continue, :load_data}}
end

@impl GenServer
def handle_continue(:load_data, state) do
  # GUARANTEED to run before any messages
  {:noreply, %{state | data: load_expensive_data()}}
end

# DON'T: send(self(), :init) - not guaranteed order
```

## Task: One-Off Async Work

```elixir
# Fire-and-forget (won't crash caller)
Task.Supervisor.start_child(MyApp.TaskSupervisor, fn ->
  do_background_work()
end)

# Async with timeout and error handling
task = Task.Supervisor.async_nolink(MyApp.TaskSupervisor, fn ->
  might_fail()
end)

case Task.yield(task, 5000) || Task.shutdown(task) do
  {:ok, result} -> result
  {:exit, reason} -> handle_error(reason)
  nil -> handle_timeout()
end

# Concurrent collection processing
urls
|> Task.async_stream(&fetch_url/1, max_concurrency: 10, timeout: 30_000)
|> Enum.map(fn {:ok, result} -> result end)
```

## Supervisor: Fault Tolerance

**Always supervise processes**. Never use `{:ok, pid} = GenServer.start_link(...)` in production.

```elixir
children = [
  {Registry, keys: :unique, name: MyApp.Registry},
  {MyApp.CacheServer, []},
  {DynamicSupervisor, name: MyApp.WorkerSupervisor, strategy: :one_for_one},
  {Task.Supervisor, name: MyApp.TaskSupervisor}
]

Supervisor.start_link(children,
  strategy: :one_for_one,
  max_restarts: 3,
  max_seconds: 5
)
```

### Restart Strategies

| Strategy | Behavior | Use When |
|----------|----------|----------|
| `:one_for_one` | Restart only crashed child | Children are independent |
| `:one_for_all` | Restart all children | Children are tightly coupled |
| `:rest_for_one` | Restart crashed + those started after | Later depend on earlier |

### Restart Types

- `:permanent` - Always restart (default for most workers)
- `:temporary` - Never restart (one-off tasks)
- `:transient` - Restart only on abnormal exit

## DynamicSupervisor: On-Demand Children

```elixir
# Combined with Registry for named access
def start_worker(user_id) do
  name = {:via, Registry, {MyApp.WorkerRegistry, user_id}}
  spec = {Worker, name: name, user_id: user_id}
  DynamicSupervisor.start_child(MyApp.WorkerSupervisor, spec)
end

def find_worker(user_id) do
  case Registry.lookup(MyApp.WorkerRegistry, user_id) do
    [{pid, _}] -> {:ok, pid}
    [] -> {:error, :not_found}
  end
end
```

## Registry: Dynamic Process Naming

```elixir
# Unique registration (no atom explosion)
name = {:via, Registry, {MyApp.Registry, "user:#{user_id}"}}
GenServer.start_link(UserWorker, args, name: name)

# Lookup
case Registry.lookup(MyApp.Registry, "user:#{user_id}") do
  [{pid, _}] -> {:ok, pid}
  [] -> {:error, :not_found}
end

# Pub/sub broadcast (duplicate keys registry)
Registry.dispatch(PubSubRegistry, "topic", fn entries ->
  for {pid, _} <- entries, do: send(pid, {:broadcast, message})
end)
```

---

## Common Scenarios

### Cache

**Pattern**: ETS (not GenServer)
**Why**: Many concurrent readers/writers, no coordination needed

### Rate Limiting

**Pattern**: ETS + optional GenServer for cleanup
**Why**: ETS for fast lookups, GenServer only if need periodic cleanup

### Background Job

**Pattern**: Task.Supervisor (or Oban for persistence)
**Why**: Don't need long-lived state, just async execution

### Connection Pool

**Pattern**: GenServer
**Why**: Need serialization, monitors, complex coordination

### User Session State

**Pattern**: DynamicSupervisor + Registry + GenServer
**Why**: Dynamic per-user processes, fault isolation, named access

---

## Resource Cleanup: try/after (Not try/rescue)

When wrapping code in instrumentation spans, telemetry, or any
resource that needs guaranteed cleanup:

```elixir
# CORRECT: try/after — runs ALWAYS
def instrumented_call(args) do
  span = Tracer.start_span("operation")
  try do
    do_work(args)
  after
    Tracer.finish_span(span)
  end
end

# WRONG: try/rescue — only runs on exception
def instrumented_call(args) do
  span = Tracer.start_span("operation")
  try do
    do_work(args)
  rescue
    e -> Tracer.finish_span(span); reraise e, __STACKTRACE__
  end
  Tracer.finish_span(span)  # Missed if do_work throws non-exception exit
end
```

**Rule**: `try/rescue` only catches exceptions. `try/after`
runs unconditionally — use it for spans, file handles, locks,
and any cleanup that must happen regardless of outcome.

## Anti-Patterns

### 1. GenServer for Code Organization

```elixir
# ANTI-PATTERN
defmodule Calculator do
  use GenServer
  def add(a, b), do: GenServer.call(__MODULE__, {:add, a, b})
end

# CORRECT
defmodule Calculator do
  def add(a, b), do: a + b
end
```

### 2. Scattered Process Interfaces

```elixir
# ANTI-PATTERN: Calling Agent from multiple modules
Agent.get(MyApp.Cache, &Map.get(&1, key))  # In various modules

# CORRECT: Encapsulate in single module
defmodule MyApp.Cache do
  use Agent
  def get(key), do: Agent.get(__MODULE__, &Map.get(&1, key))
end
```

### 3. Sending Unnecessary Data in Closures

```elixir
# ANTI-PATTERN: Captures entire struct
spawn(fn -> log_ip(conn.remote_ip) end)  # Copies entire conn!

# CORRECT: Extract before spawning
ip = conn.remote_ip
spawn(fn -> log_ip(ip) end)
```

### 4. Unsupervised Processes

```elixir
# ANTI-PATTERN
{:ok, pid} = GenServer.start_link(MyServer, [])

# CORRECT
children = [{MyServer, []}]
Supervisor.start_link(children, strategy: :one_for_one)
```

### 5. Global Singleton Bottleneck

```elixir
# ANTI-PATTERN: Global singleton for per-user data
GenServer.call(UserStateServer, {:get_user, user_id})

# CORRECT: DynamicSupervisor + Registry for per-user processes
name = {:via, Registry, {MyApp.Registry, "user:#{user_id}"}}
```
