# Channels and Presence Reference

## When to Use Channels vs LiveView

| Need | Use |
|------|-----|
| Interactive UI, server-rendered HTML | LiveView |
| Custom binary protocol, gaming | Channels |
| Mobile/desktop native client | Channels |
| Bidirectional data sync (no HTML) | Channels |
| Online user tracking | Presence (with either) |

**Default to LiveView** for web apps. Use Channels when you need
non-HTML communication or native client support.

## Channel Architecture

### Topic Routing

```elixir
# In UserSocket
channel "room:*", MyAppWeb.RoomChannel
channel "notifications:*", MyAppWeb.NotificationChannel
```

Topics use `"topic:subtopic"` convention with wildcard matching.

### Core Callbacks

```elixir
defmodule MyAppWeb.RoomChannel do
  use MyAppWeb, :channel

  # Authorization on join
  def join("room:lobby", _message, socket) do
    {:ok, socket}
  end

  def join("room:" <> _private, _params, _socket) do
    {:error, %{reason: "unauthorized"}}
  end

  # Handle incoming events
  def handle_in("new_msg", %{"body" => body}, socket) do
    broadcast!(socket, "new_msg", %{body: body})
    {:noreply, socket}
  end

  # Intercept outgoing (per-client filtering)
  intercept ["user_joined"]

  def handle_out("user_joined", msg, socket) do
    if ignoring_user?(socket.assigns[:user], msg.user_id) do
      {:noreply, socket}
    else
      push(socket, "user_joined", msg)
      {:noreply, socket}
    end
  end
end
```

### Token Authentication

```elixir
# 1. Endpoint config
socket "/socket", MyAppWeb.UserSocket,
  websocket: true,
  longpoll: false,
  auth_token: true

# 2. Generate token (in conn pipeline)
token = Phoenix.Token.sign(conn, "user socket", user.id)
assign(conn, :user_token, token)

# 3. Verify in Socket.connect/3
def connect(_params, socket, connect_info) do
  case Phoenix.Token.verify(
    socket, "user socket",
    connect_info[:auth_token],
    max_age: 1_209_600  # 2 weeks
  ) do
    {:ok, user_id} ->
      {:ok, assign(socket, :current_user, user_id)}
    {:error, _reason} ->
      :error
  end
end
```

### Client-Side Patterns

```javascript
// Connect
let socket = new Socket("/socket", {authToken: window.userToken})
socket.connect()

// Join channel
let channel = socket.channel("room:lobby", {})
channel.join()
  .receive("ok", resp => console.log("Joined", resp))
  .receive("error", resp => console.log("Failed", resp))

// Send events
channel.push("new_msg", {body: "hello"})

// Receive events
channel.on("new_msg", payload => {
  renderMessage(payload.body)
})
```

## Presence

Track online users with CRDT-based conflict resolution.

### Setup

```elixir
# lib/my_app_web/channels/presence.ex
defmodule MyAppWeb.Presence do
  use Phoenix.Presence,
    otp_app: :my_app,
    pubsub_server: MyApp.PubSub
end
```

### Track Users

```elixir
def join("room:" <> room_id, _params, socket) do
  send(self(), :after_join)
  {:ok, socket}
end

def handle_info(:after_join, socket) do
  {:ok, _} = Presence.track(socket, socket.assigns.user_id, %{
    online_at: inspect(System.system_time(:second)),
    typing: false
  })

  push(socket, "presence_state", Presence.list(socket))
  {:noreply, socket}
end
```

### Update Presence Metadata

```elixir
def handle_in("typing", %{"typing" => typing}, socket) do
  {:ok, _} = Presence.update(socket, socket.assigns.user_id, fn meta ->
    Map.put(meta, :typing, typing)
  end)
  {:noreply, socket}
end
```

### Client-Side Presence

```javascript
import {Presence} from "phoenix"

let presences = {}

channel.on("presence_state", state => {
  presences = Presence.syncState(presences, state)
  renderOnlineUsers(presences)
})

channel.on("presence_diff", diff => {
  presences = Presence.syncDiff(presences, diff)
  renderOnlineUsers(presences)
})
```

### Presence with LiveView

```elixir
def mount(_params, _session, socket) do
  if connected?(socket) do
    MyAppWeb.Presence.track(self(), "room:lobby",
      socket.assigns.current_user.id,
      %{joined_at: DateTime.utc_now()})

    Phoenix.PubSub.subscribe(MyApp.PubSub, "room:lobby")
  end

  {:ok, assign(socket, :presences,
    MyAppWeb.Presence.list("room:lobby"))}
end

def handle_info(%Phoenix.Socket.Broadcast{event: "presence_diff",
  payload: diff}, socket) do
  {:noreply, update(socket, :presences, fn presences ->
    presences
    |> MyAppWeb.Presence.merge(diff)
  end)}
end
```

## Reliability Patterns

### Message Delivery

Phoenix Channels provide **at-most-once** delivery. For stronger
guarantees, implement persistence:

```elixir
# Recovery: last-seen ID pattern
def join("rooms:" <> id, params, socket) do
  messages = fetch_messages_since(params["last_seen_id"])
  {:ok, %{messages: messages}, socket}
end
```

### Scaling

- Millions of subscribers per node with reasonable latency
- PubSub handles cluster broadcasts automatically
- One message per additional node for distributed broadcasts

## Anti-patterns

| Wrong | Right |
|-------|-------|
| Channel for HTML UI | Use LiveView |
| No auth in `join/3` | Always verify in join |
| Atom keys in payloads | String keys only |
| No token expiry | Set `max_age` on tokens |
| Sync DB calls in handle_in | Use async Task or Oban |
