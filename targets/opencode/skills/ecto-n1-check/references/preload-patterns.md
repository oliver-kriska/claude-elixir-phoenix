# Preload Patterns

Efficient strategies for loading associations in Ecto.

## Basic Preloading

### Single Association

```elixir
# In query
User
|> Repo.all()
|> Repo.preload(:posts)

# In query itself (single query with join)
from u in User,
  preload: [:posts]
|> Repo.all()
```

### Nested Associations

```elixir
# Preload nested: user -> posts -> comments
Repo.preload(user, posts: :comments)

# Multiple levels
Repo.preload(user, posts: [comments: :author])
```

### Multiple Associations

```elixir
# Multiple associations at same level
Repo.preload(user, [:posts, :comments, :profile])

# Mixed nesting
Repo.preload(user, [:profile, posts: :comments])
```

## Advanced Preloading

### Custom Query Preloads

```elixir
# Preload only active posts
active_posts_query = from p in Post, where: p.active == true

user
|> Repo.preload(posts: active_posts_query)
```

### Preload with Ordering

```elixir
ordered_posts = from p in Post, order_by: [desc: p.inserted_at]

user
|> Repo.preload(posts: ordered_posts)
```

### Preload with Limit

```elixir
# Get only latest 5 posts per user
recent_posts = from p in Post,
  order_by: [desc: p.inserted_at],
  limit: 5

users
|> Repo.preload(posts: recent_posts)
```

## Join Preloading

For filtering by associations, use joins:

```elixir
# Find users with published posts (efficient)
from u in User,
  join: p in assoc(u, :posts),
  where: p.published == true,
  preload: [posts: p]
|> Repo.all()
```

## Lateral Join for Top-N per Group

```elixir
# Get top 3 posts per user (PostgreSQL)
from u in User,
  inner_lateral_join: p in subquery(
    from p in Post,
      where: p.user_id == parent_as(:user).id,
      order_by: [desc: p.inserted_at],
      limit: 3
  ),
  as: :user,
  preload: [posts: p]
|> Repo.all()
```

## Context-Level Preloading

Always preload at the context boundary:

```elixir
# In context module
defmodule MyApp.Accounts do
  def get_user_with_posts!(id) do
    User
    |> Repo.get!(id)
    |> Repo.preload(:posts)
  end

  def list_users_with_profiles do
    User
    |> Repo.all()
    |> Repo.preload(:profile)
  end
end
```

## Preload in Pipelines

```elixir
def list_active_users_with_orders do
  User
  |> where([u], u.active == true)
  |> Repo.all()
  |> Repo.preload(orders: :line_items)
end
```

## Anti-Patterns to Avoid

### Preloading in Views

```elixir
# BAD: Preload in template
<%= for post <- Repo.preload(@user, :posts).posts do %>

# GOOD: Preload in controller/LiveView
assigns = %{user: Accounts.get_user_with_posts!(id)}
```

### Preloading Everything

```elixir
# BAD: Over-preloading
Repo.preload(user, [:posts, :comments, :likes, :followers, :following])

# GOOD: Preload only what's needed for the view
Repo.preload(user, [:profile, posts: :comments])
```

### Conditional Preloading

```elixir
# Use preload opts for conditional loading
def get_user(id, opts \\ []) do
  user = Repo.get!(User, id)

  if Keyword.get(opts, :with_posts, false) do
    Repo.preload(user, :posts)
  else
    user
  end
end
```
