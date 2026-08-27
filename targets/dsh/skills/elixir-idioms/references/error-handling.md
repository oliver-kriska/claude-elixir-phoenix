# Error Handling Reference

## Decision Tree

```
Is failure expected in normal operation?
├─ Yes → {:ok, _}/{:error, _} tuples
│   ├─ Chaining operations? → with
│   └─ Need both variants? → Provide foo/foo!
└─ No (unexpected/bug) → raise exception
    └─ Supervision handles recovery
```

## When to Use Each

| Use Exceptions | Use Error Tuples |
|----------------|------------------|
| Programming bugs | Expected failures |
| Truly unexpected errors | User input validation |
| Can't recover gracefully | Caller should handle |
| "Let it crash" scenarios | Control flow decisions |

## Tagged Tuple Pattern

```elixir
# Return error tuples for expected failures
def divide(a, b) when b != 0, do: {:ok, a / b}
def divide(_, 0), do: {:error, :division_by_zero}

# Bang variant raises for callers who want to crash
def divide!(a, b) do
  case divide(a, b) do
    {:ok, result} -> result
    {:error, reason} -> raise ArgumentError, "Cannot divide: #{reason}"
  end
end
```

## With for Happy Path

```elixir
# PREFER: with for multi-step operations
def create_order(params) do
  with {:ok, user} <- get_user(params.user_id),
       {:ok, product} <- get_product(params.product_id),
       {:ok, order} <- Orders.create(user, product) do
    {:ok, order}
  end
end

# AVOID: with for single operation
with {:ok, user} <- get_user(id), do: user  # Just use case!

# AVOID: Complex else clauses - normalize errors in helpers
with {:ok, a} <- normalize_step1(),
     {:ok, b} <- normalize_step2(a) do
  {:ok, b}
end
# Non-matching tuples pass through unchanged
```

## Assertive Map Access

```elixir
# DON'T: Silent nil for missing required keys
{point[:x], point[:y]}  # Returns {nil, nil} if keys missing!

# DO: Use .key for required keys (raises KeyError if missing)
{point.x, point.y}

# DO: Pattern match
def plot(%{x: x, y: y}), do: {x, y}  # Match fails if keys missing
```

## Rescue Only for External Code

```elixir
# DO: Rescue external library exceptions
def safe_parse(json) do
  {:ok, Jason.decode!(json)}
rescue
  e in Jason.DecodeError -> {:error, e.message}
end

# DON'T: Rescue for control flow or catch all
try do
  risky_operation()
rescue
  _ -> :error  # Never do this - masks programming errors
end
```

## Control Flow Decision Tree

```
Need to match against patterns?
├─ Yes → case
│   └─ Multiple dependent operations? → with
└─ No (boolean conditions)
    ├─ Single condition? → if
    └─ Multiple conditions? → cond
```

| Construct | Use When |
|-----------|----------|
| Function heads | First choice - most idiomatic |
| `case` | Pattern matching single value |
| `cond` | Multiple boolean conditions |
| `with` | Chaining operations returning tagged tuples |
| `if` | Single boolean check |
