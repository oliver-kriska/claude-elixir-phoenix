# Changesets Reference

## cast vs put_change vs force_change

| Function | Use When |
|----------|----------|
| `cast/4` | External data (user input, API) |
| `put_change/3` | Internal trusted data (timestamps, computed) |
| `change/2` | Internal data from existing struct |
| `force_change/3` | When you need to set even if value unchanged |

```elixir
# External data - use cast
def registration_changeset(user, attrs) do
  user
  |> cast(attrs, [:email, :password, :name])
  |> validate_required([:email, :password, :name])
  |> validate_email()
  |> hash_password()
end

# Internal data - use put_change
defp hash_password(changeset) do
  case changeset do
    %{valid?: true, changes: %{password: password}} ->
      put_change(changeset, :hashed_password, Bcrypt.hash_pwd_salt(password))
    _ ->
      changeset
  end
end
```

## Multiple Changesets per Schema

```elixir
# Different changesets for different operations
def registration_changeset(user, attrs) do
  user
  |> cast(attrs, [:email, :password, :name])
  |> validate_required([:email, :password, :name])
  |> validate_email()
  |> validate_length(:password, min: 12, max: 72)
  |> hash_password()
end

def profile_changeset(user, attrs) do
  user
  |> cast(attrs, [:name, :bio, :avatar])
  |> validate_length(:bio, max: 500)
end

def password_changeset(user, attrs) do
  user
  |> cast(attrs, [:password])
  |> validate_required([:password])
  |> validate_length(:password, min: 12, max: 72)
  |> hash_password()
end

def admin_changeset(user, attrs) do
  user
  |> cast(attrs, [:role, :permissions])
  |> validate_inclusion(:role, [:user, :moderator, :admin])
end
```

## Custom Validations

```elixir
def changeset(order, attrs) do
  order
  |> cast(attrs, [:quantity, :unit_price])
  |> validate_required([:quantity, :unit_price])
  |> validate_positive_total()
end

defp validate_positive_total(changeset) do
  validate_change(changeset, :quantity, fn :quantity, quantity ->
    unit_price = get_field(changeset, :unit_price) || 0

    if quantity * unit_price < 0 do
      [quantity: "total must be positive"]
    else
      []
    end
  end)
end
```

## prepare_changes for Transaction-Safe Operations

```elixir
def changeset(post, attrs) do
  post
  |> cast(attrs, [:title, :body, :published_at])
  |> prepare_changes(fn changeset ->
    # Runs inside the transaction
    if get_change(changeset, :published_at) do
      changeset.repo.update_all(
        from(p in Post, where: p.author_id == ^post.author_id),
        inc: [post_count: 1]
      )
    end
    changeset
  end)
end
```

## Embedded Schemas

**Use embedded_schema when:**

- Never query child independently
- Never share child across parents
- Always loaded with parent (single query)

```elixir
# Embedded schema (stored as JSONB)
defmodule MyApp.Accounts.Profile do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key false
  embedded_schema do
    field :dark_mode, :boolean, default: false
    field :timezone, :string
    field :language, :string, default: "en"
  end

  def changeset(profile, attrs) do
    profile
    |> cast(attrs, [:dark_mode, :timezone, :language])
  end
end

# Parent schema
defmodule MyApp.Accounts.User do
  schema "users" do
    field :email, :string
    embeds_one :profile, Profile, on_replace: :update
    embeds_many :addresses, Address, on_replace: :delete
  end

  def changeset(user, attrs) do
    user
    |> cast(attrs, [:email])
    |> cast_embed(:profile)
    |> cast_embed(:addresses)
  end
end
```

Migration:

```elixir
add :profile, :map
add :addresses, :map, default: "[]"
```

## Field Types

| Need | Ecto Type | PostgreSQL | Notes |
|------|-----------|------------|-------|
| Primary key | `:binary_id` | `uuid` | Prefer UUIDs |
| Text | `:string` | `varchar` | Default |
| Long text | `:text` | `text` | No limit |
| Integer | `:integer` | `integer` | |
| Money | `:integer` | `integer` | Store cents (never float!) |
| Decimal | `:decimal` | `numeric` | Precise calculations |
| Boolean | `:boolean` | `boolean` | |
| Date | `:date` | `date` | |
| DateTime | `:utc_datetime_usec` | `timestamptz` | With timezone + microseconds |
| JSON | `:map` | `jsonb` | Use for dynamic |
| Enum | `Ecto.Enum` | `varchar` | Type-safe |
| Array | `{:array, :string}` | `varchar[]` | |
