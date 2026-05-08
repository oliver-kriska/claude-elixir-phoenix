# With Statement and Pipe Operator Guide

## Contents

- [Why These Are Idiomatic](#why-these-are-idiomatic)
- [Pipe Operator](#pipe-operator-)
- [With Statement](#with-statement)
- [Real-World Examples from Production Code](#real-world-examples-from-production-code)
- [Summary](#summary)
- [Anti-Pattern: Avoiding Pipes and With](#anti-pattern-avoiding-pipes-and-with)

## Why These Are Idiomatic

Both `with` and `|>` are core Elixir idioms that experienced developers expect. Avoiding them leads to less readable, non-idiomatic code.

## Pipe Operator `|>`

### When to Use Pipes

```elixir
# ✅ Data transformation chains
params
|> Map.get("user")
|> normalize_email()
|> String.downcase()
|> String.trim()

# ✅ Query building
User
|> where(active: true)
|> where([u], u.role in ^roles)
|> order_by(desc: :inserted_at)
|> limit(10)
|> Repo.all()

# ✅ Changeset chains
%User{}
|> User.changeset(params)
|> put_change(:status, :pending)
|> validate_required([:email])
|> Repo.insert()

# ✅ Stream processing
1..1000
|> Stream.map(&expensive_operation/1)
|> Stream.filter(&valid?/1)
|> Enum.take(10)
```

### When NOT to Use Pipes

```elixir
# ❌ Single function call - no pipe needed
name |> String.upcase()
# ✅ Just call the function
String.upcase(name)

# ❌ When data isn't the first argument
Enum.map(list, &String.upcase/1) |> Enum.join(", ")
# ✅ Use variable or reorder
list
|> Enum.map(&String.upcase/1)
|> Enum.join(", ")

# ❌ Complex branching mid-pipe
data
|> transform()
|> (fn x -> if condition, do: a(x), else: b(x) end).()  # Ugly!
# ✅ Use case or separate function
data
|> transform()
|> handle_condition(condition)

defp handle_condition(x, true), do: a(x)
defp handle_condition(x, false), do: b(x)
```

### Pipe Style Rules

```elixir
# Start with data, not a function call
# ❌ Wrong
get_user(id)
|> process()

# ✅ Right
id
|> get_user()
|> process()

# Or just use variables for clarity
user = get_user(id)
process(user)
```

## With Statement

### When to Use With

```elixir
# ✅ Multiple dependent operations that can fail
def create_order(params) do
  with {:ok, user} <- get_user(params.user_id),
       {:ok, product} <- get_product(params.product_id),
       :ok <- check_inventory(product),
       {:ok, order} <- Orders.create(user, product, params) do
    {:ok, order}
  end
end

# ✅ Authorization chains
def update_post(user, post_id, params) do
  with {:ok, post} <- get_post(post_id),
       :ok <- authorize(user, :update, post),
       {:ok, updated} <- Posts.update(post, params) do
    {:ok, updated}
  end
end

# ✅ Validations that depend on each other
def process_upload(params) do
  with {:ok, file} <- validate_file_exists(params),
       {:ok, metadata} <- extract_metadata(file),
       :ok <- validate_file_type(metadata),
       {:ok, processed} <- process_file(file, metadata) do
    {:ok, processed}
  end
end
```

### When NOT to Use With

```elixir
# ❌ Single operation - use case instead
with {:ok, user} <- get_user(id) do
  {:ok, user}
end

# ✅ Just use case
case get_user(id) do
  {:ok, user} -> {:ok, user}
  {:error, _} = error -> error
end

# ❌ No failure handling needed - use pipes
with data <- fetch_data(),
     processed <- process(data),
     formatted <- format(processed) do
  formatted
end

# ✅ Use pipes
fetch_data()
|> process()
|> format()
```

### With Patterns

```elixir
# Pattern match in with clauses
with %User{active: true} = user <- get_user(id),
     %Subscription{status: :active} <- get_subscription(user) do
  {:ok, user}
else
  %User{active: false} -> {:error, :user_inactive}
  %Subscription{} -> {:error, :subscription_inactive}
  nil -> {:error, :not_found}
end

# Bare expressions (always match)
with {:ok, user} <- get_user(id),
     # This always succeeds, just assigns
     email = user.email,
     {:ok, _} <- send_notification(email) do
  :ok
end
```

### Handling Else Clauses

**Official anti-pattern**: Complex `else` in `with` — keep else to 1-2 clauses max. Normalize errors in helpers instead.

```elixir
# ✅ Simple: let non-matches pass through
def create_user(params) do
  with {:ok, validated} <- validate(params),
       {:ok, user} <- Repo.insert(validated) do
    {:ok, user}
  end
  # {:error, changeset} passes through unchanged
end

# ✅ When you need to transform errors
def create_user(params) do
  with {:ok, validated} <- validate(params),
       {:ok, user} <- Repo.insert(validated) do
    {:ok, user}
  else
    {:error, %Ecto.Changeset{} = changeset} ->
      {:error, :validation_failed, changeset}
    {:error, reason} ->
      {:error, :creation_failed, reason}
  end
end

# ❌ Avoid complex else clauses - normalize in helpers
# Instead of many else branches, make helpers return consistent errors
defp validate(params) do
  case Validator.validate(params) do
    :ok -> {:ok, params}
    {:error, reasons} -> {:error, {:validation, reasons}}
  end
end
```

## Real-World Examples from Production Code

### Context Function with Authorization

```elixir
def update_deal(broker, deal_id, params) do
  with {:ok, deal} <- get_deal(deal_id),
       :ok <- Bodyguard.permit(Deal, :update_deal, broker, deal),
       {:ok, updated} <- do_update_deal(deal, params) do
    broadcast_update(updated)
    {:ok, updated}
  end
end
```

### Query Building

```elixir
def list_articles(profile_id, opts \\ []) do
  Article
  |> where(profile_id: ^profile_id)
  |> filter_by_search(opts[:search])
  |> filter_by_status(opts[:status])
  |> filter_by_rating(opts[:rating])
  |> apply_sort(opts[:sort_by], opts[:sort_order])
  |> maybe_limit(opts[:limit])
  |> Repo.all()
end
```

### Changeset Operations

```elixir
def confirm_guest(guest, params) do
  guest
  |> Guest.confirm_changeset(params)
  |> maybe_update_attendees(params)
  |> Repo.update()
end
```

### Multi-Step Billing Check

```elixir
def check_feature_access(user, feature) do
  with true <- billing_enforced?(),
       {:ok, subscription} <- get_active_subscription(user),
       true <- feature_included?(subscription, feature) do
    :ok
  else
    false -> {:error, :feature_not_available}
    {:error, :no_subscription} -> {:error, :subscription_required}
  end
end
```

## Summary

| Pattern | Use When | Avoid When |
|---------|----------|------------|
| `\|>` pipe | Data transformation, query building, changesets | Single calls, complex branching |
| `with` | Multiple dependent fallible operations | Single operation, no failures possible |
| `case` | Pattern matching single value | Chaining multiple operations |
| Nested `case` | Never | Always - use `with` instead |

## Anti-Pattern: Avoiding Pipes and With

```elixir
# ❌ This is NOT more readable
result1 = function1(data)
result2 = function2(result1)
result3 = function3(result2)
final = function4(result3)

# ✅ Pipes are clearer for transformations
final =
  data
  |> function1()
  |> function2()
  |> function3()
  |> function4()

# ❌ Nested case is hard to follow
case get_user(id) do
  {:ok, user} ->
    case get_subscription(user) do
      {:ok, sub} ->
        case check_feature(sub, feature) do
          :ok -> {:ok, user}
          error -> error
        end
      error -> error
    end
  error -> error
end

# ✅ With flattens the happy path
with {:ok, user} <- get_user(id),
     {:ok, sub} <- get_subscription(user),
     :ok <- check_feature(sub, feature) do
  {:ok, user}
end
```
