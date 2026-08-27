# Pattern Matching Reference

## Function Heads (Preferred)

```elixir
def process(%{status: :active} = user), do: activate(user)
def process(%{status: :inactive} = user), do: deactivate(user)
def process(_user), do: {:error, :unknown_status}
```

## Pin Operator

Match against existing values:

```elixir
expected = :ok
^expected = get_result()  # Only matches if returns :ok

# Essential for dynamic map keys
key = :user_id
%{^key => value} = data
```

## is_non_struct_map/1 Guard (Elixir 1.17+)

Structs ARE maps, so `is_map/1` matches both:

```elixir
# DO: Distinguish plain maps from structs
def process(data) when is_non_struct_map(data), do: handle_map(data)
def process(%User{} = user), do: handle_user(user)

# DON'T: This matches structs too!
def process(%{} = data), do: handle_data(data)  # Matches User struct!
```

## Custom Guards

```elixir
defguard is_positive_integer(n) when is_integer(n) and n > 0

def process(n) when is_positive_integer(n), do: n * 2
```

## Binary Pattern Matching

```elixir
# UTF-8 prefix matching
"hello " <> rest = "hello world"  # rest = "world"

# Protocol parsing
<<header::8, length::32-big, payload::binary-size(length), rest::binary>> = data

# ANTI-PATTERN: Small sub-binary keeps large parent alive
<<small::binary-size(100), _::binary>> = one_gb_binary
# DO: Copy if keeping only the small part
small = :binary.copy(small)
```

## Guards: Allowed Operations

Guards must be pure, deterministic:

- Type checks: `is_atom/1`, `is_binary/1`, `is_integer/1`, `is_list/1`, `is_map/1`
- Comparisons: `==`, `!=`, `<`, `>`, `<=`, `>=`
- Arithmetic: `+`, `-`, `*`, `/`, `abs/1`, `div/2`, `rem/2`
- Value access: `hd/1`, `tl/1`, `elem/2`, `tuple_size/1`, `map_size/1`, `length/1`

**CRITICAL**: Guards use `and`/`or`/`not`, never short-circuit operators (they require boolean operands)

```elixir
# CORRECT
def process(n) when is_integer(n) and n > 0, do: n * 2

# WRONG - compile error
def process(n) when is_integer(n) && n > 0, do: n * 2
```
