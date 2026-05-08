# Security Headers Reference

## Content Security Policy

```elixir
# In endpoint.ex or plug
plug :put_secure_headers

defp put_secure_headers(conn, _opts) do
  nonce = :crypto.strong_rand_bytes(16) |> Base.encode64()

  conn
  |> assign(:csp_nonce, nonce)
  |> put_resp_header("content-security-policy", """
    default-src 'self';
    script-src 'self' 'nonce-#{nonce}';
    style-src 'self' 'nonce-#{nonce}';
    img-src 'self' data:;
    connect-src 'self' wss:;
    frame-ancestors 'self';
  """)
end
```

## CSRF Protection

Phoenix enables CSRF protection by default:

```elixir
# router.ex - browser pipeline
pipeline :browser do
  # ...
  plug :protect_from_forgery
  plug :put_secure_browser_headers
end
```

Forms automatically include token:

```elixir
<.form for={@form} action={~p"/users"}>
  <!-- CSRF token automatically included -->
</.form>
```

## Rate Limiting

```elixir
# Using Hammer
defmodule MyAppWeb.RateLimiter do
  import Plug.Conn

  def rate_limit(conn, opts) do
    key = "#{opts[:prefix]}:#{get_ip(conn)}"
    limit = opts[:limit] || 10
    period = opts[:period] || 60_000

    case Hammer.check_rate(key, period, limit) do
      {:allow, _count} ->
        conn

      {:deny, _limit} ->
        conn
        |> put_status(:too_many_requests)
        |> Phoenix.Controller.json(%{error: "Rate limit exceeded"})
        |> halt()
    end
  end

  defp get_ip(conn) do
    conn.remote_ip |> :inet.ntoa() |> to_string()
  end
end

# Usage in router
plug MyAppWeb.RateLimiter, prefix: "login", limit: 5, period: 60_000
```

## Security Headers

```elixir
plug :put_secure_browser_headers, %{
  "x-frame-options" => "SAMEORIGIN",
  "x-content-type-options" => "nosniff",
  "x-xss-protection" => "1; mode=block",
  "referrer-policy" => "strict-origin-when-cross-origin"
}

# HSTS (if using SSL)
plug Plug.SSL,
  hsts: true,
  expires: 31_536_000,
  preload: true
```

## Security Audit Tools

```bash
# Static analysis
mix sobelow --exit medium

# Dependency audit
mix deps.audit
mix hex.audit

# Add to CI/CD
```

## Security Checklist

- [ ] Argon2/bcrypt for password hashing
- [ ] Timing-safe authentication
- [ ] CSRF protection enabled
- [ ] Scopes for data access
- [ ] Re-authorization in LiveView events
- [ ] Input validation via changesets
- [ ] No string interpolation in queries
- [ ] HTML escaping (no raw with user content)
- [ ] CSP headers configured
- [ ] Secrets in runtime.exs from env vars
- [ ] Rate limiting on sensitive endpoints
- [ ] Security headers set
- [ ] sobelow in CI/CD
- [ ] Dependency audits
