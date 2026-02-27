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

## AI Code Generation Anti-Slop

Patterns that produce technically correct but generic, low-quality code.
Avoid these when generating Elixir/Phoenix code:

### Boilerplate Padding

```elixir
# SLOP: Empty moduledocs on every module
defmodule MyApp.Accounts do
  @moduledoc ""
  # ...
end

# BETTER: Only add @moduledoc when there's something meaningful to say
# Omit it entirely for obvious single-purpose modules

# SLOP: Commented-out placeholder code
def create_user(attrs) do
  # TODO: Add validation
  # TODO: Send welcome email
  # TODO: Notify admin
  Repo.insert(changeset)
end

# BETTER: Either implement it or don't mention it
def create_user(attrs) do
  %User{} |> User.changeset(attrs) |> Repo.insert()
end
```

### Over-Abstraction

```elixir
# SLOP: Premature abstraction for one-time use
defmodule MyApp.Helpers.StringUtils do
  def format_name(first, last), do: "#{first} #{last}"
end

# BETTER: Inline it where it's used — three lines beats a module

# SLOP: Unnecessary GenServer wrapping
defmodule MyApp.Calculator do
  use GenServer
  def calculate(x, y), do: GenServer.call(__MODULE__, {:calc, x, y})
  def handle_call({:calc, x, y}, _from, state), do: {:reply, x + y, state}
end

# BETTER: A module function — no state, no concurrency need
defmodule MyApp.Calculator do
  def calculate(x, y), do: x + y
end
```

### Defensive Over-Engineering

```elixir
# SLOP: Redundant error handling for internal code
def get_user!(id) do
  case Repo.get(User, id) do
    nil -> raise "User not found"  # Repo.get! already does this
    user -> user
  end
end

# BETTER: Trust the framework
def get_user!(id), do: Repo.get!(User, id)

# SLOP: Validating what the type system guarantees
def process(%User{} = user) do
  if is_map(user) and Map.has_key?(user, :id) do
    # ...
  end
end

# BETTER: The pattern match already ensures the struct shape
def process(%User{id: id} = user) do
  # ...
end
```

### Uniform Style

```elixir
# SLOP: Everything looks the same — identical structure everywhere
# (every context function: get, list, create, update, delete)
def list_users, do: Repo.all(User)
def get_user(id), do: Repo.get(User, id)
def create_user(attrs), do: %User{} |> User.changeset(attrs) |> Repo.insert()
def update_user(user, attrs), do: user |> User.changeset(attrs) |> Repo.update()
def delete_user(user), do: Repo.delete(user)

# BETTER: Only implement what the domain actually needs
# Not every entity needs full CRUD. A read-only lookup table
# only needs list and get. An append-only audit log only needs create.
```

### Key Principle

Write code that solves the specific problem at hand. Don't generate
scaffolding for hypothetical future needs, add defensive checks for
impossible states, or create abstractions before you have two concrete
uses. Three similar lines of code is better than a premature
abstraction.
