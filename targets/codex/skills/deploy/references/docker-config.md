# Docker Configuration Reference

## Multi-Stage Build

```dockerfile
# Dockerfile
ARG ELIXIR_VERSION=1.18.0
ARG OTP_VERSION=27.0
ARG DEBIAN_VERSION=bookworm-20240130-slim

ARG BUILDER_IMAGE="hexpm/elixir:${ELIXIR_VERSION}-erlang-${OTP_VERSION}-debian-${DEBIAN_VERSION}"
ARG RUNNER_IMAGE="debian:${DEBIAN_VERSION}"

# Build stage
FROM ${BUILDER_IMAGE} as builder

RUN apt-get update -y && apt-get install -y build-essential git \
    && apt-get clean && rm -f /var/lib/apt/lists/*_*

WORKDIR /app

RUN mix local.hex --force && \
    mix local.rebar --force

ENV MIX_ENV=prod

# Dependencies
COPY mix.exs mix.lock ./
RUN mix deps.get --only $MIX_ENV
RUN mkdir config

# Config
COPY config/config.exs config/${MIX_ENV}.exs config/
RUN mix deps.compile

# Assets (esbuild + tailwind, configured in config/config.exs)
COPY priv priv
COPY assets assets
RUN mix assets.deploy

# Application
COPY lib lib
RUN mix compile

# Release
COPY config/runtime.exs config/
COPY rel rel
RUN mix release

# Runner stage
FROM ${RUNNER_IMAGE}

RUN apt-get update -y && \
    apt-get install -y libstdc++6 openssl libncurses6 locales ca-certificates \
    && apt-get clean && rm -f /var/lib/apt/lists/*_*

RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen

ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

WORKDIR /app

RUN chown nobody:nogroup /app

USER nobody:nogroup

COPY --from=builder --chown=nobody:nogroup /app/_build/prod/rel/my_app ./

ENV HOME=/app

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:4000/health/liveness || exit 1

CMD ["bin/my_app", "start"]
```

## Release Configuration

### mix.exs

```elixir
def project do
  [
    releases: [
      my_app: [
        strip_beams: [keep: ["Docs"]],
        include_erts: true,
        config_providers: [],
        steps: [:assemble, :tar]
      ]
    ]
  ]
end
```

### rel/env.sh.eex

```bash
#!/bin/sh

# Clustering setup
export RELEASE_DISTRIBUTION=name
export RELEASE_NODE="${FLY_APP_NAME}@${FLY_PRIVATE_IP:-127.0.0.1}"

# For Fly.io IPv6
export ERL_AFLAGS="-proto_dist inet6_tcp"
```

### rel/vm.args.eex

```
## Performance tuning
+sbwt very_short
+swt very_low

## Increase process limit
+P 1000000

## Enable dirty schedulers
+SDio 16

## Disable kernel poll on containers (can cause issues)
# +K true
```

## Migration in Production

```elixir
# rel/overlays/bin/migrate
#!/bin/sh
cd -P -- "$(dirname -- "$0")"
exec ./my_app eval MyApp.Release.migrate

# lib/my_app/release.ex
defmodule MyApp.Release do
  @app :my_app

  def migrate do
    load_app()

    for repo <- repos() do
      {:ok, _, _} = Ecto.Migrator.with_repo(repo, &Ecto.Migrator.run(&1, :up, all: true))
    end
  end

  def rollback(repo, version) do
    load_app()
    {:ok, _, _} = Ecto.Migrator.with_repo(repo, &Ecto.Migrator.run(&1, :down, to: version))
  end

  defp repos, do: Application.fetch_env!(@app, :ecto_repos)
  defp load_app, do: Application.load(@app)
end
```
