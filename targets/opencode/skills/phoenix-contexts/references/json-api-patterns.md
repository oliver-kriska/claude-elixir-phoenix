# JSON and API Patterns Reference

## JSON Controller Pattern

```elixir
defmodule MyAppWeb.PostController do
  use MyAppWeb, :controller

  action_fallback MyAppWeb.FallbackController

  def index(conn, _params) do
    posts = Blog.list_posts(conn.assigns.current_scope)
    render(conn, :index, posts: posts)
  end

  def create(conn, %{"post" => post_params}) do
    with {:ok, %Post{} = post} <-
           Blog.create_post(conn.assigns.current_scope, post_params) do
      conn
      |> put_status(:created)
      |> put_resp_header("location", ~p"/api/posts/#{post}")
      |> render(:show, post: post)
    end
  end

  def show(conn, %{"id" => id}) do
    post = Blog.get_post!(conn.assigns.current_scope, id)
    render(conn, :show, post: post)
  end

  def update(conn, %{"id" => id, "post" => post_params}) do
    post = Blog.get_post!(conn.assigns.current_scope, id)

    with {:ok, %Post{} = post} <-
           Blog.update_post(conn.assigns.current_scope, post, post_params) do
      render(conn, :show, post: post)
    end
  end

  def delete(conn, %{"id" => id}) do
    post = Blog.get_post!(conn.assigns.current_scope, id)

    with {:ok, %Post{}} <-
           Blog.delete_post(conn.assigns.current_scope, post) do
      send_resp(conn, :no_content, "")
    end
  end
end
```

## JSON View Pattern

```elixir
defmodule MyAppWeb.PostJSON do
  alias MyApp.Blog.Post

  def index(%{posts: posts}) do
    %{data: for(post <- posts, do: data(post))}
  end

  def show(%{post: post}) do
    %{data: data(post)}
  end

  defp data(%Post{} = post) do
    %{
      id: post.id,
      title: post.title,
      body: post.body,
      inserted_at: post.inserted_at
    }
  end
end
```

## FallbackController

Centralize error handling for `with` chains:

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
```

## ChangesetJSON

```elixir
defmodule MyAppWeb.ChangesetJSON do
  def error(%{changeset: changeset}) do
    %{errors: Ecto.Changeset.traverse_errors(changeset,
      &translate_error/1)}
  end

  defp translate_error({msg, opts}) do
    Regex.replace(~r"%{(\w+)}", msg, fn _, key ->
      opts
      |> Keyword.get(String.to_existing_atom(key), key)
      |> to_string()
    end)
  end
end
```

## API Authentication Pipeline

```elixir
# In router.ex
pipeline :api do
  plug :accepts, ["json"]
  plug :fetch_current_scope_for_api_user
end

scope "/api", MyAppWeb do
  pipe_through :api

  resources "/posts", PostController, except: [:new, :edit]
end
```

### Bearer Token Authentication

```elixir
def fetch_current_scope_for_api_user(conn, _opts) do
  with ["Bearer " <> token] <- get_req_header(conn, "authorization"),
       {:ok, user} <- Accounts.fetch_user_by_api_token(token) do
    assign(conn, :current_scope, Scope.for_user(user))
  else
    _ ->
      conn
      |> put_status(:unauthorized)
      |> put_view(json: MyAppWeb.ErrorJSON)
      |> render(:"401")
      |> halt()
  end
end
```

## Multi-Format Controllers

Serve both HTML and JSON from the same controller:

```elixir
defmodule MyAppWeb.PostController do
  use MyAppWeb, :controller

  plug :put_format, :json when action in [:api_index]

  def index(conn, _params) do
    posts = Blog.list_posts(conn.assigns.current_scope)
    render(conn, :index, posts: posts)
  end

  # Separate view modules: PostHTML and PostJSON
end
```

## API Versioning

```elixir
scope "/api/v1", MyAppWeb.V1 do
  pipe_through :api
  resources "/posts", PostController
end

scope "/api/v2", MyAppWeb.V2 do
  pipe_through :api
  resources "/posts", PostController
end
```

## Anti-patterns

| Wrong | Right |
|-------|-------|
| Render HTML errors for API | Use JSON FallbackController |
| No `action_fallback` | Always set FallbackController |
| Return `Repo.insert` directly | Use `with` chain in controller |
| Include sensitive fields in JSON | Explicit `data/1` function |
| No `Location` header on create | Set `put_resp_header("location", ...)` |
