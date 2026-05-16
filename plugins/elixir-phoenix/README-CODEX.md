# Elixir Phoenix Codex Support

This fork adds Codex-native plugin support to
`oliver-kriska/claude-elixir-phoenix`.

Claude Code support remains in the existing `.claude-plugin/`, `skills/`,
`agents/`, and `hooks/` directories. Codex-specific entrypoints live in
`plugins/elixir-phoenix/codex-skills/` and are exposed by `plugins/elixir-phoenix/.codex-plugin/plugin.json`.

## Initial Skills

- `phx-plan`
- `phx-work`
- `phx-review`

Use natural-language prompts such as:

```text
phx plan Add user avatars with S3 upload
phx work docs/plans/user-avatars.md
phx review my current changes
```

Exact Claude slash-command parity like `/phx:plan` is not guaranteed in Codex.
The target is Codex-native skill routing.
