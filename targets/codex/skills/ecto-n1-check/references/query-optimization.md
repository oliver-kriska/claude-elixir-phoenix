# Query Optimization Techniques

Strategies for optimizing Ecto queries and eliminating N+1 patterns.

## Batching Queries

### Replace Loop Queries with IN Clause

```elixir
# BAD: N queries
Enum.map(user_ids, fn id -> Repo.get(User, id) end)

# GOOD: Single query
from(u in User, where: u.id in ^user_ids)
|> Repo.all()
```

### Batch Inserts

```elixir
# BAD: N inserts
Enum.each(items, fn item ->
  %Item{}
  |> Item.changeset(item)
  |> Repo.insert()
end)

# GOOD: Single insert
Repo.insert_all(Item, items)
```

### Batch Updates

```elixir
# BAD: N updates
Enum.each(users, fn user ->
  user
  |> User.changeset(%{active: false})
  |> Repo.update()
end)

# GOOD: Single update
from(u in User, where: u.id in ^user_ids)
|> Repo.update_all(set: [active: false])
```

## Query Composition

### Composable Query Functions

```elixir
defmodule MyApp.Queries.UserQueries do
  import Ecto.Query

  def base, do: from(u in User)

  def active(query \\ base()) do
    from u in query, where: u.active == true
  end

  def with_posts(query \\ base()) do
    from u in query, preload: [:posts]
  end

  def recent(query \\ base(), days \\ 30) do
    cutoff = DateTime.utc_now() |> DateTime.add(-days, :day)
    from u in query, where: u.inserted_at > ^cutoff
  end
end

# Usage: Compose queries
UserQueries.base()
|> UserQueries.active()
|> UserQueries.with_posts()
|> UserQueries.recent(7)
|> Repo.all()
```

## Subqueries for Complex Filtering

### EXISTS Subquery

```elixir
# Find users with at least one published post
posts_subquery = from p in Post,
  where: p.user_id == parent_as(:user).id,
  where: p.published == true

from u in User,
  as: :user,
  where: exists(posts_subquery)
|> Repo.all()
```

### Count Subquery

```elixir
# Get users with post counts
post_counts = from p in Post,
  group_by: p.user_id,
  select: %{user_id: p.user_id, count: count(p.id)}

from u in User,
  left_join: pc in subquery(post_counts),
  on: pc.user_id == u.id,
  select: {u, pc.count}
|> Repo.all()
```

## Window Functions

### Ranking Within Groups

```elixir
# Get top post per user
from p in Post,
  windows: [user_window: [partition_by: p.user_id, order_by: [desc: p.likes]]],
  select: %{
    post: p,
    rank: row_number() |> over(:user_window)
  }
|> Repo.all()
|> Enum.filter(fn %{rank: rank} -> rank == 1 end)
```

## Database-Specific Optimizations

### PostgreSQL DISTINCT ON

```elixir
# Latest post per user (PostgreSQL only)
from p in Post,
  distinct: p.user_id,
  order_by: [asc: p.user_id, desc: p.inserted_at]
|> Repo.all()
```

### Index Hints

Ensure indexes exist for:

- Foreign keys (`user_id`, `post_id`)
- Columns in WHERE clauses
- Columns in ORDER BY
- Columns used in joins

```elixir
# Migration
create index(:posts, [:user_id])
create index(:posts, [:published, :inserted_at])
```

## Avoiding Common Pitfalls

### Select Only Needed Fields

```elixir
# BAD: Select all columns when only needing ids
Repo.all(User)
|> Enum.map(& &1.id)

# GOOD: Select only what's needed
from(u in User, select: u.id)
|> Repo.all()
```

### Use Streams for Large Datasets

```elixir
# BAD: Load all into memory
Repo.all(LargeTable)
|> Enum.each(&process/1)

# GOOD: Stream processing
LargeTable
|> Repo.stream()
|> Stream.each(&process/1)
|> Stream.run()
```

### Aggregate in Database

```elixir
# BAD: Count in Elixir
Repo.all(User) |> length()

# GOOD: Count in database
Repo.aggregate(User, :count)
```

## Monitoring Queries

### Telemetry for Query Logging

```elixir
# In application.ex
:telemetry.attach(
  "ecto-query-logger",
  [:my_app, :repo, :query],
  &MyApp.QueryLogger.handle_event/4,
  nil
)

defmodule MyApp.QueryLogger do
  require Logger

  def handle_event(_event, measurements, metadata, _config) do
    if measurements.total_time > 100_000_000 do  # > 100ms
      Logger.warning("Slow query: #{metadata.query}")
    end
  end
end
```
