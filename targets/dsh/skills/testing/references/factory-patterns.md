# Factory Patterns Reference

## ExMachina Style

```elixir
defmodule MyApp.Factory do
  use ExMachina.Ecto, repo: MyApp.Repo

  def user_factory do
    %MyApp.Accounts.User{
      name: sequence(:name, &"User #{&1}"),
      email: sequence(:email, &"user#{&1}@example.com")
    }
  end

  # Traits as functions
  def admin(user), do: %{user | role: :admin}
  def verified(user), do: %{user | verified_at: DateTime.utc_now()}
end

# Usage
user = build(:user) |> admin() |> verified() |> insert()
```

## Key Patterns

```elixir
# BUILD by default (no DB hit)
user = build(:user)

# INSERT only when needed
user = insert(:user)

# Associations - use build in factory, insert when needed
def post_factory do
  %Post{
    title: "Test",
    author: build(:user)  # NOT insert!
  }
end

# Sequences for uniqueness
sequence(:email, &"user#{&1}@example.com")
```

## Updating Factories for Required Fields

When a schema adds fields to `@required_fields`, update ALL factories
BEFORE running tests to prevent cascade failures:

1. Find all factories that build the affected struct
2. Add the new required fields with sensible defaults
3. Then run the test suite

```elixir
# Schema added currency_code to @required_fields
# -> Update factory FIRST:
def deal_factory do
  %Deal{
    title: sequence(:title, &"Deal #{&1}"),
    currency_code: :USD,          # NEW required field
    area_unit: :square_feet        # NEW required field
  }
end
```

Skipping this step causes 20+ test failures that all have the same
root cause (missing factory field) but look like unrelated failures.

## Anti-patterns

```elixir
# ❌ insert() in factory definitions
def post_factory do
  %Post{author: insert(:user)}  # Creates record even on build()!
end

# ✅ Use build() in factories
def post_factory do
  %Post{author: build(:user)}
end

# ❌ Hardcoded unique values
insert(:user, email: "test@example.com")  # Will fail on second run!

# ✅ Use sequences
insert(:user)  # Uses sequence for email
```

## Oban Testing

```elixir
# config/test.exs
config :my_app, Oban, testing: :manual

# In test
use Oban.Testing, repo: MyApp.Repo

test "enqueues welcome email" do
  {:ok, user} = Accounts.create_user(%{email: "test@example.com"})

  assert_enqueued worker: MyApp.WelcomeWorker,
                  args: %{user_id: user.id},
                  queue: :mailers
end

test "processes job correctly" do
  assert :ok = perform_job(MyApp.WelcomeWorker, %{user_id: 1})
end

test "drains queue" do
  assert %{success: 3, failure: 0} = Oban.drain_queue(queue: :default)
end
```

## Property Testing

```elixir
use ExUnitProperties

property "roundtrip encoding works" do
  check all data <- map_of(string(:alphanumeric), integer()) do
    assert data == data |> Jason.encode!() |> Jason.decode!()
  end
end

# Custom generator
email_gen = gen all
    name <- string(:alphanumeric, min_length: 1),
    domain <- member_of(["gmail.com", "outlook.com"]) do
  "#{name}@#{domain}"
end
```
