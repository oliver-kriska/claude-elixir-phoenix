# Codex (`elixir-phoenix-codex`)

Codex installs **from this repo** — no separate mirror. Codex reads its
own marketplace manifest at the repo-root `.agents/plugins/marketplace.json`
(NOT the Claude `.claude-plugin/marketplace.json`); that manifest lists
only `elixir-phoenix-codex` and points at the `targets/codex/` subtree via
a `git-subdir` source.

## Install

Verified against `codex-cli 0.130.0`.

```bash
# 1. Register the marketplace SOURCE (one-time — this does NOT install
#    anything; it only writes ~/.codex/config.toml).
codex plugin marketplace add oliver-kriska/claude-elixir-phoenix --ref main

# 2. ACTIVATE the plugin (load-bearing — without this the plugin is
#    completely inert): run `codex`, open the plugin picker, Space-toggle
#    `elixir-phoenix-codex` ON, then restart the session.

# 3. Verify activation took (skills are copied into ~/.codex/skills/):
ls ~/.codex/skills | grep -i phx     # must list phx-* dirs
```

> **Step 2 is not optional.** `codex plugin marketplace add` only
> registers a *source* — it installs no skills. Until you toggle
> `elixir-phoenix-codex` ON in the picker, a Codex session's skill
> registry will not contain a single `phx-*` skill and the plugin has
> zero effect (verified empirically: a session run after only step 1
> listed 9 unrelated skills and no Iron Laws). If `ls ~/.codex/skills`
> shows no `phx-*` dirs, the plugin is **not** active no matter what the
> picker appeared to show — re-toggle and restart.

Notes:

- The flag is `--ref <branch|tag|sha>` — **there is no `--branch`**. The
  source also accepts the ref inline:
  `oliver-kriska/claude-elixir-phoenix@main`. To try a PR branch use
  `--ref feat/multi-agent-port`.
- There is **no `codex plugin add` / `codex plugin install`** in 0.130.0.
  `codex plugin marketplace add` only registers the marketplace; plugin
  enable/disable lives in the interactive picker (Space to toggle, the
  `[*]/[-]` list).
- **`marketplace add` is idempotent and does NOT re-pull a newer ref.**
  If you registered an older revision (or a PR branch that has since
  moved), the cached checkout is stale. Force a refresh with
  `codex plugin marketplace remove oliver-kriska` then `add … --ref …`
  again (or `codex plugin marketplace upgrade`). Re-toggle in the picker
  afterward.
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

> **Codex has no `$command` / `/command` invocation.** Verified against
> codex-cli 0.130.0: plugin skills auto-load by their `description` —
> exactly the Claude skill model. You **describe your task in plain
> language** and the matching skill triggers. There is nothing to type
> like `$phx-help`.

```
add a unique constraint to the email column      → phx-quick skill
plan multi-tenant billing with Stripe webhooks   → phx-plan skill
this query looks like an N+1                      → ecto-n1-check skill
```

The 14 file-context reference skills (testing, oban, ecto-patterns, …)
auto-load when you touch matching files. The 31 workflow skills
(`phx-plan`, `phx-work`, `phx-review`, …) trigger from their description.
The 22 Iron Laws are **inlined** at the bottom of each auto-load skill
body since Codex has no SubagentStart hook.

## Tidewave MCP

`targets/codex/.mcp.json` ships a stdio Tidewave config. Codex doesn't
support MCP SSE. Once your Phoenix app is running, Codex picks it up
automatically.

## What ships (v3.0.0)

Full Phase 1 + Phase 2 parity — one release:

- 45 skills (14 file-context reference + 31 workflow skills like
  `phx-plan`), all description-triggered — no typed commands
- **22 sub-agents** as `agents-toml/<name>.toml`, copied into
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
- No typed commands at all (Codex has no `$`/`/` invocation). Workflow
  skills that are `/phx:plan` on Claude are description-triggered skills
  here; the pipeline rewrites in-body cross-references to the bare skill
  name (e.g. `` `phx-review` ``). Slightly less discoverable than a
  command palette, but the routing is automatic.
- 8 KB description budget is real. `descriptions_short.yaml` lets us
  override individual skill descriptions if any single edit pushes us
  over.

## Manual smoke test

After enabling the plugin in the picker, confirm the skills installed:

```bash
ls ~/.codex/skills | grep -i phx     # phx-* skill dirs present
ls ~/.codex/agents | grep -i elixir  # 22 agent TOMLs (SessionStart helper)
```

Then in a `codex` session, just describe a task — don't type a command:

```
add a unique index on users.email
```

If Codex produces an Ecto migration following the plugin's patterns
(and Iron Laws are respected), the workflow path is intact. Opening a
`.ex` file should auto-load the matching reference skill.
