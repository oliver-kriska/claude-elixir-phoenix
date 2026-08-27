# Worker Patterns Reference

## Worker Options

```elixir
use Oban.Worker,
  queue: :mailers,           # Queue name
  max_attempts: 5,           # Retries before discarded
  priority: 1,               # 0-9, lower = higher priority
  tags: ["email"],           # For filtering/monitoring
  unique: [                  # Deduplication
    period: {5, :minutes},
    keys: [:user_id],
    states: [:available, :scheduled, :executing],
    fields: [:worker, :queue, :args]
  ]
```

## Unique Jobs (Deduplication)

```elixir
use Oban.Worker,
  unique: [
    period: {2, :minutes},     # Uniqueness window
    keys: [:user_id],          # Only compare these arg keys
    states: [:available, :scheduled, :executing],
    fields: [:worker, :queue, :args]
  ]
```

## Custom Backoff

```elixir
@impl Oban.Worker
def backoff(%Job{attempt: attempt}) do
  # Exponential with jitter
  trunc(:math.pow(attempt, 4) + 15 + :rand.uniform(30) * attempt)
end
```

## Custom Timeout

```elixir
@impl Oban.Worker
def timeout(_job), do: :timer.minutes(5)
```

## Idempotency Pattern

```elixir
defmodule MyApp.Workers.ChargeWorker do
  use Oban.Worker,
    queue: :payments,
    max_attempts: 3,
    unique: [period: {24, :hours}, keys: [:idempotency_key]]

  @impl Oban.Worker
  def perform(%Job{args: %{"idempotency_key" => key, "user_id" => user_id, "amount" => amount}}) do
    case Payments.find_by_idempotency_key(key) do
      {:ok, existing} ->
        {:ok, existing}

      :not_found ->
        Payments.charge(user_id, amount, idempotency_key: key)
    end
  end
end
```

## Error Handling & Telemetry

```elixir
# In application.ex or telemetry.ex
:telemetry.attach(
  "oban-errors",
  [:oban, :job, :exception],
  &MyApp.ObanErrorReporter.handle_event/4,
  []
)

defmodule MyApp.ObanErrorReporter do
  def handle_event([:oban, :job, :exception], _measure, %{job: job}, _config) do
    %{reason: exception, stacktrace: stacktrace} = job.unsaved_error

    Sentry.capture_exception(exception,
      stacktrace: stacktrace,
      extra: Map.take(job, [:id, :args, :queue, :worker]),
      tags: %{oban_worker: job.worker}
    )
  end
end
```

## Runtime Queue Control

```elixir
# Pause/resume
Oban.pause_queue(queue: :mailers)
Oban.resume_queue(queue: :mailers)

# Scale
Oban.scale_queue(queue: :mailers, limit: 50)

# Start new queue at runtime
Oban.start_queue(queue: :new_queue, limit: 10)
```

## Anti-patterns

```elixir
# ❌ Atom keys in args (JSON roundtrip converts to strings)
def perform(%Job{args: %{user_id: id}})  # Won't match!

# ✅ String keys
def perform(%Job{args: %{"user_id" => id}})

# ❌ Struct in args
%{user: %User{id: 1, name: "Jane"}}  # Can't serialize!

# ✅ Just the ID
%{user_id: 1}

# ❌ Silent failures
def perform(%Job{args: args}) do
  Mailer.send(args["email"])  # Ignores return value!
end

# ✅ Handle all outcomes
def perform(%Job{args: %{"email" => email}}) do
  case Mailer.send(email) do
    {:ok, _} -> :ok
    {:error, :invalid_email} -> {:cancel, "Invalid email"}
    {:error, reason} -> {:error, reason}
  end
end
```
