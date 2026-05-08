# Codex (`elixir-phoenix-codex`)

Codex CLI reads `.claude-plugin/marketplace.json` natively and supports
sparse installs, so the Codex flavour ships **from this repo** —
no separate mirror. The generated tree lives at `targets/codex/`.

## Install

```bash
codex plugin marketplace add oliver-kriska/claude-elixir-phoenix \
  --sparse targets/codex
codex plugin install elixir-phoenix-codex
```

If your Codex version doesn't accept `--sparse`, fall back to:

```bash
git clone https://github.com/oliver-kriska/claude-elixir-phoenix.git
codex plugin install ./claude-elixir-phoenix/targets/codex
```

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
auto-load skill body since Codex has no SubagentStart hook (yet).

## Tidewave MCP

`targets/codex/.mcp.json` ships a stdio Tidewave config. Codex doesn't
support MCP SSE. Once your Phoenix app is running, Codex picks it up
automatically.

## What works (v2.9.0)

- 43 skills loaded
- 29 slash commands invokable as `$skill-name`
- Iron Laws inlined into 14 reference skills
- Tidewave MCP via stdio
- `CLAUDE.md` / `AGENTS.md` companion files
- 8 KB description-budget enforcement at port time

## What's deferred to v3.0.0

- Sub-agents — generated as TOMLs into `targets/codex/agents-toml/`
  and dropped into `~/.codex/agents/` via SessionStart hook (Phase 2A)
- Hooks parity for 6 of 9 events (PreToolUse, PostToolUse, SessionStart,
  Stop, PreCompact/PostCompact, PermissionRequest stub)
- Dropped events: PostToolUseFailure, SubagentStart, StopFailure
  (no Codex equivalents)

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
