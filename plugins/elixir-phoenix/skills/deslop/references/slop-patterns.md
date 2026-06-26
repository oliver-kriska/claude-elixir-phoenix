# Elixir AI Slop Patterns

Detailed detection patterns for each category of AI-generated code slop.

## Dead Code Patterns

### Orphaned handle_event clauses

AI generates handle_event for buttons that were later removed from templates:

```elixir
# SLOP: button was removed from template but handler remains
def handle_event("old_filter", _params, socket) do
  # ... filtering logic for removed UI element
end
```

**Detection**: Grep for `handle_event` names, cross-reference with `phx-click`
and `phx-submit` in templates/components.

### Unused private functions

AI generates helper functions during iteration, then rewrites the caller
to not need them:

```elixir
# SLOP: was used in v1, caller was rewritten in v2
defp format_phone_number(phone) do
  # ... formatting logic no longer called
end
```

**Detection**: `mix xref unreachable` catches most. For private functions,
check `_build/` compilation warnings for "unused function" warnings.

## Duplication Patterns

### Mirror changesets

AI copies create_changeset to make update_changeset with minimal changes:

```elixir
# SLOP: identical validation logic duplicated
def create_changeset(user, attrs) do
  user
  |> cast(attrs, [:name, :email, :role])
  |> validate_required([:name, :email])
  |> validate_format(:email, ~r/@/)
  |> unique_constraint(:email)
end

def update_changeset(user, attrs) do
  user
  |> cast(attrs, [:name, :email, :role])  # same fields
  |> validate_required([:name, :email])    # same validations
  |> validate_format(:email, ~r/@/)        # same format
  |> unique_constraint(:email)             # same constraint
end
```

**Fix**: Extract shared validation into `changeset/2`, call from both.

### Copied context functions

AI duplicates query logic across contexts:

```elixir
# In Accounts context
def list_active_users, do: from(u in User, where: u.active == true) |> Repo.all()

# In Admin context — SLOP: same query duplicated
def list_active_users, do: from(u in User, where: u.active == true) |> Repo.all()
```

**Fix**: One canonical function in the owning context, other contexts call it.

## Needless Abstraction Patterns

### Single-caller wrappers

```elixir
# SLOP: UserHelpers.get_user/1 called from exactly one place
defmodule MyApp.UserHelpers do
  def get_user(id), do: MyApp.Repo.get(MyApp.Accounts.User, id)
end
```

**Fix**: Delete the wrapper, use `Repo.get(User, id)` directly.

### Unnecessary GenServer

```elixir
# SLOP: GenServer that wraps a single ETS table lookup
defmodule MyApp.Cache do
  use GenServer
  def get(key), do: GenServer.call(__MODULE__, {:get, key})
  def handle_call({:get, key}, _from, state), do: {:reply, Map.get(state, key), state}
end
```

**Fix**: If no concurrent access or state mutation needed, use a plain module
with ETS or even a simple map in the caller's assigns.

## Boundary Violations

### Repo calls in LiveView

```elixir
# SLOP: bypasses context layer
def handle_event("delete", %{"id" => id}, socket) do
  MyApp.Repo.get!(Post, id) |> MyApp.Repo.delete()  # Should go through context
end
```

**Fix**: `Posts.delete_post(id)` — delegate to context.

### Direct schema access from controllers

```elixir
# SLOP: controller knows about schema internals
def index(conn, _params) do
  users = from(u in User, where: u.role == "admin") |> Repo.all()
end
```

**Fix**: `Accounts.list_admins()` — context owns the query.
