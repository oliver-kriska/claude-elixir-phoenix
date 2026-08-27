# Refactoring Boundary Violations

Step-by-step guide to fixing common Phoenix context boundary issues.

## Fixing Direct Repo Access in Controllers

### Before (Violation)

```elixir
defmodule MyAppWeb.UserController do
  alias MyApp.Repo
  alias MyApp.Accounts.User

  def show(conn, %{"id" => id}) do
    user = Repo.get!(User, id)  # Direct Repo access!
    render(conn, :show, user: user)
  end
end
```

### After (Fixed)

```elixir
# In context
defmodule MyApp.Accounts do
  def get_user!(id), do: Repo.get!(User, id)
end

# In controller
defmodule MyAppWeb.UserController do
  alias MyApp.Accounts

  def show(conn, %{"id" => id}) do
    user = Accounts.get_user!(id)
    render(conn, :show, user: user)
  end
end
```

## Fixing Business Logic in LiveView

### Before (Violation)

```elixir
defmodule MyAppWeb.OrderLive do
  def handle_event("complete", %{"id" => id}, socket) do
    order = Repo.get!(Order, id)

    # Business logic in LiveView!
    Ecto.Multi.new()
    |> Ecto.Multi.update(:order, Order.changeset(order, %{status: :completed}))
    |> Ecto.Multi.insert(:notification, Notification.changeset(%{...}))
    |> Repo.transaction()

    {:noreply, socket}
  end
end
```

### After (Fixed)

```elixir
# In context
defmodule MyApp.Orders do
  def complete_order(order) do
    Ecto.Multi.new()
    |> Ecto.Multi.update(:order, Order.changeset(order, %{status: :completed}))
    |> Ecto.Multi.run(:notification, fn repo, _ ->
      MyApp.Notifications.create_order_notification(order)
    end)
    |> Repo.transaction()
  end
end

# In LiveView
defmodule MyAppWeb.OrderLive do
  alias MyApp.Orders

  def handle_event("complete", %{"id" => id}, socket) do
    order = Orders.get_order!(id)

    case Orders.complete_order(order) do
      {:ok, _} -> {:noreply, put_flash(socket, :info, "Order completed")}
      {:error, _} -> {:noreply, put_flash(socket, :error, "Failed")}
    end
  end
end
```

## Fixing Schema with Queries

### Before (Violation)

```elixir
defmodule MyApp.Accounts.User do
  use Ecto.Schema
  import Ecto.Query  # Violation!

  schema "users" do
    field :email, :string
  end

  def active_query do
    from u in __MODULE__, where: u.active == true
  end
end
```

### After (Fixed)

```elixir
# Schema is pure
defmodule MyApp.Accounts.User do
  use Ecto.Schema

  schema "users" do
    field :email, :string
    field :active, :boolean
  end

  def changeset(user, attrs) do
    user
    |> cast(attrs, [:email, :active])
    |> validate_required([:email])
  end
end

# Queries in context
defmodule MyApp.Accounts do
  import Ecto.Query

  def list_active_users do
    from(u in User, where: u.active == true)
    |> Repo.all()
  end
end
```

## Fixing Cross-Context Schema Access

### Before (Violation)

```elixir
defmodule MyApp.Orders do
  alias MyApp.Accounts.User  # Tight coupling!
  alias MyApp.Orders.Order

  def create_order(%User{id: user_id, email: email}, attrs) do
    %Order{}
    |> Order.changeset(Map.put(attrs, :user_id, user_id))
    |> Repo.insert()
    |> tap(fn {:ok, _} -> send_confirmation(email) end)
  end
end
```

### After (Fixed)

```elixir
defmodule MyApp.Orders do
  alias MyApp.Accounts
  alias MyApp.Orders.Order

  def create_order(user_id, attrs) when is_integer(user_id) do
    # Fetch needed data through context API
    user = Accounts.get_user!(user_id)

    %Order{}
    |> Order.changeset(Map.put(attrs, :user_id, user_id))
    |> Repo.insert()
    |> tap(fn {:ok, _} -> send_confirmation(user.email) end)
  end
end
```

## Migration Strategy

### Step 1: Identify Violations

```bash
# Find Repo access in web layer
grep -r "Repo\." lib/my_app_web/ --include="*.ex"

# Find cross-context aliases
grep -r "alias MyApp\.\w\+\.\w\+" lib/my_app/ --include="*.ex"

# Find import Ecto.Query in schemas
grep -r "import Ecto.Query" lib/my_app/**/schemas/ --include="*.ex"
```

### Step 2: Create Context Functions

For each violation, create appropriate context function:

| Violation | Solution |
|-----------|----------|
| `Repo.get(Schema, id)` | `Context.get_schema(id)` |
| `Repo.all(Schema)` | `Context.list_schemas()` |
| `Repo.insert(changeset)` | `Context.create_schema(attrs)` |
| `Ecto.Multi` in controller | `Context.complex_operation(...)` |

### Step 3: Update Callers

Replace direct calls with context API calls.

### Step 4: Verify with xref

```bash
# After refactoring, verify no web -> Repo dependencies
mix xref graph --source lib/my_app_web/ --sink MyApp.Repo

# Should return empty or only through contexts
```

## Incremental Refactoring Tips

1. **Don't refactor everything at once** - Fix one boundary at a time
2. **Add tests first** - Ensure behavior is preserved
3. **Use deprecation warnings** - Mark old functions as deprecated before removing
4. **Keep commits atomic** - One boundary fix per commit
