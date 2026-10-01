# Elixir/Phoenix: LiveView

Keeps the `/lv:*` commands of the
[Elixir/Phoenix plugin](https://phxagents.dev) working. It is installed with
that plugin as a dependency, and does nothing on its own: each command hands
off to the matching `/phx:` skill.

| Command | Runs |
|---|---|
| `/lv:assigns` | `/phx:assigns-audit` — audit a LiveView's assigns for memory use |

This plugin has no hooks, agents, MCP servers or network access of its own.
Questions and bugs: [GitHub issues](https://github.com/oliver-kriska/claude-elixir-phoenix/issues).
