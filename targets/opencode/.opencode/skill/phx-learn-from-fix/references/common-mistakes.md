# Common Mistakes - Reference

> **READ-ONLY**: This file ships with the plugin. Do NOT edit it
> at runtime — changes to cached plugin files are lost on update.
> To capture new lessons, use `/phx:learn-from-fix` which writes to
> project CLAUDE.md or auto-memory.

Common Elixir/Phoenix mistakes and their fixes. Use as reference
when checking if a lesson is already documented.

Format:

- **Mistake**: What went wrong
- **Pattern**: Do NOT [bad] - instead [good]
- **Example**: Code showing before/after

---

## Ecto

### String vs Atom Keys

**Mistake**: Using string keys for internal data, atom keys for external

**Pattern**: Do NOT use `map["key"]` for internal structs - instead use `map.key` or pattern match

**Example**:

```elixir
# Bad - external data pattern on internal struct
user["email"]

# Good - atom access for internal data
user.email
%{email: email} = user
```

### Missing Preload

**Mistake**: Accessing association without preloading

**Pattern**: Do NOT access `record.association` without preload - instead use `Repo.preload/2` or include in query

**Example**:

```elixir
# Bad - causes Ecto.Association.NotLoaded
user = Repo.get!(User, id)
user.posts  # Boom!

# Good - explicit preload
user = Repo.get!(User, id) |> Repo.preload(:posts)
user.posts  # Works
```

---

## LiveView

### Blocking Mount

**Mistake**: Slow operations in mount blocking page render

**Pattern**: Do NOT do slow work in mount - instead use `assign_async` or send self a message

**Example**:

```elixir
# Bad - blocks initial render
def mount(_params, _session, socket) do
  data = SlowAPI.fetch()  # User waits...
  {:ok, assign(socket, data: data)}
end

# Good - non-blocking with assign_async
def mount(_params, _session, socket) do
  {:ok, assign_async(socket, :data, fn -> {:ok, %{data: SlowAPI.fetch()}} end)}
end
```

### Missing render_async in Tests

**Mistake**: Testing assign_async without waiting for async completion

**Pattern**: Do NOT assert on async assigns without `render_async/1` - instead call it after `live/2`

**Example**:

```elixir
# Bad - async not completed yet
{:ok, view, _html} = live(conn, ~p"/dashboard")
assert render(view) =~ "Data"  # Fails!

# Good - wait for async
{:ok, view, _html} = live(conn, ~p"/dashboard")
render_async(view)
assert render(view) =~ "Data"  # Works
```

---

## OTP

### Unnecessary GenServer

**Mistake**: Creating GenServer for stateless computation

**Pattern**: Do NOT use GenServer for code organization - instead use plain modules and functions

**Example**:

```elixir
# Bad - GenServer for stateless work
defmodule MyApp.Calculator do
  use GenServer
  def add(a, b), do: GenServer.call(__MODULE__, {:add, a, b})
  def handle_call({:add, a, b}, _from, state), do: {:reply, a + b, state}
end

# Good - just a function
defmodule MyApp.Calculator do
  def add(a, b), do: a + b
end
```

---

## Testing

### Process.sleep for Timing

**Mistake**: Using Process.sleep to wait for async operations

**Pattern**: Do NOT use `Process.sleep` - instead use `assert_receive` with timeout

**Example**:

```elixir
# Bad - flaky, slow
test "processes message" do
  send_message()
  Process.sleep(100)
  assert processed?()
end

# Good - deterministic
test "processes message" do
  send_message()
  assert_receive {:processed, _}, 1000
end
```

### insert() in Factory Definition

**Mistake**: Using insert() inside factory, creating DB records even on build()

**Pattern**: Do NOT use `insert/1` in factory definitions - instead use `build/1`

**Example**:

```elixir
# Bad - creates user even on build(:post)
def post_factory do
  %Post{author: insert(:user)}
end

# Good - lazy association
def post_factory do
  %Post{author: build(:user)}
end
```

---

## Phoenix

### Business Logic in Controller

**Mistake**: Complex logic in controller actions

**Pattern**: Do NOT put business logic in controllers - instead delegate to context functions

**Example**:

```elixir
# Bad - logic in controller
def create(conn, %{"user" => params}) do
  params = Map.put(params, "role", "member")
  if valid_email?(params["email"]) do
    # 20 more lines...
  end
end

# Good - delegate to context
def create(conn, %{"user" => params}) do
  case Accounts.register_user(params) do
    {:ok, user} -> redirect(conn, to: ~p"/users/#{user}")
    {:error, changeset} -> render(conn, :new, changeset: changeset)
  end
end
```
