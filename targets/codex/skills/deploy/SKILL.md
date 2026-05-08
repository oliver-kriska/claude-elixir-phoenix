---
name: deploy
description: Elixir/Phoenix deployment patterns — Dockerfile, fly.toml, runtime.exs,
  mix release, rel/ overlays. Use when configuring Fly.io, Docker, CI/CD, health checks,
  or production migrations.
metadata:
  effort: medium
  paths:
  - config/runtime.exs
  - Dockerfile
  - fly.toml
  - rel/**/*
---

# Elixir/Phoenix Deployment Reference

Quick reference for deploying Elixir/Phoenix applications.

## Iron Laws — Never Violate These

1. **Config at runtime, not compile time** — Secrets in `config.exs` get baked into the release binary. Use `runtime.exs` with env vars so secrets are resolved at boot
2. **Graceful shutdown ≥ 60 seconds** — Shorter timeouts kill in-flight requests and WebSocket connections mid-operation, causing data loss for users
3. **Health checks required** — Without startup/liveness/readiness endpoints, orchestrators can't distinguish a booting node from a dead one, leading to cascading restarts
4. **SSL verification for database** — Skipping `verify: :verify_peer` allows MITM attacks between your app and database; production data traverses the connection
5. **No CPU limits** — The BEAM scheduler assumes it owns all cores; cgroups CPU limits cause scheduler collapse where the VM thinks it has more cores than it can use, leading to latency spikes

## Quick Configuration

### runtime.exs (Essential)

```elixir
if config_env() == :prod do
  database_url = System.get_env("DATABASE_URL") || raise "DATABASE_URL is required"
  secret_key_base = System.get_env("SECRET_KEY_BASE") || raise "SECRET_KEY_BASE is required"
  host = System.get_env("PHX_HOST") || raise "PHX_HOST is required"

  config :my_app, MyApp.Repo,
    url: database_url,
    pool_size: String.to_integer(System.get_env("POOL_SIZE") || "10"),
    ssl: true,
    ssl_opts: [verify: :verify_peer]

  config :my_app, MyAppWeb.Endpoint,
    url: [host: host, port: 443, scheme: "https"],
    http: [ip: {0, 0, 0, 0}, port: String.to_integer(System.get_env("PORT") || "4000")],
    secret_key_base: secret_key_base,
    server: true
end
```

### Health Check Plug

```elixir
def call(%{path_info: ["health", "readiness"]} = conn, _opts) do
  case Ecto.Adapters.SQL.query(MyApp.Repo, "SELECT 1", []) do
    {:ok, _} -> send_resp(conn, 200, ~s({"status":"ok"})) |> halt()
    {:error, _} -> send_resp(conn, 503, ~s({"status":"error"})) |> halt()
  end
end
```

## Quick Decisions

### Platform Choice

| Need | Use |
|------|-----|
| Simple, managed | Fly.io |
| Enterprise, existing K8s | Kubernetes |
| Custom infrastructure | Docker + your orchestrator |

### Resource Limits

| Resource | Recommendation |
|----------|----------------|
| CPU | **NO LIMITS** (BEAM scheduler issues) |
| Memory | Set limits (256Mi-512Mi typical) |
| Graceful shutdown | ≥ 60 seconds |

## Deployment Checklist

- [ ] All secrets from environment variables in runtime.exs
- [ ] `server: true` in endpoint config
- [ ] SSL verification for database connections
- [ ] Health endpoints: /health/startup, /health/liveness, /health/readiness
- [ ] Graceful shutdown period ≥ 60 seconds
- [ ] No CPU limits (memory limits only)
- [ ] Migrations in deploy process

## Asset Pipeline Notes

Phoenix 1.8 uses esbuild + tailwind (no Node.js required):

- Config in `config/config.exs` under `:esbuild` and `:tailwind`
- `mix assets.deploy` builds for production
- `mix assets.setup` installs binaries on first run
- Custom JS bundlers: configure in `config/config.exs`

## References

For detailed patterns, see:

- `references/docker-config.md` - Multi-stage Dockerfile, best practices
- `references/flyio-config.md` - fly.toml, clustering, commands

## Iron Laws (Inlined)

- **NO unconditional DB queries in mount** — Mount runs twice. Default: `assign_async`. SEO routes: `connected?` + cache-backed disconnected branch (dead-render IS the crawler-indexed HTML)
- **ALWAYS use streams for lists >100 items** — Regular assigns = O(n) memory per user
- **CHECK `connected?/1` before PubSub subscribe** — Prevents double subscriptions
- **NEVER use `:float` for money** — Use `:decimal` or `:integer` (cents)
- **ALWAYS pin values with `^` in queries** — Never interpolate user input
- **SEPARATE QUERIES for `has_many`, JOIN for `belongs_to`** — Avoids row multiplication
- **Jobs MUST be idempotent** — Safe to retry
- **Args use STRING keys, not atoms** — Pattern match `%{"user_id" => id}`
- **NEVER store structs in args** — Store IDs, not `%User{}`
- **NO `String.to_atom` with user input** — Atom exhaustion DoS
- **AUTHORIZE in EVERY LiveView `handle_event`** — Don't trust mount authorization
- **NEVER use `raw/1` with untrusted content** — XSS vulnerability
- **NO process without runtime reason** — Processes model concurrency/state/isolation, NOT code structure
- **SUPERVISE ALL LONG-LIVED PROCESSES** — Never bare `GenServer.start_link`/`Agent.start_link` in production. Use supervision trees
- **NO IMPLICIT CROSS JOINS** — `from(a in A, b in B)` without `on:` creates Cartesian product
- **@external_resource FOR COMPILE-TIME FILES** — Modules reading files at compile time MUST declare `@external_resource`
- **DEDUP BEFORE `cast_assoc` WITH SHARED DATA** — Deduplicate shared child records before building changesets, not inside them
- **CHECK CHANGESET ERRORS BEFORE UI DEBUGGING** — When a form save produces no visible error but no expected side effect, check `{:error, changeset}` first
- **HIDDEN INPUTS FOR ALL REQUIRED EMBEDDED FIELDS** — Every required field in an embedded schema MUST have a `hidden_input` if not directly editable
- **WRAP THIRD-PARTY LIBRARY APIs** — Always facade external dependency APIs behind a project-owned module. Enables swapping libraries without touching callers
- **NEVER use `assign_new` for values refreshed every mount** — `assign_new` skips the function if the key exists. Use `assign/3` for locale, current user, or any value that must be set on every mount
- **VERIFY BEFORE CLAIMING DONE** — Never say "should work" or "this fixes it." Run `mix compile && mix test` and show the result. If you can't verify, explicitly state what remains unverified
