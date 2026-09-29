# Elixir/Phoenix (`phx`)

Plan, build, review and debug Elixir, Phoenix, LiveView, Ecto and Oban code
with Claude Code. The plugin adds a Plan → Work → Review → Compound workflow,
26 specialist agents, 51 skills, and hooks that enforce the Elixir/Phoenix
Iron Laws (no float money, no unconditional queries in `mount`, idempotent
Oban jobs, and others).

Full documentation: <https://phxagents.dev> · Source and issues:
<https://github.com/oliver-kriska/claude-elixir-phoenix>

## Install

```text
/plugin marketplace add oliver-kriska/claude-elixir-phoenix
/plugin install elixir-phoenix
```

The `ecto` and `lv` dependency plugins install with it and provide the
`/ecto:*` and `/lv:*` commands.

## Start here

- `/phx:intro` — a short tour of the commands
- `/phx:plan <feature>` then `/phx:work` — plan and implement a feature
- `/phx:review` — review changes with parallel specialist agents
- `/phx:investigate` — find the root cause of a bug
- `/phx:help` — which command fits a task

## What it runs on your machine

- **Hooks** act only in projects with a `mix.exs`, on failed `mix` commands,
  or on plans the plugin created. The exception is the force-push guard, which
  runs everywhere. They check formatting with `mix format --check-formatted`,
  flag Iron Law violations and debug statements, and block destructive
  commands such as `mix ecto.reset` or `git push --force`. No hook runs
  `git fetch` or uses your credentials.
- **Network**: at session start a hook probes `localhost:4000` for a running
  Tidewave server. `/phx:deps-audit` reads package metadata from `hex.pm`.
  `/phx:pr-review`, `/phx:watch-pr` and `/phx:deps-update` call GitHub through
  your own `gh` login, and `/phx:codex-loop` / `--codex` run your own `codex`
  CLI. The plugin stores no credentials and sends no telemetry.
- **Files**: plans, reviews and solution notes go to your project's `.claude/`
  directory. `/phx:init` adds rules to `CLAUDE.md` (and `AGENTS.md` if you
  ask) only when you run it. Hooks keep small counters in `/tmp` and in the
  plugin's own data directory.

## Requirements

An Elixir project, and `jq`, which the hooks use to read Claude Code events.
Tidewave MCP, `gh` and `codex` are optional.

## License

MIT
