# Rate Limiting Patterns

## Composite Key Strategy

Rate limit on multiple dimensions to prevent abuse while allowing legitimate use:

```elixir
defmodule MyApp.RateLimit do
  @moduledoc """
  Rate limiting with composite keys for different abuse scenarios.
  """

  # Magic link: limit by IP AND email hash (prevent enumeration)
  def check_magic_link(ip, email) do
    email_hash = :crypto.hash(:sha256, email) |> Base.encode16()

    with :ok <- check("magic_link:ip:#{ip}", 10, :timer.minutes(15)),
         :ok <- check("magic_link:email:#{email_hash}", 3, :timer.hours(1)) do
      :ok
    end
  end

  # API: limit by user AND global IP
  def check_api(user_id, ip) do
    with :ok <- check("api:user:#{user_id}", 100, :timer.minutes(1)),
         :ok <- check("api:ip:#{ip}", 1000, :timer.minutes(1)) do
      :ok
    end
  end

  # AI tokens: separate call limit from token limit
  def check_ai_generation(user_id, estimated_tokens) do
    with :ok <- check("ai:calls:#{user_id}", 50, :timer.hours(1)),
         :ok <- check_tokens("ai:tokens:#{user_id}", estimated_tokens, 100_000, :timer.hours(24)) do
      :ok
    end
  end

  defp check(key, limit, window) do
    case Hammer.check_rate(key, window, limit) do
      {:allow, _count} -> :ok
      {:deny, retry_after} -> {:error, {:rate_limited, retry_after}}
    end
  end

  defp check_tokens(key, tokens, limit, window) do
    case Hammer.check_rate_inc(key, window, limit, tokens) do
      {:allow, _count} -> :ok
      {:deny, retry_after} -> {:error, {:token_limit, retry_after}}
    end
  end
end
```

## Plug-Based Rate Limiting

```elixir
defmodule MyAppWeb.Plugs.RateLimiter do
  import Plug.Conn

  def init(opts), do: opts

  def call(conn, opts) do
    key = build_key(conn, opts)
    limit = Keyword.get(opts, :limit, 60)
    window = Keyword.get(opts, :window, :timer.minutes(1))

    case Hammer.check_rate(key, window, limit) do
      {:allow, count} ->
        conn
        |> put_resp_header("x-ratelimit-limit", to_string(limit))
        |> put_resp_header("x-ratelimit-remaining", to_string(limit - count))

      {:deny, retry_after} ->
        conn
        |> put_resp_header("retry-after", to_string(div(retry_after, 1000)))
        |> send_resp(429, "Rate limit exceeded")
        |> halt()
    end
  end

  defp build_key(conn, opts) do
    base = Keyword.get(opts, :key, "default")
    ip = get_ip(conn)

    case Keyword.get(opts, :by) do
      :ip -> "#{base}:ip:#{ip}"
      :user -> "#{base}:user:#{conn.assigns[:current_user].id}"
      :user_or_ip -> "#{base}:#{user_or_ip_key(conn)}"
      _ -> "#{base}:ip:#{ip}"
    end
  end

  defp user_or_ip_key(conn) do
    case conn.assigns[:current_user] do
      nil -> "ip:#{get_ip(conn)}"
      user -> "user:#{user.id}"
    end
  end

  defp get_ip(conn) do
    conn.remote_ip |> :inet.ntoa() |> to_string()
  end
end
```

## Router Usage

```elixir
pipeline :rate_limited_api do
  plug MyAppWeb.Plugs.RateLimiter,
    key: "api",
    limit: 100,
    window: :timer.minutes(1),
    by: :user_or_ip
end

pipeline :strict_rate_limit do
  plug MyAppWeb.Plugs.RateLimiter,
    key: "auth",
    limit: 5,
    window: :timer.minutes(15),
    by: :ip
end

scope "/api", MyAppWeb do
  pipe_through [:api, :rate_limited_api]

  resources "/posts", PostController
end

scope "/auth", MyAppWeb do
  pipe_through [:browser, :strict_rate_limit]

  post "/magic-link", AuthController, :send_magic_link
end
```

## Context-Level Rate Limiting

```elixir
defmodule MyApp.Accounts do
  alias MyApp.RateLimit

  def send_magic_link(email, ip) do
    with :ok <- RateLimit.check_magic_link(ip, email),
         {:ok, user} <- get_user_by_email(email),
         {:ok, token} <- generate_magic_link_token(user) do
      deliver_magic_link(user, token)
    end
  end

  def login_with_password(email, password, ip) do
    # Rate limit by IP for failed attempts
    with :ok <- RateLimit.check("login:ip:#{ip}", 10, :timer.minutes(15)) do
      case get_user_by_email_and_password(email, password) do
        {:ok, user} ->
          # Reset rate limit on success
          Hammer.delete_buckets("login:ip:#{ip}")
          {:ok, user}

        {:error, :invalid_credentials} ->
          {:error, :invalid_credentials}
      end
    end
  end
end
```

## Strategies by Use Case

| Use Case | Key Strategy | Limit | Window |
|----------|-------------|-------|--------|
| Login attempts | IP | 10 | 15 min |
| Magic link | IP + email hash | 3/email, 10/IP | 1h/15m |
| Password reset | IP + email hash | 3/email | 1 hour |
| API (authenticated) | User ID | 1000 | 1 min |
| API (public) | IP | 100 | 1 min |
| AI generation | User (calls + tokens) | 50 calls, 100k tokens | 1h/24h |
| File upload | User | 10 | 1 hour |
| Email sending | User | 100 | 24 hours |

## PlugAttack Alternative

```elixir
defmodule MyAppWeb.PlugAttack do
  use PlugAttack

  rule "allow local", conn do
    allow conn.remote_ip == {127, 0, 0, 1}
  end

  rule "throttle by ip", conn do
    throttle conn.remote_ip,
      period: 60_000,
      limit: 100,
      storage: {PlugAttack.Storage.Ets, MyApp.PlugAttack.Storage}
  end

  rule "throttle authenticated more generously", conn do
    if user = conn.assigns[:current_user] do
      throttle {:user, user.id},
        period: 60_000,
        limit: 1000,
        storage: {PlugAttack.Storage.Ets, MyApp.PlugAttack.Storage}
    end
  end
end
```

## Testing Rate Limits

```elixir
defmodule MyApp.RateLimitTest do
  use MyApp.DataCase

  setup do
    # Clear rate limit buckets before each test
    on_exit(fn ->
      Hammer.delete_buckets("test:*")
    end)
  end

  test "blocks after limit exceeded" do
    ip = "127.0.0.1"

    # First 10 should pass
    for _ <- 1..10 do
      assert :ok = RateLimit.check("test:ip:#{ip}", 10, :timer.minutes(1))
    end

    # 11th should fail
    assert {:error, {:rate_limited, _}} =
             RateLimit.check("test:ip:#{ip}", 10, :timer.minutes(1))
  end
end
```

## Configuration

```elixir
# config/config.exs
config :hammer,
  backend: {Hammer.Backend.ETS, [
    expiry_ms: :timer.hours(1),
    cleanup_interval_ms: :timer.minutes(10)
  ]}

# For distributed systems, use Redis backend
# config/prod.exs
config :hammer,
  backend: {Hammer.Backend.Redis, [
    expiry_ms: :timer.hours(1),
    redix_config: [host: "redis", port: 6379]
  ]}
```
