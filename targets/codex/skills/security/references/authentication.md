# Authentication Patterns Reference

## phx.gen.auth (Recommended)

```bash
# Generate with Argon2 (recommended over bcrypt)
mix phx.gen.auth Accounts User users --hashing-lib argon2
```

## Timing-Safe Authentication

```elixir
def authenticate(email, password) do
  user = Repo.get_by(User, email: email)

  cond do
    user && Argon2.verify_pass(password, user.hashed_password) ->
      {:ok, user}

    user ->
      # Wrong password - but don't reveal user exists
      {:error, :invalid_credentials}

    true ->
      # No user - timing attack prevention
      Argon2.no_user_verify()
      {:error, :invalid_credentials}
    end
end
```

## Session Configuration

```elixir
# endpoint.ex
plug Plug.Session,
  store: :cookie,
  key: "_my_app_key",
  signing_salt: "RANDOM_SALT",
  http_only: true,
  secure: true,  # HTTPS only
  same_site: "Lax"  # Or "Strict" for more protection
```

## MFA with NimbleTOTP

```elixir
# Generate secret
secret = NimbleTOTP.secret()

# Generate QR code URI
uri = NimbleTOTP.otpauth_uri("MyApp:#{user.email}", secret, issuer: "MyApp")

# Validate code (with replay protection)
NimbleTOTP.valid?(secret, code, since: user.last_totp_at)
```

## Secrets Management

### Runtime Configuration

```elixir
# config/runtime.exs
if config_env() == :prod do
  database_url =
    System.get_env("DATABASE_URL") ||
      raise "DATABASE_URL is required"

  secret_key_base =
    System.get_env("SECRET_KEY_BASE") ||
      raise "SECRET_KEY_BASE is required (run: mix phx.gen.secret)"

  config :my_app, MyApp.Repo,
    url: database_url,
    ssl: true,
    ssl_opts: [verify: :verify_peer]

  config :my_app, MyAppWeb.Endpoint,
    secret_key_base: secret_key_base
end
```

### Sensitive Data Redaction

```elixir
defmodule MyApp.Accounts.User do
  schema "users" do
    field :email, :string
    field :hashed_password, :string, redact: true
    field :password, :string, virtual: true, redact: true
  end
end

# Filter in logs
config :phoenix, :filter_parameters, [
  "password",
  "secret",
  "token",
  "api_key",
  "credit_card"
]

# Derive for Inspect
@derive {Inspect, except: [:password_hash, :api_key]}
```
