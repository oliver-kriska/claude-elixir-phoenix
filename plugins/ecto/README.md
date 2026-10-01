# Elixir/Phoenix: Ecto

Keeps the `/ecto:*` commands of the
[Elixir/Phoenix plugin](https://phxagents.dev) working. It is installed with
that plugin as a dependency, and does nothing on its own: each command hands
off to the matching `/phx:` skill.

| Command | Runs |
|---|---|
| `/ecto:n1-check` | `/phx:n1-check` — find N+1 queries in Ecto code |
| `/ecto:constraint-debug` | `/phx:ecto-constraint-debug` — debug unique, foreign-key and check constraint violations |

This plugin has no hooks, agents, MCP servers or network access of its own.
Questions and bugs: [GitHub issues](https://github.com/oliver-kriska/claude-elixir-phoenix/issues).
