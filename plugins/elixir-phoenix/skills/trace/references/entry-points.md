# Entry Points Reference

Patterns for identifying entry points in Elixir/Phoenix applications. These are where request/event handling begins - stop tracing here.

## Phoenix Controllers

```elixir
# Standard REST actions
def index(conn, _params)
def show(conn, %{"id" => id})
def new(conn, _params)
def create(conn, %{"user" => user_params})
def edit(conn, %{"id" => id})
def update(conn, %{"id" => id, "user" => user_params})
def delete(conn, %{"id" => id})

# Custom actions
def custom_action(conn, params)
```

**Detection pattern:**

```regex
def (index|show|new|create|edit|update|delete|\w+)\(conn[,\s]
```

**Entry point info:**

- Route: Check `router.ex` for matching path
- HTTP method: GET/POST/PUT/PATCH/DELETE
- Params come from: URL params, query string, request body

## Phoenix LiveView

```elixir
# Lifecycle
def mount(params, session, socket)
def handle_params(params, uri, socket)
def terminate(reason, socket)

# Events
def handle_event("event_name", params, socket)
def handle_event("event_name", %{"key" => value}, socket)

# Messages
def handle_info(message, socket)
def handle_info({:ref, data}, socket)
def handle_info(%Phoenix.Socket.Broadcast{}, socket)

# Async operations
def handle_async(name, async_fun_result, socket)
```

**Detection patterns:**

```regex
def mount\(_?\w*, _?\w*, socket\)
def handle_event\("[\w-]+", .*, socket\)
def handle_info\(.*, socket\)
def handle_params\(.*, .*, socket\)
```

**Entry point info:**

- mount: Initial page load, params from URL
- handle_event: User interaction, params from JS/form
- handle_info: PubSub messages, process messages
- handle_params: URL changes (live_patch)

## LiveComponent

```elixir
# Lifecycle
def mount(socket)
def update(assigns, socket)
def handle_event("event", params, socket)
```

**Note:** LiveComponents receive assigns from parent, but handle_event is an entry point for component-specific events.

## Oban Workers

```elixir
# Standard perform
def perform(%Oban.Job{args: args} = job)
def perform(%Oban.Job{args: %{"user_id" => user_id}})

# With meta
def perform(%Oban.Job{args: args, meta: meta})
```

**Detection pattern:**

```regex
def perform\(%Oban\.Job\{
```

**Entry point info:**

- Triggered by: Oban queue processing
- Args source: `Oban.insert(%{args: %{...}})`
- No user context (unless passed in args)

## GenServer

```elixir
# Synchronous calls
def handle_call(request, from, state)
def handle_call({:get, key}, _from, state)
def handle_call(:status, _from, state)

# Asynchronous casts
def handle_cast(request, state)
def handle_cast({:update, value}, state)

# Info messages
def handle_info(message, state)
def handle_info(:tick, state)
def handle_info({:DOWN, ref, :process, pid, reason}, state)

# Init
def init(args)
```

**Detection patterns:**

```regex
def handle_call\(.*, _?from, state\)
def handle_cast\(.*, state\)
def handle_info\(.*, state\)
def init\(
```

**Entry point info:**

- handle_call: From `GenServer.call(pid, request)`
- handle_cast: From `GenServer.cast(pid, request)`
- handle_info: From `send(pid, message)` or system messages

## Plugs

```elixir
# Module plug
def call(conn, opts)
def init(opts)

# Function plug (in controller)
plug :authenticate

def authenticate(conn, _opts)
```

**Detection pattern:**

```regex
def call\(conn, opts?\)
```

**Note:** Plugs are middleware, often not final entry points but part of the chain.

## Mix Tasks

```elixir
def run(args)
def run([])
def run(["--flag", value | rest])
```

**Detection pattern:**

```regex
def run\(\[
def run\(args\)
```

**Entry point info:**

- Triggered by: `mix task_name args`
- Args: Command line arguments as list

## Phoenix Channels

```elixir
# Join
def join(topic, payload, socket)
def join("room:" <> room_id, _payload, socket)

# Messages
def handle_in(event, payload, socket)
def handle_in("new_msg", %{"body" => body}, socket)

# Info
def handle_info(message, socket)
```

**Detection patterns:**

```regex
def join\("[\w:]+.*, .*, socket\)
def handle_in\("[\w_]+", .*, socket\)
```

## Broadway (Message Processing)

```elixir
def handle_message(processor, message, context)
def handle_batch(batcher, messages, batch_info, context)
def handle_failed(messages, context)
```

**Entry point info:**

- Messages from: Kafka, RabbitMQ, SQS, etc.
- Batch processing context

## Absinthe (GraphQL)

```elixir
# Resolver
def resolve(parent, args, resolution)
def resolve(_parent, %{id: id}, _resolution)

# Middleware
def call(resolution, config)
```

**Entry point info:**

- Triggered by: GraphQL query/mutation
- Args from: GraphQL variables

## Entry Point Detection Code

```elixir
@entry_patterns [
  # Phoenix Controllers
  ~r/def\s+(index|show|new|create|edit|update|delete)\s*\(\s*conn/,
  ~r/def\s+\w+\s*\(\s*conn\s*,/,

  # LiveView
  ~r/def\s+mount\s*\([^)]*socket\s*\)/,
  ~r/def\s+handle_event\s*\("/,
  ~r/def\s+handle_info\s*\([^)]*socket\s*\)/,
  ~r/def\s+handle_params\s*\(/,

  # Oban
  ~r/def\s+perform\s*\(\s*%Oban\.Job/,

  # GenServer
  ~r/def\s+handle_call\s*\(/,
  ~r/def\s+handle_cast\s*\(/,
  ~r/def\s+handle_info\s*\([^)]*state\s*\)/,
  ~r/def\s+init\s*\(/,

  # Plug
  ~r/def\s+call\s*\(\s*conn\s*,\s*opts?\s*\)/,

  # Mix Task
  ~r/def\s+run\s*\(\s*[\[\w]/
]

def entry_point?(line) do
  Enum.any?(@entry_patterns, &Regex.match?(&1, line))
end
```

## Contextualizing Entry Points

When you find an entry point, gather this context:

| Entry Point Type | Find This |
|------------------|-----------|
| Controller | Route in `router.ex`, auth plugs |
| LiveView | Route, on_mount hooks |
| Oban Worker | Queue config, scheduling |
| GenServer | How it's started, supervision tree |
| Channel | Socket config, join conditions |
