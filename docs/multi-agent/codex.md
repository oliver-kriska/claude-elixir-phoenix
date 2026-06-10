# Codex (`elixir-phoenix-codex`)

Codex installs **from this repo** — no separate mirror. Codex reads its
own marketplace manifest at the repo-root `.agents/plugins/marketplace.json`
(NOT the Claude `.claude-plugin/marketplace.json`); that manifest lists
only `elixir-phoenix-codex` and points at `targets/codex/` via a `local`
source resolved inside the marketplace snapshot.

> **Why `local`, not `git-subdir`:** a `git-subdir` plugin source clones
> the repo's **default branch** in a separate fetch — `targets/codex/`
> doesn't exist there until this work merges, and the clone ignores the
> `--ref` you gave `marketplace add`. A `local` path resolves inside the
> snapshot, which **is** fetched at your `--ref` (verified on codex-cli
> 0.139.0; this is also how Codex's own bundled `openai-curated`
> marketplace works).

## Install

Verified end-to-end against `codex-cli 0.139.0`.

```bash
# 1. Register the marketplace source (fetches the snapshot)
codex plugin marketplace add oliver-kriska/claude-elixir-phoenix --ref main

# 2. Install the plugin — non-interactive since codex-cli 0.131.0
codex plugin add elixir-phoenix-codex@oliver-kriska

# 3. Verify
codex plugin list --json   # → installed: elixir-phoenix-codex, enabled: true
```

