# Routing Patterns Reference

## Verified Routes (~p sigil) - Phoenix 1.7+

```elixir
# ALWAYS use verified routes
~p"/posts/#{@post}"
~p"/search?#{%{q: user_input}}"  # Auto URL-encoded

# DON'T use path helpers (deprecated)
Routes.post_path(conn, :show, post)
```

## Pipeline Design

```elixir
pipeline :browser do
  plug :accepts, ["html"]
  plug :fetch_session
  plug :fetch_live_flash
  plug :put_root_layout, html: {MyAppWeb.Layouts, :root}
  plug :protect_from_forgery
  plug :put_secure_browser_headers
  plug :fetch_current_user
  plug :fetch_current_scope
end

pipeline :api do
  plug :accepts, ["json"]
  plug :fetch_current_scope_for_api_user
end

scope "/", MyAppWeb do
  pipe_through [:browser, :require_authenticated_user]
  live "/dashboard", DashboardLive
end
```

## Anti-patterns (DON'T DO THESE)

### Rails/Ruby Patterns (Not Phoenix)

```elixir
# WRONG: Service objects
defmodule MyApp.Services.UserCreationService do
  def call(params), do: ...
end

# WRONG: Concerns
defmodule MyApp.Concerns.Authenticatable do
  # Rails ActiveSupport::Concern pattern
end

# WRONG: Decorators/Presenters
defmodule MyApp.Decorators.UserDecorator do
  def full_name(user), do: ...
end

# WRONG: Interactors/Commands
defmodule MyApp.Interactors.CreateUser do
  def call(params), do: ...
end

# RIGHT: Context functions
defmodule MyApp.Accounts do
  def create_user(scope, params), do: ...
  def authenticate_user(email, password), do: ...
end

# RIGHT: View functions for presentation
defmodule MyAppWeb.UserHTML do
  def full_name(user), do: "#{user.first_name} #{user.last_name}"
end
```

### Repository Pattern (Don't)

Repo IS the repository. Don't wrap it.

### God Context (Don't)

Split when > 400 lines or when domains are distinct.

### Schema Callbacks with Side Effects (Don't)

Ecto removed callbacks intentionally. Use Ecto.Multi.

### Reaching Across Contexts (Don't)

```elixir
# WRONG
def create_order(user_id, params) do
  user = Repo.get!(User, user_id)  # Bypassing Accounts context!
end

# RIGHT
def create_order(%Scope{} = scope, user_id, params) do
  with {:ok, user} <- Accounts.get_user(scope, user_id),
       {:ok, order} <- do_create_order(scope, user, params) do
    {:ok, order}
  end
end
```

### Direct Repo Calls in Controllers/LiveViews (Don't)

```elixir
# WRONG: Business logic in controller
def show(conn, %{"id" => id}) do
  user = Repo.get!(User, id) |> Repo.preload(:posts)
  render(conn, :show, user: user)
end

# RIGHT: Delegate to context
def show(conn, %{"id" => id}) do
  user = Accounts.get_user_with_posts!(conn.assigns.current_scope, id)
  render(conn, :show, user: user)
end
```
