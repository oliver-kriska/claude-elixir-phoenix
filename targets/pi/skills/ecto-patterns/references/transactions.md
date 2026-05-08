# Transactions Reference

## Repo.transact (Simpler for most cases)

```elixir
Repo.transact(fn ->
  with {:ok, user} <- create_user(params),
       {:ok, profile} <- create_profile(user) do
    {:ok, user}
  end
end)
```

## Ecto.Multi (Complex operations, testing)

```elixir
alias Ecto.Multi

# Basic Multi
Multi.new()
|> Multi.insert(:user, user_changeset)
|> Multi.insert(:profile, fn %{user: user} ->
  Profile.changeset(%Profile{user_id: user.id}, %{})
end)
|> Multi.run(:welcome_email, fn _repo, %{user: user} ->
  MyApp.Mailer.deliver_welcome(user)
end)
|> Repo.transaction()

# Composition with merge
Multi.new()
|> Multi.insert(:order, order_changeset)
|> Multi.merge(fn %{order: order} ->
  Multi.new()
  |> Multi.insert_all(:items, OrderItem, build_items(order))
end)
|> Repo.transaction()

# Reusable Multi components (default to Multi.new())
def transfer_money(multi \\ Multi.new(), from_id, to_id, amount) do
  multi
  |> Multi.run(:validate, fn _, _ -> validate_accounts(from_id, to_id) end)
  |> Multi.update(:debit, fn _ -> debit_changeset(from_id, amount) end)
  |> Multi.update(:credit, fn _ -> credit_changeset(to_id, amount) end)
end

# Error handling
case Repo.transaction(multi) do
  {:ok, %{user: user, team: team}} ->
    {:ok, user}
  {:error, :user, changeset, _changes} ->
    {:error, :user_creation_failed, changeset}
  {:error, :team, changeset, _changes} ->
    {:error, :team_creation_failed, changeset}
end

# Testing Multi without DB
multi = PasswordManager.reset(account, params)
assert [{:account, {:update, changeset, []}}] = Ecto.Multi.to_list(multi)
```

## Upsert Patterns

```elixir
# Insert or update on conflict
Repo.insert(
  changeset,
  on_conflict: {:replace, [:name, :updated_at]},
  conflict_target: :external_id
)

# Insert or do nothing
Repo.insert(changeset, on_conflict: :nothing, conflict_target: :email)

# Insert all with upsert
Repo.insert_all(
  Post,
  posts,
  on_conflict: {:replace_all_except, [:id, :inserted_at]},
  conflict_target: :external_id
)
```

## Batch Operations

```elixir
# insert_all (fast bulk insert)
Repo.insert_all(Post, posts, returning: [:id])

# update_all (fast bulk update)
from(p in Post, where: p.status == :draft)
|> Repo.update_all(set: [status: :archived, updated_at: DateTime.utc_now()])

# delete_all (fast bulk delete)
from(p in Post, where: p.inserted_at < ^cutoff)
|> Repo.delete_all()
```

## Streaming

```elixir
# For processing large result sets without loading all into memory
Repo.transaction(fn ->
  from(p in Post)
  |> Repo.stream()
  |> Stream.each(&process_post/1)
  |> Stream.run()
end)
```

## Connection Pool Tuning

```elixir
# config/runtime.exs
config :my_app, MyApp.Repo,
  pool_size: String.to_integer(System.get_env("POOL_SIZE") || "10"),
  queue_target: 50,
  queue_interval: 1000
```

Rule of thumb: `pool_size = (CPU cores * 2) + disk spindles`
