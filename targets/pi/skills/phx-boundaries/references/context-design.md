# Context Design Principles

Guidelines for designing and maintaining Phoenix context boundaries.

## Context Responsibilities

### What Belongs in a Context

- Business logic and domain rules
- Data access (Repo calls)
- Schema ownership
- Changeset definitions
- Transaction coordination
- PubSub broadcasting

### What Does NOT Belong in a Context

- HTTP concerns (conn, params parsing)
- Presentation logic
- View helpers
- WebSocket handling
- External API clients (use separate modules)

## Context API Design

### Public Functions

```elixir
defmodule MyApp.Accounts do
  @moduledoc """
  The Accounts context handles user management and authentication.
  """

  # List operations
  def list_users(opts \\ [])
  def list_active_users

  # Get operations (return nil or raise)
  def get_user(id)
  def get_user!(id)
  def get_user_by_email(email)

  # Create operations
  def create_user(attrs)
  def register_user(attrs)

  # Update operations
  def update_user(user, attrs)
  def change_user_email(user, attrs)

  # Delete operations
  def delete_user(user)

  # Changeset functions (for forms)
  def change_user(user, attrs \\ %{})
end
```

### Function Naming Conventions

| Prefix | Meaning | Returns |
|--------|---------|---------|
| `list_` | Collection | `[%Schema{}]` |
| `get_` | Single item, may not exist | `%Schema{} \| nil` |
| `get_!` | Single item, must exist | `%Schema{}` or raises |
| `create_` | New record | `{:ok, %Schema{}} \| {:error, changeset}` |
| `update_` | Modify record | `{:ok, %Schema{}} \| {:error, changeset}` |
| `delete_` | Remove record | `{:ok, %Schema{}} \| {:error, changeset}` |
| `change_` | Return changeset | `%Changeset{}` |

## Cross-Context Communication

### Option 1: Direct Function Calls

For simple, synchronous operations:

```elixir
defmodule MyApp.Orders do
  alias MyApp.Accounts

  def create_order(user_id, attrs) do
    user = Accounts.get_user!(user_id)
    # ... create order
  end
end
```

### Option 2: PubSub for Decoupling

For events that trigger side effects:

```elixir
# In Orders context
defmodule MyApp.Orders do
  def complete_order(order) do
    with {:ok, order} <- update_order(order, %{status: :completed}) do
      Phoenix.PubSub.broadcast(MyApp.PubSub, "orders", {:order_completed, order})
      {:ok, order}
    end
  end
end

# In Notifications context (subscriber)
defmodule MyApp.Notifications do
  def handle_info({:order_completed, order}, state) do
    send_order_confirmation(order)
    {:noreply, state}
  end
end
```

### Option 3: Domain Events

For complex workflows:

```elixir
defmodule MyApp.Events do
  def dispatch(%{type: :order_completed} = event) do
    MyApp.Notifications.handle(event)
    MyApp.Analytics.handle(event)
    MyApp.Inventory.handle(event)
  end
end
```

## Context Boundaries Checklist

### When Creating New Context

- [ ] Single responsibility (one bounded context)
- [ ] Clear API surface (public functions documented)
- [ ] Owns its schemas (no shared schemas)
- [ ] No web layer dependencies
- [ ] Tests don't require web layer

### When Adding Cross-Context Dependency

- [ ] Dependency is intentional (not accidental)
- [ ] Using public API (not internal functions)
- [ ] No circular dependencies created
- [ ] Consider if PubSub is better fit

## Anti-Patterns to Avoid

### Bloated Contexts

```elixir
# BAD: One context doing too much
defmodule MyApp.Core do
  def create_user(attrs)
  def create_order(attrs)
  def create_product(attrs)
  def send_email(to, subject, body)
  def process_payment(amount)
end

# GOOD: Separate concerns
defmodule MyApp.Accounts do ... end
defmodule MyApp.Orders do ... end
defmodule MyApp.Catalog do ... end
defmodule MyApp.Mailer do ... end
defmodule MyApp.Payments do ... end
```

### Leaky Abstractions

```elixir
# BAD: Exposing internal query
def get_active_users_query do
  from u in User, where: u.active == true
end

# GOOD: Return data, not queries
def list_active_users do
  from(u in User, where: u.active == true)
  |> Repo.all()
end
```

### Schema Sharing

```elixir
# BAD: Sharing schemas between contexts
defmodule MyApp.Orders do
  alias MyApp.Accounts.User  # Cross-context schema access

  def create_order(%User{} = user, attrs) do
    # Tight coupling
  end
end

# GOOD: Use IDs, call context API
defmodule MyApp.Orders do
  alias MyApp.Accounts

  def create_order(user_id, attrs) do
    user = Accounts.get_user!(user_id)
    # Create order with user data
  end
end
```
