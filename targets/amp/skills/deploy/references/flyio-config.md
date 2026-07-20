# Fly.io Configuration Reference

## fly.toml

```toml
app = "my-app"
primary_region = "iad"

[build]

[deploy]
  release_command = "/app/bin/migrate"
  strategy = "rolling"

[env]
  PHX_HOST = "my-app.fly.dev"
  PORT = "8080"
  ECTO_IPV6 = "true"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 1

  [http_service.concurrency]
    type = "connections"
    hard_limit = 1000
    soft_limit = 800

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 512

[processes]
  app = "/app/bin/server"
```

## Commands

```bash
# Create app
fly launch

# Set secrets
fly secrets set SECRET_KEY_BASE=$(mix phx.gen.secret)
fly secrets set DATABASE_URL="postgres://..."

# Create Postgres
fly postgres create --name my-app-db
fly postgres attach my-app-db

# Deploy
fly deploy

# SSH into running instance
fly ssh console --pty -C "/app/bin/my_app remote"

# View logs
fly logs

# Scale
fly scale count 3
fly scale vm shared-cpu-2x
```

## Clustering on Fly.io

```elixir
# config/runtime.exs
if System.get_env("FLY_APP_NAME") do
  config :libcluster,
    topologies: [
      fly6pn: [
        strategy: Cluster.Strategy.DNSPoll,
        config: [
          polling_interval: 5_000,
          query: System.get_env("FLY_APP_NAME") <> ".internal",
          node_basename: System.get_env("FLY_APP_NAME")
        ]
      ]
    ]
end
```

## rel/env.sh.eex for Fly.io

```bash
#!/bin/sh

# Clustering setup
export RELEASE_DISTRIBUTION=name
export RELEASE_NODE="${FLY_APP_NAME}@${FLY_PRIVATE_IP:-127.0.0.1}"

# For Fly.io IPv6
export ERL_AFLAGS="-proto_dist inet6_tcp"
```
