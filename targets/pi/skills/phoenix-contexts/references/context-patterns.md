# Context Patterns Reference

## Full Context Module Pattern

```elixir
defmodule MyApp.Accounts do
  @moduledoc """
  The Accounts context - manages users and authentication.
  """

  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Accounts.{User, Token, Scope}

  @topic inspect(__MODULE__)

  # ============================================
  # PubSub
  # ============================================

  def subscribe do
    Phoenix.PubSub.subscribe(MyApp.PubSub, @topic)
  end

  defp broadcast({:ok, result}, scope, event) do
    Phoenix.PubSub.broadcast(MyApp.PubSub, @topic, {__MODULE__, event, result})
    {:ok, result}
  end

  defp broadcast({:error, _} = error, _scope, _event), do: error

  # ============================================
  # Users
  # ============================================

  def list_users(%Scope{} = scope) do
    from(u in User, where: u.organization_id == ^scope.user.organization_id)
    |> Repo.all()
  end

  def get_user(%Scope{} = scope, id) do
    Repo.get_by(User, id: id, organization_id: scope.user.organization_id)
  end

  def get_user!(%Scope{} = scope, id) do
    Repo.get_by!(User, id: id, organization_id: scope.user.organization_id)
  end

  def create_user(%Scope{} = scope, attrs \\ %{}) do
    %User{organization_id: scope.user.organization_id}
    |> User.registration_changeset(attrs)
    |> Repo.insert()
    |> broadcast(scope, [:user, :created])
  end

  def update_user(%Scope{} = scope, %User{} = user, attrs) do
    user
    |> User.changeset(attrs)
    |> Repo.update()
    |> broadcast(scope, [:user, :updated])
  end

  def delete_user(%Scope{} = _scope, %User{} = user) do
    Repo.delete(user)
  end

  def change_user(%User{} = user, attrs \\ %{}) do
    User.changeset(user, attrs)
  end

  # ============================================
  # Authentication
  # ============================================

  def authenticate_user(email, password) do
    user = Repo.get_by(User, email: email)

    cond do
      user && Bcrypt.verify_pass(password, user.hashed_password) ->
        {:ok, user}

      user ->
        {:error, :invalid_password}

      true ->
        Bcrypt.no_user_verify()  # Timing-safe
        {:error, :not_found}
    end
  end
end
```

## Side Effects with Ecto.Multi

NO side effects in changesets. Use Ecto.Multi:

```elixir
def register_user(%Scope{} = scope, attrs) do
  Ecto.Multi.new()
  |> Ecto.Multi.insert(:user, User.registration_changeset(%User{}, attrs))
  |> Ecto.Multi.run(:welcome_email, fn _repo, %{user: user} ->
    MyApp.Mailer.deliver_welcome(user)
  end)
  |> Ecto.Multi.run(:broadcast, fn _repo, %{user: user} ->
    broadcast({:ok, user}, scope, [:user, :registered])
  end)
  |> Repo.transaction()
end
```

## FallbackController Pattern

For APIs, use FallbackController for consistent error handling:

```elixir
defmodule MyAppWeb.FallbackController do
  use MyAppWeb, :controller

  def call(conn, {:error, %Ecto.Changeset{} = changeset}) do
    conn
    |> put_status(:unprocessable_entity)
    |> put_view(json: MyAppWeb.ChangesetJSON)
    |> render(:error, changeset: changeset)
  end

  def call(conn, {:error, :not_found}) do
    conn
    |> put_status(:not_found)
    |> put_view(json: MyAppWeb.ErrorJSON)
    |> render(:"404")
  end

  def call(conn, {:error, :unauthorized}) do
    conn
    |> put_status(:forbidden)
    |> put_view(json: MyAppWeb.ErrorJSON)
    |> render(:"403")
  end
end

# In controller
defmodule MyAppWeb.PostController do
  use MyAppWeb, :controller

  action_fallback MyAppWeb.FallbackController

  def show(conn, %{"id" => id}) do
    with {:ok, post} <- Blog.fetch_post(conn.assigns.current_scope, id) do
      render(conn, :show, post: post)
    end
  end
end
```

## Cross-Context Boundary Patterns

When contexts have data dependencies, two approaches:

### Option A: API-Driven (Preferred)

Reference other contexts by ID, call their public API:

```elixir
def create_order(%Scope{} = scope, user_id, product_ids) do
  with {:ok, user} <- Accounts.fetch_user(scope, user_id) do
    do_create_order(scope, user.id, product_ids)
  end
end
```

### Option B: DB Joins (When Performance Requires)

Use `belongs_to` for cross-context schema references:

```elixir
# In ShoppingCart.CartItem
schema "cart_items" do
  field :price_when_carted, :decimal
  field :quantity, :integer
  belongs_to :cart, ShoppingCart.Cart
  belongs_to :product, Catalog.Product  # Cross-context ref
  timestamps(type: :utc_datetime)
end
```

### Upsert for Cross-Context Operations

```elixir
def add_item_to_cart(%Scope{} = scope, %Cart{} = cart, product_id) do
  true = cart.user_id == scope.user.id  # Scope enforcement!
  product = Catalog.get_product!(product_id)

  %CartItem{quantity: 1, price_when_carted: product.price}
  |> CartItem.changeset(%{})
  |> Ecto.Changeset.put_assoc(:cart, cart)
  |> Ecto.Changeset.put_assoc(:product, product)
  |> Repo.insert(
    on_conflict: [inc: [quantity: 1]],
    conflict_target: [:cart_id, :product_id]
  )
end
```

### Cross-Context Preloading

```elixir
def get_cart(%Scope{} = scope) do
  Repo.one(
    from(c in Cart,
      where: c.user_id == ^scope.user.id,
      left_join: i in assoc(c, :items),
      left_join: p in assoc(i, :product),
      order_by: [asc: i.inserted_at],
      preload: [items: {i, product: p}]
    )
  )
end
```

### Database Integrity at Boundaries

Use cascade delete for cross-context FK constraints:

```elixir
add :cart_id, references(:carts, on_delete: :delete_all)
add :product_id, references(:products, on_delete: :delete_all)
```

Keep data integrity in the database, not application code.

## Subcontext Pattern (for large contexts)

```elixir
# lib/accounts/subcontexts/users.ex (internal)
defmodule MyApp.Accounts.Users do
  @moduledoc false
  def list_users(scope), do: Repo.all(scoped_query(User, scope))
end

# lib/accounts.ex (public API)
defmodule MyApp.Accounts do
  defdelegate list_users(scope), to: MyApp.Accounts.Users
end
```