`codex plugin add` (added in 0.131.0, PR #21396) replaces the old
interactive-picker-only activation — no TUI required. Skills load
directly from the plugin cache
(`~/.codex/plugins/cache/oliver-kriska/elixir-phoenix-codex/<version>/`);
they are **no longer copied into `~/.codex/skills/`** (that was 0.130.x
behavior — don't use `ls ~/.codex/skills` as the activation check).

Notes:

- The flag is `--ref <branch|tag|sha>` — **there is no `--branch`**. The
  source also accepts the ref inline:
  `oliver-kriska/claude-elixir-phoenix@main`. To try a PR branch use
  `--ref feat/multi-agent-port`.
- **`marketplace add` is idempotent and does NOT re-pull a newer ref.**
  If you registered an older revision (or a PR branch that has since
  moved), the cached snapshot is stale. Force a refresh with
  `codex plugin marketplace remove oliver-kriska` then `add … --ref …`
  again (or `codex plugin marketplace upgrade`), then
  `codex plugin add …` again.
- `--sparse <path>` is an optional git sparse-checkout speedup, **not** a
  plugin filter — the manifest already scopes the install.
- All plugin subcommands take `--json` (0.137–0.138+) for scripting.

Local clone (offline / inspecting the tree):

```bash
git clone https://github.com/oliver-kriska/claude-elixir-phoenix.git
codex plugin marketplace add ./claude-elixir-phoenix
codex plugin add elixir-phoenix-codex@oliver-kriska
```

You will see **exactly one** plugin (`elixir-phoenix-codex`). Verified:
when `.agents/plugins/marketplace.json` exists Codex reads it and never
reads the Claude `.claude-plugin/marketplace.json`, so the Claude
`elixir-phoenix` plugin no longer appears as a duplicate (manifest
precedence re-confirmed in codex-rs source:
`MARKETPLACE_MANIFEST_RELATIVE_PATHS` lists `.agents/plugins/` first).

## Usage

> **Codex has no `$command` / `/command` invocation.** Plugin skills
> auto-load by their `description` — exactly the Claude skill model. You
> **describe your task in plain language** and the matching skill
> triggers. There is nothing to type like `$phx-help`.

```
add a unique constraint to the email column      → phx-quick skill
plan multi-tenant billing with Stripe webhooks   → phx-plan skill
this query looks like an N+1                      → ecto-n1-check skill
```

Verified live on 0.139.0: a `codex exec` session lists all 47
`elixir-phoenix-codex:*` skills in its registry and routes plain-language
tasks to them. Since 0.139.0 Codex requires the agent to read a selected
SKILL.md **completely through EOF** (PR #27044) — good news for this
plugin's progressive-disclosure skill bodies.

The 16 file-context reference skills (testing, oban, ecto-patterns, …)
auto-load when you touch matching files. The 31 workflow skills
(`phx-plan`, `phx-work`, `phx-review`, …) trigger from their description.
The 22 Iron Laws are **inlined** at the bottom of each auto-load skill
body — defence in depth alongside the SubagentStart hook (below).

## Tidewave MCP

`targets/codex/.mcp.json` ships a stdio Tidewave config. Codex doesn't
support MCP SSE. Once your Phoenix app is running, Codex picks it up
automatically.

## What ships (v3.0.0)

Full Phase 1 + Phase 2 parity — one release:

- 47 skills (16 file-context reference + 31 workflow skills like
  `phx-plan`), all description-triggered — no typed commands
- **25 sub-agents** as `agents-toml/<name>.toml`, copied into
  `~/.codex/agents/` by a SessionStart helper (see hook-trust caveat)
- **Hooks for 7 of 9 events** (PreToolUse, PostToolUse, SessionStart,
  Stop, PreCompact, PostCompact, **SubagentStart** — supported since
  codex-cli 0.133.0, PR #22782)
- Iron Laws inlined into 16 reference skills
- Tidewave MCP via stdio
- `CLAUDE.md` / `AGENTS.md` companion files
- 8 KB description-budget enforcement at port time

## Hook trust (read this before relying on hooks)

Codex gates non-managed hooks behind a **trust prompt**: each hook's
normalized config is hashed and must be approved (persisted as
`trusted_hash` under `[hooks.state]` in `~/.codex/config.toml`) before it
executes. Expect a one-time approval flow in the TUI after installing.

Current verification status on 0.139.0:

- Plugin hooks **load** (hook metadata is read from
  `plugin.json → hooks/hooks.json`; source-verified) and hook commands
  resolve via `${PLUGIN_ROOT}` (Codex injects `PLUGIN_ROOT` and
  `CLAUDE_PLUGIN_ROOT` into plugin hook env).
- Plugin hooks were **not observed executing under `codex exec`**, even
  with `--dangerously-bypass-hook-trust` (an isolated one-hook probe
  plugin confirmed this; user-level `~/.codex/hooks.json` hooks DO fire
  there). Interactive TUI behavior may differ — if hooks don't fire for
  you after trusting them, that's the same limitation.
- Fallback if the SessionStart agent-installer doesn't run: copy the
  agent TOMLs once by hand —

```bash
bash ~/.codex/plugins/cache/oliver-kriska/elixir-phoenix-codex/*/hooks/scripts/install-codex-agents.sh
ls ~/.codex/agents | head        # 25 agent TOMLs
```

## Not ported (no Codex equivalent)

- Hook events `PostToolUseFailure` and `StopFailure` have no Codex
  counterpart. (`SubagentStart` **is** ported as of codex-cli 0.133.0 —
  earlier revisions of this doc predate that.) Codex additionally offers
  `SubagentStop`, `UserPromptSubmit`, and `PermissionRequest` events that
  the source plugin doesn't use yet.

## Tradeoffs vs. Claude Code

- Iron Laws are both injected via `SubagentStart` **and** inlined per
  reference skill — the inlining predates 0.133.0 SubagentStart support
  and stays as defence in depth (hook trust is user-granted, inlining
  always works).
- No typed commands at all (Codex has no `$`/`/` invocation). Workflow
  skills that are `/phx:plan` on Claude are description-triggered skills
  here; the pipeline rewrites in-body cross-references to the bare skill
  name (e.g. `` `phx-review` ``). Slightly less discoverable than a
  command palette, but the routing is automatic.
- 8 KB description budget is real. `descriptions_short.yaml` lets us
  override individual skill descriptions if any single edit pushes us
  over.
- Hook execution requires user trust (see above) — Claude Code plugin
  hooks run without a comparable approval step.

## Smoke test

```bash
codex plugin list --json                    # installed + enabled
printf 'list skills starting with phx-' | codex exec --skip-git-repo-check -
```

Then in a `codex` session, just describe a task — don't type a command:

```
add a unique index on users.email
```

If Codex produces an Ecto migration following the plugin's patterns
(and Iron Laws are respected), the workflow path is intact. Opening a
`.ex` file should auto-load the matching reference skill.
