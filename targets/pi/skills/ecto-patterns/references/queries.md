# Queries Reference

## Composable Query Functions

```elixir
defmodule MyApp.Posts.PostQuery do
  import Ecto.Query

  def base, do: from(p in Post, as: :post)

  def published(query \\ base()) do
    from p in query, where: not is_nil(p.published_at)
  end

  def by_author(query \\ base(), author_id) do
    from p in query, where: p.author_id == ^author_id
  end

  def recent(query \\ base(), days \\ 7) do
    cutoff = Date.add(Date.utc_today(), -days)
    from p in query, where: p.inserted_at >= ^cutoff
  end

  def ordered(query \\ base(), direction \\ :desc) do
    from p in query, order_by: [{^direction, p.inserted_at}]
  end
end

# Usage: Pipeline composition
PostQuery.base()
|> PostQuery.published()
|> PostQuery.by_author(author_id)
|> PostQuery.ordered()
|> Repo.all()
```

## Dynamic Queries

```elixir
def filter_where(params) do
  Enum.reduce(params, dynamic(true), fn
    {"author", value}, dynamic ->
      dynamic([p], ^dynamic and p.author == ^value)

    {"category", value}, dynamic ->
      dynamic([p], ^dynamic and p.category == ^value)

    {"title_contains", value}, dynamic ->
      dynamic([p], ^dynamic and ilike(p.title, ^"%#{value}%"))

    {_, _}, dynamic ->
      dynamic  # Ignore unknown params
  end)
end

# Usage
def list_posts(params) do
  Post
  |> where(^filter_where(params))
  |> Repo.all()
end
```

## Subqueries

```elixir
# Correlated subquery with parent_as
comment_count = from c in Comment,
  where: parent_as(:post).id == c.post_id,
  select: count()

from p in Post, as: :post,
  select: %{title: p.title, comment_count: subquery(comment_count)}
```

## Window Functions

```elixir
from p in Post,
  select: %{
    id: p.id,
    title: p.title,
    row_num: row_number() |> over(partition_by: p.category_id, order_by: p.inserted_at),
    rank: rank() |> over(partition_by: p.category_id, order_by: [desc: p.view_count])
  }
```

## JSONB Queries (Ecto 3.12+)

### json_extract_path/2

Extract values from JSONB columns without raw SQL:

```elixir
# Extract nested JSON value
from u in User,
  where: json_extract_path(u.settings, ["notifications", "email"]) == true,
  select: json_extract_path(u.metadata, ["theme"])

# Compare with older fragment approach (still works but verbose)
from u in User,
  where: fragment("?->>'email' = ?", u.settings["notifications"], "true")
```

### JSONB Pattern: Filtering on Nested Keys

```elixir
# Dynamic key extraction
def by_metadata_key(query, key, value) do
  from u in query,
    where: json_extract_path(u.metadata, ^[key]) == ^value
end

# Array access in JSONB
from p in Product,
  where: json_extract_path(p.attributes, ["tags", 0]) == "featured"
```

### JSONB Anti-patterns

```elixir
# WRONG: Loading all rows then filtering in Elixir
Repo.all(User)
|> Enum.filter(fn u -> u.settings["notifications"]["email"] == true end)

# RIGHT: Filter in database
from u in User,
  where: json_extract_path(u.settings, ["notifications", "email"]) == true

# TIP: For frequently queried JSONB paths, create expression index
# In migration:
# execute "CREATE INDEX users_settings_notifications_idx ON users ((settings->'notifications'))"
```

## Repo.reload Options (Ecto 3.12+)

```elixir
# Basic reload (unchanged)
user = Repo.reload!(user)

# With preloads (new in 3.12)
user = Repo.reload!(user, preload: [:posts, :comments])

# Force fresh query (skip query cache)
user = Repo.reload!(user, force: true)
```

## Full-Text Search

For PostgreSQL full-text search patterns, see `references/fulltext-search.md`.

## Preload Strategies

```elixir
# Separate queries (default) - BEST for has_many
# Two queries: posts + comments
Repo.preload(post, :comments)

# Join (single query) - BEST for belongs_to/has_one
# One query with JOIN - watch for row multiplication with has_many!
from(p in Post, preload: [:author])

# Custom query for filtered/ordered preloads
Repo.preload(post, comments: from(c in Comment, order_by: c.inserted_at, limit: 10))
```

## Pagination

```elixir
def list_posts(params \\ %{}) do
  page = Map.get(params, :page, 1)
  per_page = Map.get(params, :per_page, 20)

  from(p in Post,
    order_by: [desc: p.inserted_at],
    offset: ^((page - 1) * per_page),
    limit: ^per_page
  )
  |> Repo.all()
end
```

## Anti-patterns

```elixir
# WRONG: N+1 queries
users = Repo.all(User)
Enum.map(users, fn u -> u.posts end)  # N queries!

# RIGHT: Preload
users = Repo.all(User) |> Repo.preload(:posts)

# WRONG: Getting all then filtering in Elixir
Repo.all(User) |> Enum.filter(& &1.active)

# RIGHT: Filter in query
from(u in User, where: u.active) |> Repo.all()

# WRONG: String interpolation (SQL injection!)
from(u in User, where: fragment("name = '#{name}'"))

# RIGHT: Parameterized queries
from(u in User, where: u.name == ^name)

# WRONG: Using Repo.get! with user input (may raise)
Repo.get!(User, user_provided_id)

# RIGHT: Handle not found
case Repo.get(User, id) do
  nil -> {:error, :not_found}
  user -> {:ok, user}
end
```
