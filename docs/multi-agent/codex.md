# Codex (`elixir-phoenix-codex`)

Codex installs **from this repo** — no separate mirror. Codex reads its
own marketplace manifest at the repo-root `.agents/plugins/marketplace.json`
(NOT the Claude `.claude-plugin/marketplace.json`); that manifest lists
only `elixir-phoenix-codex` and points at the `targets/codex/` subtree via
a `git-subdir` source.

## Install

Verified against `codex-cli 0.130.0`.

```bash
# 1. Register the marketplace (one-time)
codex plugin marketplace add oliver-kriska/claude-elixir-phoenix --ref main

# 2. Enable the plugin in Codex's interactive plugin picker:
#    run `codex`, open the plugin list, Space to toggle
#    `elixir-phoenix-codex` on.
```

Notes:

- The flag is `--ref <branch|tag|sha>` — **there is no `--branch`**. The
  source also accepts the ref inline:
  `oliver-kriska/claude-elixir-phoenix@main`. To try a PR branch use
  `--ref feat/multi-agent-port`.
- There is **no `codex plugin add` / `codex plugin install`** in 0.130.0.
  `codex plugin marketplace add` only registers the marketplace; plugin
  enable/disable lives in the interactive picker (Space to toggle, the
  `[*]/[-]` list).
- `--sparse <path>` is an optional git sparse-checkout speedup, **not** a
  plugin filter — the manifest already scopes the install. Omit it unless
  the full-repo checkout is too large for you.

Local clone (offline / inspecting the tree):

```bash
git clone https://github.com/oliver-kriska/claude-elixir-phoenix.git
codex plugin marketplace add ./claude-elixir-phoenix
# then enable elixir-phoenix-codex in the picker as above
```

You will see **exactly one** plugin (`elixir-phoenix-codex`). Verified:
when `.agents/plugins/marketplace.json` exists Codex reads it and never
reads the Claude `.claude-plugin/marketplace.json`, so the Claude
`elixir-phoenix` plugin no longer appears as a duplicate.

## Usage

Slash commands are invoked with `$skill-name` (Codex convention):

```
$phx-quick add a unique constraint to the email column
$phx-plan multi-tenant billing with Stripe webhooks
$ecto-n1-check
$lv-assigns
```

The 14 reference skills (testing, oban, ecto-patterns, …) auto-load on
file context. The 22 Iron Laws are **inlined** at the bottom of each
auto-load skill body since Codex has no SubagentStart hook.

## Tidewave MCP

`targets/codex/.mcp.json` ships a stdio Tidewave config. Codex doesn't
support MCP SSE. Once your Phoenix app is running, Codex picks it up
automatically.

## What ships (v3.0.0)

Full Phase 1 + Phase 2 parity — one release:

- 43 skills loaded
- 29 slash commands invokable as `$skill-name`
- **21 sub-agents** as `agents-toml/<name>.toml`, copied into
  `~/.codex/agents/` by a SessionStart helper
- **Hooks for 6 of 9 events** (PreToolUse, PostToolUse, SessionStart,
  Stop, PreCompact, PostCompact)
- Iron Laws inlined into 14 reference skills
- Tidewave MCP via stdio
- `CLAUDE.md` / `AGENTS.md` companion files
- 8 KB description-budget enforcement at port time

## Not ported (no Codex equivalent)

- Hook events `PostToolUseFailure`, `SubagentStart`, `StopFailure` have no
  Codex counterpart. `SubagentStart` is the reason Iron Laws are inlined
  per skill instead of injected globally — not a deferral, a permanent
  per-target tradeoff.

## Tradeoffs vs. Claude Code

- No `SubagentStart` → Iron Laws inlined per skill instead of injected
  globally. Adds ~600 bytes to each auto-load skill, but doesn't bleed
  into the description budget.
- Slash commands use `$skill-name`, not `/phx:skill-name`. The pipeline
  rewrites these in skill bodies; user muscle memory is the only friction.
- 8 KB description budget is real. `descriptions_short.yaml` lets us
  override individual skill descriptions if any single edit pushes us
  over.

## Manual smoke test

After install, run:

```bash
$phx-help
$phx-quick add a unique index on users.email
```

If `$phx-help` produces a command list, the plugin is loaded.
If `$phx-quick` produces an Ecto migration, the canonical workflow path
is intact.
