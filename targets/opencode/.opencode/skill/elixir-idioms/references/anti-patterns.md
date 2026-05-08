# Anti-Patterns Reference

## Memory & Performance

```elixir
# WRONG: length/1 for empty check (O(n))
length(list) == 0

# RIGHT: Pattern match or Enum.empty?
list == []
Enum.empty?(list)

# WRONG: ++ to append (O(n))
list ++ [item]

# RIGHT: Prepend and reverse, or use different structure
[item | list] |> Enum.reverse()

# WRONG: Dynamic atom creation (memory leak - atoms aren't GC'd)
String.to_atom(user_input)

# RIGHT: Explicit mapping or existing atoms
defp status_atom("ok"), do: :ok
defp status_atom("error"), do: :error
# Or: String.to_existing_atom(input)

# WRONG: Sending unnecessary data (copies entire vars between processes)
spawn(fn -> log_ip(conn.remote_ip) end)  # Copies entire conn!
GenServer.cast(pid, {:process, large_struct.id})  # Copies entire struct!

# RIGHT: Extract minimal data before spawning or sending
ip = conn.remote_ip
spawn(fn -> log_ip(ip) end)
id = large_struct.id
GenServer.cast(pid, {:process, id})
```

## Message Handling

```elixir
# WRONG: Selective receive without reference (O(n) mailbox scan)
receive do
  {:response, data} -> data  # Scans entire mailbox
end

# RIGHT: Reference-based (compiler optimizes)
ref = make_ref()
send(server, {self(), ref, :request})
receive do
  {^ref, response} -> response  # Compiler uses receive marker
end
```

## Code Organization

```elixir
# WRONG: String keys internally
%{"name" => value}

# RIGHT: Atom keys internally
%{name: value}

# WRONG: Macro when function works
defmacro sum(a, b), do: quote do: unquote(a) + unquote(b)

# RIGHT: Just use a function
def sum(a, b), do: a + b
```

## OTP Anti-Patterns

```elixir
# ANTI-PATTERN: GenServer for stateless computation
def add(a, b), do: GenServer.call(__MODULE__, {:add, a, b})
def handle_call({:add, a, b}, _from, state), do: {:reply, a + b, state}

# CORRECT: Just use functions
def add(a, b), do: a + b

# ANTI-PATTERN: Single GenServer bottleneck
# All requests serialize through one process

# CORRECT: Use ETS for reads, GenServer for writes
# Or partition into multiple processes
```

## Assertiveness (from official Elixir anti-patterns)

```elixir
# WRONG: Non-assertive map access — nil on missing required key
user[:email]  # Returns nil silently if :email missing

# RIGHT: Assert required keys exist
user.email    # Raises KeyError — fail fast
# Use [:key] ONLY for truly optional keys
config[:timeout] || 5000

# WRONG: Catch-all hides bugs
case fetch_user(id) do
  {:ok, user} -> process(user)
  _ -> :error  # What failed? Why?
end

# RIGHT: Match known cases explicitly
case fetch_user(id) do
  {:ok, user} -> process(user)
  {:error, :not_found} -> {:error, :not_found}
end

# WRONG: Boolean obsession — multiple related booleans
%{is_admin: true, is_editor: false, is_viewer: false}

# RIGHT: Single atom field
%{role: :admin}
# Or enum-like pattern in schema:
# field :role, Ecto.Enum, values: [:admin, :editor, :viewer]
```

## Stream vs Enum

```elixir
# Stream processes lazily—only computes what's needed
1..1_000_000
|> Stream.map(&(&1 * 3))
|> Stream.filter(&(rem(&1, 2) != 0))
|> Enum.take(5)  # Only processes ~5 elements

# Enum processes eagerly—entire collection each step
1..1_000_000
|> Enum.map(&(&1 * 3))      # Creates 1M list
|> Enum.filter(&(rem(&1, 2) != 0))  # Creates another list
|> Enum.take(5)
```

**Use Enum** for small/medium collections, immediate results.
**Use Stream** for large collections, multiple transformations, memory constraints.

## Pipe Operator Misuse

```elixir
# AVOID: Pipe with single step
user |> do_something()  # Just: do_something(user)

# AVOID: Start with function call
String.upcase("hello") |> String.split()  # Start with "hello"

# DO: Use tap/1 for side effects (returns original value)
user
|> validate()
|> tap(&Logger.info("Validated: #{&1.name}"))  # Returns user
|> persist()

# DO: Use then/1 for transformations
user
|> validate()
|> persist()
|> then(&{:ok, &1})  # Transforms to tagged tuple
```

## Binary Handling

```elixir
# ANTI-PATTERN: Small sub-binary keeps large parent alive
<<small::binary-size(100), _::binary>> = one_gb_binary

# DO: Copy if keeping only the small part
small = :binary.copy(small)
```

## Tail Recursion

For tail call optimization, recursive call must be the **last operation**:

```elixir
# Tail recursive (optimized - constant stack)
def sum(list), do: do_sum(list, 0)
defp do_sum([], acc), do: acc
defp do_sum([head | tail], acc), do: do_sum(tail, head + acc)

# Not tail recursive (builds stack - O(n) memory)
def factorial(0), do: 1
def factorial(n), do: n * factorial(n - 1)  # Multiplication after recursion
```

**Rule of thumb**: Use Enum for 95% of cases—cleaner and well-tested.
