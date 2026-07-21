# Authorization Patterns Reference

## Bodyguard (Recommended)

```elixir
# In context module
defmodule MyApp.Blog do
  @behaviour Bodyguard.Policy

  # Policy callbacks
  def authorize(:view_post, _user, %Post{published: true}), do: :ok
  def authorize(:view_post, %User{id: id}, %Post{user_id: id}), do: :ok
  def authorize(:update_post, %User{id: id}, %Post{user_id: id}), do: :ok
  def authorize(:delete_post, %User{role: :admin}, _post), do: :ok
  def authorize(_, _, _), do: {:error, :unauthorized}

  # Usage in context functions
  def update_post(user, post, attrs) do
    with :ok <- Bodyguard.permit(__MODULE__, :update_post, user, post) do
      post
      |> Post.changeset(attrs)
      |> Repo.update()
    end
  end
end
```

## Scope-Based Queries

```elixir
# Ensure users only see their own data
def list_posts(%Scope{user: user}) do
  from(p in Post, where: p.user_id == ^user.id)
  |> Repo.all()
end
```

## LiveView Authorization

```elixir
# on_mount hook for authentication
def on_mount(:require_authenticated, _params, session, socket) do
  case session["user_token"] do
    nil ->
      {:halt, socket |> put_flash(:error, "Login required") |> redirect(to: ~p"/login")}
    token ->
      user = Accounts.get_user_by_session_token(token)
      {:cont, assign(socket, :current_user, user)}
  end
end

# RE-AUTHORIZE IN EVERY EVENT HANDLER
def handle_event("delete", %{"id" => id}, socket) do
  post = Blog.get_post!(id)

  # Don't trust that mount authorized this action!
  with :ok <- Bodyguard.permit(Blog, :delete_post, socket.assigns.current_user, post) do
    Blog.delete_post(post)
    {:noreply, stream_delete(socket, :posts, post)}
  else
    _ -> {:noreply, put_flash(socket, :error, "Unauthorized")}
  end
end
```

## Anti-patterns

```elixir
# ❌ Authorization only in mount (socket state can be stale)
def mount(_params, _session, socket) do
  if authorized?(socket.assigns.user), do: {:ok, socket}
end
# User then calls handle_event without re-checking!

# ✅ Re-authorize in every event handler
def handle_event("action", params, socket) do
  with :ok <- authorize(socket.assigns.current_user, :action, resource) do
    # ... perform action
  end
end
```
