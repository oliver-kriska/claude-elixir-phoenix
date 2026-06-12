# Oban Testing Patterns Reference

> **Official docs**: <https://hexdocs.pm/oban/testing.html>
> **Oban Pro testing**: <https://hexdocs.pm/oban_pro/testing.html>

## Configuration

```elixir
# config/test.exs
config :my_app, Oban, testing: :manual  # Or :inline
```

## Test Helper Setup

```elixir
defmodule MyApp.DataCase do
  using do
    quote do
      use Oban.Testing, repo: MyApp.Repo
    end
  end
end
```

## Assert Enqueued

```elixir
test "enqueues welcome email on signup" do
  {:ok, user} = Accounts.create_user(%{email: "test@example.com"})

  assert_enqueued worker: MyApp.WelcomeWorker,
                  args: %{user_id: user.id},
                  queue: :mailers
end

# Scheduled with tolerance
assert_enqueued worker: MyApp.ReminderWorker,
                scheduled_at: {tomorrow, delta: 60}

# Assert NOT enqueued
refute_enqueued worker: MyApp.WelcomeWorker
```

## Execute Jobs

```elixir
test "processes valid order" do
  assert :ok = perform_job(MyApp.OrderWorker, %{order_id: 1})
end

test "cancels for missing order" do
  assert {:cancel, _} = perform_job(MyApp.OrderWorker, %{order_id: -1})
end
```

## Drain Queues

```elixir
test "full workflow processes correctly" do
  {:ok, _} = MyApp.start_import(file_path: "data.csv")

  assert %{success: 3, failure: 0} = Oban.drain_queue(
    queue: :imports,
    with_scheduled: true,
    with_recursion: true
  )
end
```

## Oban Pro Testing

> If project uses Oban Pro, use `Oban.Pro.Testing` instead of `Oban.Testing`.
> Pro.Testing API may vary between versions — check `mix hex.docs online oban_pro`.

### Setup

```elixir
# In test helper or DataCase
use Oban.Pro.Testing, repo: MyApp.Repo
```

### Drain Jobs

```elixir
# Pro uses drain_jobs/1 instead of drain_queue/2
assert %{success: 3, failure: 0} = drain_jobs()
drain_jobs(with_scheduled: true, with_recursion: true)
```

### Test Workflows and Batches

```elixir
# Workflow test — insert and drain
test "ETL workflow completes" do
  alias Oban.Pro.Workflow

  Workflow.new()
  |> Workflow.add(:extract, ExtractWorker.new(%{source: "test"}))
  |> Workflow.add(:load, LoadWorker.new(%{}), deps: [:extract])
  |> Oban.insert_all()

  assert %{success: 2} = drain_jobs()
end
```

---

## Anti-patterns

```elixir
# ❌ No idempotency for payments
def perform(%Job{args: %{"amount" => amount}}) do
  PaymentGateway.charge(amount)  # Will double-charge on retry!
end

# ✅ Idempotency key
def perform(%Job{args: %{"amount" => amount, "idempotency_key" => key}}) do
  case Payments.find_by_key(key) do
    {:ok, existing} -> {:ok, existing}
    :not_found -> PaymentGateway.charge(amount, idempotency_key: key)
  end
end

# ❌ Large data in args
%{file_content: large_binary}

# ✅ Store reference
%{file_path: "/uploads/abc123.csv"}

# ❌ No unique constraint for user actions
# Double-click creates duplicate jobs!

# ✅ Add unique constraint
unique: [period: {5, :minutes}, keys: [:user_id, :action]]
```
