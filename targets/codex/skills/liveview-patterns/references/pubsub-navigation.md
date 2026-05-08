# PubSub and Navigation Reference

## PubSub Pattern

### Context Broadcasting Pattern

```elixir
defmodule MyApp.Chat do
  @topic inspect(__MODULE__)

  def subscribe(room_id) do
    Phoenix.PubSub.subscribe(MyApp.PubSub, "#{@topic}:#{room_id}")
  end

  def create_message(scope, attrs) do
    case Repo.insert(changeset) do
      {:ok, message} = result ->
        Phoenix.PubSub.broadcast(
          MyApp.PubSub,
          "#{@topic}:#{message.room_id}",
          {__MODULE__, :message_created, message}
        )
        result
      error -> error
    end
  end
end
```

### LiveView Subscription Pattern

```elixir
def mount(%{"room_id" => room_id}, _session, socket) do
  if connected?(socket), do: Chat.subscribe(room_id)
  {:ok, stream(socket, :messages, Chat.list_messages(room_id))}
end

def handle_info({Chat, :message_created, message}, socket) do
  {:noreply, stream_insert(socket, :messages, message, at: 0)}
end
```

### Message Design

- Use module-scoped topics: `@topic inspect(__MODULE__)`
- Include entity ID in topic: `"#{@topic}:#{room_id}"`
- Send tuples: `{Module, :event, data}` not maps

## Navigation Decision Tree

```
Same LiveView, different params? → patch / push_patch
Different LiveView, same live_session? → navigate / push_navigate
Different live_session or non-LiveView? → href / redirect
```

| Template | Server | Behavior |
|----------|--------|----------|
| `<.link patch={url}>` | `push_patch` | Same LV, calls handle_params |
| `<.link navigate={url}>` | `push_navigate` | New LV, keeps layout |
| `<.link href={url}>` | `redirect` | Full page reload |

## LiveView Structure

```elixir
defmodule MyAppWeb.UserLive.Index do
  use MyAppWeb, :live_view

  alias MyApp.Accounts

  # ============================================
  # Lifecycle
  # ============================================

  @impl true
  def mount(_params, _session, socket) do
    if connected?(socket) do
      Accounts.subscribe()
    end

    {:ok,
     socket
     |> assign(:page_title, "Users")
     |> stream(:users, Accounts.list_users(socket.assigns.current_scope))}
  end

  @impl true
  def handle_params(params, _url, socket) do
    {:noreply, apply_action(socket, socket.assigns.live_action, params)}
  end

  defp apply_action(socket, :index, _params) do
    assign(socket, :user, nil)
  end

  defp apply_action(socket, :edit, %{"id" => id}) do
    assign(socket, :user, Accounts.get_user!(socket.assigns.current_scope, id))
  end

  # ============================================
  # Events
  # ============================================

  @impl true
  def handle_event("delete", %{"id" => id}, socket) do
    user = Accounts.get_user!(socket.assigns.current_scope, id)
    {:ok, _} = Accounts.delete_user(socket.assigns.current_scope, user)

    {:noreply, stream_delete(socket, :users, user)}
  end

  # ============================================
  # PubSub
  # ============================================

  @impl true
  def handle_info({Accounts, [:user, :created], user}, socket) do
    {:noreply, stream_insert(socket, :users, user, at: 0)}
  end

  def handle_info({Accounts, [:user, :deleted], user}, socket) do
    {:noreply, stream_delete(socket, :users, user)}
  end

  # ============================================
  # Render
  # ============================================

  @impl true
  def render(assigns) do
    ~H"""
    <.header>Users</.header>

    <.table id="users" rows={@streams.users}>
      <:col :let={{_id, user}} label="Name">{user.name}</:col>
      <:action :let={{id, user}}>
        <.link phx-click="delete" phx-value-id={user.id} data-confirm="Sure?">
          Delete
        </.link>
      </:action>
    </.table>
    """
  end
end
```

## Anti-patterns

```elixir
# ❌ PubSub subscribe without connected? check
def mount(_params, _session, socket) do
  Phoenix.PubSub.subscribe(MyApp.PubSub, "topic")  # Double subscribes!
  {:ok, socket}
end

# ✅ Check connected? first
def mount(_params, _session, socket) do
  if connected?(socket), do: Phoenix.PubSub.subscribe(MyApp.PubSub, "topic")
  {:ok, socket}
end

# ❌ Business logic in handle_event
def handle_event("submit", params, socket) do
  # 50 lines of logic here
end

# ✅ Delegate to context
def handle_event("submit", params, socket) do
  case MyContext.do_thing(socket.assigns.current_scope, params) do
    {:ok, result} -> {:noreply, handle_success(socket, result)}
    {:error, reason} -> {:noreply, handle_error(socket, reason)}
  end
end

# ❌ Passing socket to business logic
Accounts.update_user(socket, params)

# ✅ Extract needed data
Accounts.update_user(socket.assigns.current_scope, socket.assigns.user, params)
```
