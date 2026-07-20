# Claude Code Settings Permission Format

How to correctly write permissions to Claude Code settings files.

Source: [code.claude.com/docs/en/permissions](https://code.claude.com/docs/en/permissions)

## Settings File Hierarchy

Claude Code reads settings from multiple locations. More specific scopes
take precedence; `deny` at any level blocks even if another level allows:

| Scope | File | Shared? |
|-------|------|---------|
| User (global) | `~/.claude/settings.json` | No |
| Project (team) | `.claude/settings.json` | Yes (git) |
| Local (personal) | `.claude/settings.local.json` | No (gitignored) |

## Permission Format

```json
{
  "permissions": {
    "allow": [
      "Bash(npm run build)",
      "Bash(npm run test *)",
      "Bash(git *)"
    ],
    "deny": [
      "Bash(rm -rf *)",
      "Bash(sudo *)"
    ]
  }
}
```

Rules are evaluated: **deny → ask → allow**. First match wins.

## Pattern Syntax

Permission rules follow `Tool` or `Tool(specifier)` format.

### Match all uses

| Rule | Effect |
|------|--------|
| `Bash` | Matches ALL Bash commands |
| `Bash(*)` | Same — matches all |

### Wildcard patterns with `*`

`*` is a glob wildcard. The **space before `*` matters**:

| Pattern | Matches | Does NOT match |
|---------|---------|----------------|
| `Bash(ls *)` | `ls -la`, `ls /tmp` | `lsof` (word boundary) |
| `Bash(ls*)` | `ls -la`, `lsof` | (no boundary) |
| `Bash(git *)` | `git diff`, `git add` | `gitk` |
| `Bash(mix test *)` | `mix test test/foo.exs` | `mix testing` |
| `Bash(* --version)` | `node --version` | — |
| `Bash(npm run build)` | exact match only | `npm run build:dev` |

### Deprecated `:*` syntax

> "The legacy `:*` suffix syntax is equivalent to `*` but is deprecated."
> — [Claude Code docs](https://code.claude.com/docs/en/permissions)

**Do NOT use** `Bash(git:*)` — use `Bash(git *)` instead. The `:*` format
may not match reliably and will be removed in a future version.

### Compound commands

Claude Code is aware of shell operators (`&&`, `|`, `;`). A prefix match
rule like `Bash(safe-cmd *)` won't give permission to run `safe-cmd && other-cmd`.

When "Yes, don't ask again" is clicked on a compound command, Claude Code
saves a **separate rule for each subcommand** (up to 5 rules).

## Recommended Permission Sets

### Minimal (Read-Only Developer)

```json
{
  "permissions": {
    "allow": [
      "Bash(ls *)",
      "Bash(cat *)",
      "Bash(grep *)",
      "Bash(mix compile *)",
      "Bash(mix test *)",
      "Bash(git status)",
      "Bash(git log *)",
      "Bash(git diff *)"
    ]
  }
}
```

### Standard Elixir Developer

```json
{
  "permissions": {
    "allow": [
      "Bash(ls *)", "Bash(cat *)", "Bash(grep *)",
      "Bash(head *)", "Bash(tail *)", "Bash(wc *)",
      "Bash(find *)", "Bash(which *)", "Bash(mkdir *)",
      "Bash(mix compile *)", "Bash(mix test *)",
      "Bash(mix format *)", "Bash(mix credo *)",
      "Bash(mix deps.get *)", "Bash(mix ecto.migrate *)",
      "Bash(mix ecto.gen.migration *)", "Bash(mix phx.routes *)",
      "Bash(mix xref *)", "Bash(mix hex.info *)",
      "Bash(git *)"
    ]
  }
}
```

### Full-Trust Developer

```json
{
  "permissions": {
    "allow": [
      "Bash(mix *)", "Bash(git *)", "Bash(npm *)",
      "Bash(ls *)", "Bash(cat *)", "Bash(grep *)",
      "Bash(find *)", "Bash(mkdir *)", "Bash(cp *)"
    ],
    "deny": [
      "Bash(mix ecto.reset *)", "Bash(mix ecto.drop *)",
      "Bash(git push --force *)", "Bash(git push -f *)",
      "Bash(git reset --hard *)",
      "Bash(rm -rf *)", "Bash(sudo *)"
    ]
  }
}
```

## Merging Strategy

When the permission analyzer writes to settings:

1. **Read** current contents of the target settings file
2. **Parse** existing `permissions.allow` array
3. **Append** new entries (skip duplicates)
4. **Fix deprecated** `:*` patterns → `*`
5. **Write** merged result back

## Project vs Global Placement

| Command Type | Recommended Location |
|-------------|---------------------|
| Universal tools (`ls`, `grep`, `cat`) | `~/.claude/settings.json` (global) |
| Elixir-specific (`mix test`, `mix compile`) | `.claude/settings.json` (project) |
| Personal preferences | `.claude/settings.local.json` (local) |
