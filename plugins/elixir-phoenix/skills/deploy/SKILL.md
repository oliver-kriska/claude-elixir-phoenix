---
name: deploy
description: Elixir/Phoenix deployment patterns - releases, Docker, Kubernetes, Fly.io. Use when editing Dockerfile, fly.toml, config/runtime.exs, or any deployment config. Also use when the user mentions deploying, releases, CI/CD, or production setup.
---

# Elixir/Phoenix Deployment Reference

Quick reference for deploying Elixir/Phoenix applications.

## Iron Laws — Never Violate These

1. **CONFIG AT RUNTIME, NOT COMPILE TIME** — All secrets in `runtime.exs` from env vars
2. **GRACEFUL SHUTDOWN ≥ 60 SECONDS** — Let connections drain
3. **HEALTH CHECKS REQUIRED** — Startup, liveness, readiness endpoints
4. **SSL VERIFICATION FOR DATABASE** — `ssl_opts: [verify: :verify_peer]`
5. **DON'T SET CPU LIMITS** — BEAM scheduler issues with cgroups CPU limits

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
- `references/kubernetes-config.md` - Deployments, probes, BEAM-specific
- `references/flyio-config.md` - fly.toml, clustering, commands
- `references/observability.md` - Telemetry, logging, Sentry, spans
- `references/ci-templates.md` - GitHub Actions workflows, Claude Code integration
