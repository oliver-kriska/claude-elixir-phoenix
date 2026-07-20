# Plug Patterns Reference

## Plug Types

### Function Plug

Accept `conn` + `opts`, return `conn`. Defined in the module
where used:

```elixir
plug :authenticate

defp authenticate(conn, _opts) do
  if conn.assigns[:current_user] do
    conn
  else
    conn
    |> put_flash(:error, "Must log in")
    |> redirect(to: ~p"/login")
    |> halt()
  end
end
```

**CRITICAL**: Always call `halt()` after redirect in auth plugs.
Without halt, downstream plugs still execute.

### Module Plug

Implement `init/1` (compile-time) and `call/2` (runtime):

```elixir
defmodule MyAppWeb.Plugs.Locale do
  import Plug.Conn

  @default_locale "en"

  def init(opts), do: Keyword.get(opts, :default, @default_locale)

  def call(conn, default_locale) do
    locale = conn.params["locale"] || default_locale
    assign(conn, :locale, locale)
  end
end

# Usage in router pipeline
plug MyAppWeb.Plugs.Locale, default: "en"
```

**Optimization**: `init/1` runs at compile time. Put expensive
setup there, not in `call/2`.

## Plug Placement

| Location | Scope | Example |
|----------|-------|---------|
| Endpoint | Every request | Static files, session, parsers |
| Router pipeline | Route group | Auth, API token validation |
| Controller | Action-specific | Resource loading, authorization |

### Controller-Level Plug Guards

```elixir
defmodule MyAppWeb.PostController do
  use MyAppWeb, :controller

  # Only for specific actions
  plug :fetch_post when action in [:show, :edit, :update, :delete]
  plug :authorize when action in [:edit, :update, :delete]

  defp fetch_post(conn, _opts) do
    post = Blog.get_post!(conn.assigns.current_scope, conn.params["id"])
    assign(conn, :post, post)
  end

  defp authorize(conn, _opts) do
    if conn.assigns.post.user_id == conn.assigns.current_scope.user.id do
      conn
    else
      conn |> put_flash(:error, "Unauthorized") |> redirect(to: ~p"/") |> halt()
    end
  end
end
```

## Endpoint Plug Order

Default endpoint plugs run in this order:

```elixir
# 1. Static assets (before anything else)
plug Plug.Static, at: "/", from: :my_app

# 2. Request metadata
plug Plug.RequestId
plug Plug.Telemetry, event_prefix: [:phoenix, :endpoint]

# 3. Body parsing
plug Plug.Parsers,
  parsers: [:urlencoded, :multipart, :json],
  pass: ["*/*"],
  json_decoder: Phoenix.json_library()

# 4. HTTP method override (for PUT/PATCH/DELETE from forms)
plug Plug.MethodOverride

# 5. Content negotiation
plug Plug.Head

# 6. Session
plug Plug.Session, @session_options

# 7. Router (last)
plug MyAppWeb.Router
```

## Common Plug Patterns

### Rate Limiting Plug

```elixir
defmodule MyAppWeb.Plugs.RateLimit do
  import Plug.Conn

  def init(opts), do: opts

  def call(conn, opts) do
    key = rate_limit_key(conn, opts)
    limit = Keyword.get(opts, :limit, 60)
    window = Keyword.get(opts, :window_ms, 60_000)

    case MyApp.RateLimit.check(key, limit, window) do
      :ok -> conn
      :rate_limited ->
        conn
        |> put_resp_header("retry-after", "60")
        |> send_resp(429, "Too Many Requests")
        |> halt()
    end
  end

  defp rate_limit_key(conn, opts) do
    case Keyword.get(opts, :by, :ip) do
      :ip -> "rate:#{:inet.ntoa(conn.remote_ip)}"
      :user -> "rate:user:#{conn.assigns[:current_user]&.id}"
    end
  end
end
```

### CORS Plug

```elixir
# Use CORSPlug with explicit origins (never wildcard in prod)
plug CORSPlug, origin: [
  "https://app.example.com",
  "https://admin.example.com"
]
```

## Anti-patterns

| Wrong | Right |
|-------|-------|
| No `halt()` after redirect | Always `halt()` after redirect |
| Expensive work in `init/1` DB calls | `init/1` for config only, DB in `call/2` |
| Auth in endpoint (runs for static) | Auth in router pipeline |
| All plugs in endpoint | Split by pipeline scope |
