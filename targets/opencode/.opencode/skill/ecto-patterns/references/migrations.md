# Migrations Reference

## Basic Migration

```elixir
defmodule MyApp.Repo.Migrations.CreateUsers do
  use Ecto.Migration

  def change do
    create table(:users, primary_key: false) do
      add :id, :binary_id, primary_key: true
      add :email, :string, null: false
      add :name, :string
      add :role, :string, default: "user"

      timestamps(type: :utc_datetime_usec)
    end

    create unique_index(:users, [:email])
  end
end
```

## Add Foreign Key (Safe - 2 steps)

```elixir
# Step 1: Add without validation (fast, no table lock)
def change do
  alter table(:posts) do
    add :user_id, references(:users, type: :binary_id, validate: false), null: false
  end

  create index(:posts, [:user_id])
end

# Step 2: Validate in separate migration (separate deploy)
def change do
  execute "ALTER TABLE posts VALIDATE CONSTRAINT posts_user_id_fkey", ""
end
```

## Add NOT NULL (Safe - 3 steps)

```elixir
# Step 1: Add check constraint without validation
def change do
  create constraint("products", :active_not_null,
    check: "active IS NOT NULL",
    validate: false
  )
end

# Step 2: Backfill data (separate deploy)
def change do
  execute "UPDATE products SET active = false WHERE active IS NULL", ""
end

# Step 3: Validate constraint, add NOT NULL, drop constraint
def change do
  execute "ALTER TABLE products VALIDATE CONSTRAINT active_not_null", ""
  execute "ALTER TABLE products ALTER COLUMN active SET NOT NULL", ""
  drop constraint("products", :active_not_null)
end
```

## Concurrent Index (Large Tables)

```elixir
@disable_ddl_transaction true
@disable_migration_lock true

def change do
  create index(:posts, [:slug], concurrently: true)
end
```

## Batched Data Migration

```elixir
def change do
  # For large tables, process in batches
  execute &migrate_data/0, &rollback_data/0
end

defp migrate_data do
  repo().transaction(fn ->
    from(u in "users", where: is_nil(u.status), select: u.id, limit: 1000)
    |> repo().all()
    |> Enum.each(&update_user_status/1)
  end)
end
```

## Mixed Primary Key Types (bigint + binary_id)

When integrating libraries that use UUID PKs (Sagents, Oban, etc.)
while your project uses bigint:

```elixir
# WRONG: Global @foreign_key_type affects ALL associations
@foreign_key_type :binary_id

# RIGHT: Explicit type ONLY on specific associations
schema "interviews" do
  belongs_to :user, MyApp.Accounts.User        # bigint (default)
  belongs_to :conversation, Agents.Conversation, type: :binary_id
end
```

In migrations, match the referenced table's PK type:

```elixir
alter table(:interviews) do
  add :user_id, references(:users, type: :bigint), null: false
  add :conversation_id, references(:conversations, type: :binary_id)
end
```

## Associations

```elixir
# One-to-many (always specify on_delete!)
has_many :posts, Post, on_delete: :delete_all
belongs_to :user, User

# Many-to-many
many_to_many :tags, Tag, join_through: "post_tags", on_replace: :delete

# Has one through
has_one :organization, through: [:user, :organization]

# Self-referential
belongs_to :parent, __MODULE__
has_many :children, __MODULE__, foreign_key: :parent_id
```

## Optimistic Locking

```elixir
schema "products" do
  field :name, :string
  field :lock_version, :integer, default: 1
end

def changeset(product, attrs) do
  product
  |> cast(attrs, [:name])
  |> optimistic_lock(:lock_version)
end

# Usage - raises Ecto.StaleEntryError if version changed
Repo.update!(changeset)
```
