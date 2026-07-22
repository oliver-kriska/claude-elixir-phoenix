# Advanced Security Patterns

Extends core security skill with SSRF prevention, secrets management, and supply chain security.

## Contents

- [SSRF Prevention](#ssrf-prevention-server-side-request-forgery)
- [Secrets Management](#secrets-management)
- [Supply Chain Security](#supply-chain-security)
- [Extended Security Checklist](#extended-security-checklist)
- [CORS Configuration](#cors-configuration)
- [Safe Deserialization](#safe-deserialization)
- [File Upload Content-Type Validation](#file-upload-content-type-validation)

## SSRF Prevention (Server-Side Request Forgery)

### The Risk

User-controlled URLs can access internal services:

```elixir
# VULNERABLE
def fetch_url(url) do
  HTTPoison.get(url)  # User passes http://169.254.169.254/metadata
end
```

### Prevention Patterns

#### URL Allowlist

```elixir
@allowed_hosts ["api.example.com", "cdn.example.com"]

def fetch_url(url) do
  uri = URI.parse(url)

  if uri.host in @allowed_hosts do
    HTTPoison.get(url)
  else
    {:error, :host_not_allowed}
  end
end
```

#### Block Internal IPs

```elixir
defmodule MyApp.Security.SSRF do
  @blocked_ranges [
    # Loopback
    {127, 0, 0, 0..255},
    # Private networks
    {10, 0..255, 0..255, 0..255},
    {172, 16..31, 0..255, 0..255},
    {192, 168, 0..255, 0..255},
    # Link-local
    {169, 254, 0..255, 0..255},
    # AWS/cloud metadata
    {169, 254, 169, 254}
  ]

  def safe_url?(url) do
    uri = URI.parse(url)

    with {:ok, ip} <- resolve_host(uri.host),
         false <- internal_ip?(ip) do
      true
    else
      _ -> false
    end
  end

  defp resolve_host(host) do
    case :inet.gethostbyname(String.to_charlist(host)) do
      {:ok, {:hostent, _, _, _, _, [ip | _]}} -> {:ok, ip}
      _ -> {:error, :resolve_failed}
    end
  end

  defp internal_ip?({a, b, c, d}) do
    Enum.any?(@blocked_ranges, fn {ra, rb, rc, rd} ->
      matches?(a, ra) && matches?(b, rb) && matches?(c, rc) && matches?(d, rd)
    end)
  end

  defp matches?(val, range) when is_integer(range), do: val == range
  defp matches?(val, min..max), do: val >= min && val <= max
end
```

#### Webhook Validation

```elixir
def register_webhook(url) do
  with true <- MyApp.Security.SSRF.safe_url?(url),
       {:ok, %{status_code: 200}} <- HTTPoison.head(url, [], timeout: 5000) do
    {:ok, url}
  else
    _ -> {:error, :invalid_webhook_url}
  end
end
```

## Secrets Management

### Environment Variables (Basic)

```elixir
# config/runtime.exs
config :my_app,
  api_key: System.fetch_env!("API_KEY"),
  db_password: System.fetch_env!("DATABASE_PASSWORD")
```

### Vault Integration

```elixir
defmodule MyApp.Secrets do
  def get(key) do
    vault = Vault.new(
      host: System.get_env("VAULT_ADDR"),
      token: System.get_env("VAULT_TOKEN")
    )

    case Vault.read(vault, "secret/data/my_app") do
      {:ok, %{"data" => %{"data" => secrets}}} ->
        Map.get(secrets, key)
      _ ->
        nil
    end
  end
end
```

### Secrets in Code Detection

```elixir
# BAD - Hardcoded secrets
api_key = "sk_live_abc123"  # NEVER!

# BAD - Committed .env
# .env should be in .gitignore

# GOOD - Runtime only
api_key = System.fetch_env!("API_KEY")
```

### Audit Script

```bash
# Find potential hardcoded secrets
grep -rn "sk_live\|sk_test\|api_key.*=" lib/ config/ --include="*.ex" --include="*.exs"
grep -rn "password.*=" lib/ config/ --include="*.ex" --include="*.exs"
grep -rn "secret.*=" lib/ config/ --include="*.ex" --include="*.exs"
```

### Secrets Rotation Pattern

```elixir
defmodule MyApp.Secrets.Rotator do
  use GenServer

  @refresh_interval :timer.hours(1)

  def start_link(_) do
    GenServer.start_link(__MODULE__, %{}, name: __MODULE__)
  end

  def get(key) do
    GenServer.call(__MODULE__, {:get, key})
  end

  def init(_) do
    secrets = fetch_secrets()
    schedule_refresh()
    {:ok, %{secrets: secrets}}
  end

  def handle_call({:get, key}, _from, state) do
    {:reply, Map.get(state.secrets, key), state}
  end

  def handle_info(:refresh, state) do
    secrets = fetch_secrets()
    schedule_refresh()
    {:noreply, %{state | secrets: secrets}}
  end

  defp fetch_secrets do
    # Fetch from Vault/AWS Secrets Manager/etc.
  end

  defp schedule_refresh do
    Process.send_after(self(), :refresh, @refresh_interval)
  end
end
```

## Supply Chain Security

### Dependency Auditing

```bash
# Check for known vulnerabilities
mix deps.audit

# Check for retired packages
mix hex.audit

# Both in CI
mix deps.audit && mix hex.audit || exit 1
```

### Lock File Verification

```bash
# Verify mix.lock matches mix.exs
mix deps.get --check-locked
```

### Dependency Review Checklist

Before adding new dependency:

- [ ] Check hex.pm download count (popularity)
- [ ] Check GitHub stars/activity
- [ ] Check last commit date
- [ ] Check open security issues
- [ ] Review permissions/capabilities needed
- [ ] Check transitive dependencies

```elixir
# Check what a dep brings in
mix deps.tree --only prod | grep new_dep
```

### Minimal Dependencies

```elixir
# Prefer standard library
# BAD - unnecessary dep
{:timex, "~> 3.0"}  # Just for date formatting?

# GOOD - use built-in
DateTime.to_string(datetime)
Calendar.strftime(datetime, "%Y-%m-%d")
```

## Extended Security Checklist

Add to security review:

### SSRF

- [ ] User-controlled URLs validated
- [ ] Internal IPs blocked
- [ ] DNS rebinding considered
- [ ] Webhook URLs verified

### Secrets

- [ ] No hardcoded secrets in code
- [ ] Secrets loaded at runtime only
- [ ] .env in .gitignore
- [ ] Rotation mechanism for long-lived secrets

### Supply Chain

- [ ] `mix deps.audit` clean
- [ ] `mix hex.audit` clean
- [ ] Lock file committed
- [ ] New deps reviewed

### CORS

- [ ] Origins explicitly allowlisted (never `~r/^http.*/`)
- [ ] Credentials mode requires specific origins
- [ ] Preflight caching configured

### Additional Vectors

- [ ] XML parsing: external entities disabled (XXE)
- [ ] File paths: sanitized (path traversal)
- [ ] Serialization: no `:erlang.binary_to_term` with user data
- [ ] Use `Plug.Crypto.non_executable_binary_to_term/1` instead
- [ ] Rate limiting on expensive operations
- [ ] File uploads: validate content-type, not just extension
- [ ] State-changing GET requests: never (CSRF bypass)

## CORS Configuration

```elixir
# SAFE: Explicit origin allowlist
plug CORSPlug, origin: [
  "https://app.example.com",
  "https://admin.example.com"
]

# VULNERABLE: Overly broad regex
# plug CORSPlug, origin: ~r/^https?:\/\/.*example\.com/
# Matches: https://evil-example.com (attacker domain!)
```

## Safe Deserialization

```elixir
# VULNERABLE: arbitrary term execution
:erlang.binary_to_term(user_data)

# SAFE: non-executable binary_to_term
Plug.Crypto.non_executable_binary_to_term(user_data)
```

## File Upload Content-Type Validation

```elixir
# Validate BOTH extension and magic bytes
def validate_image(upload) do
  case File.read(upload.path) do
    {:ok, <<0xFF, 0xD8, 0xFF, _::binary>>} -> :jpg
    {:ok, <<0x89, 0x50, 0x4E, 0x47, _::binary>>} -> :png
    _ -> {:error, :invalid_content_type}
  end
end
```

Without content-type validation, attackers can upload HTML files
with `.jpg` extension that execute XSS when served.
