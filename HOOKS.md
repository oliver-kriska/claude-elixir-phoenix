# Hooks

The plugin ships **23 hooks across 8 lifecycle events**. They are the
deterministic layer: skills and agents are instructions a model may or may not
follow, hooks are shell scripts that always run.

That distinction is the whole reason they exist. Session analysis across 400
sessions measured `CLAUDE.md` prose rules firing **~0% of the time** — the rules
were correct and simply never consulted. Anything that genuinely must happen
lives here instead.

Every script is plain, auditable bash in
[`plugins/elixir-phoenix/hooks/scripts/`](plugins/elixir-phoenix/hooks/scripts/).
No telemetry, no network calls except a localhost Tidewave probe and `git fetch`.

## Contents

- [The five things hooks do](#the-five-things-hooks-do)
- [What fires when](#what-fires-when)
- [Full hook list](#full-hook-list)
- [Two rules that govern all of them](#two-rules-that-govern-all-of-them)
- [Turning hooks off](#turning-hooks-off)
- [Deep dives](#deep-dives)

## The five things hooks do

**1. Stop destructive commands.** `mix ecto.reset`, `mix ecto.drop`,
`MIX_ENV=prod mix …`, and force pushes are denied before they execute, with a
safer alternative attached so Claude does not just retry.

**2. Verify code against the Iron Laws.** After every edit to an Elixir file,
the content you just wrote is scanned for seven of the non-negotiable rules —
`:float` for money, `String.to_atom` on user input, `raw/1` with a variable,
implicit cross joins, unsupervised `start_link`, and more. A violation feeds the
specific law and line back to Claude for correction.

**3. Get context to models that cannot read it themselves.** Subagents start
with fresh context and cannot reliably read plugin reference files. A
`SubagentStart` hook injects all 26 Iron Laws into every one. A
`UserPromptSubmit` hook spots PR URLs and stack traces and suggests the right
`/phx:` command.

**4. Keep the plan workflow coherent.** Writing a `plan.md` hard-stops the run so
you can review before implementation. Compaction re-injects the current phase's
rules and your scratchpad's dead ends. An API failure leaves a breadcrumb the
next session reads.

**5. Break debugging loops.** Repeated `mix` failures escalate from generic
hints to a structured critic that consolidates the error history and tells
Claude to stop retrying — the Critic→Refiner pattern from AutoHarness
(Lou et al., 2026).

## What fires when

```text
  session opens
      │
      ├─ SessionStart ······ setup dirs · detect Tidewave · detect Ash
      │                      resume banner · scratchpad · branch freshness
      ▼
  you type a prompt
      │
      ├─ UserPromptSubmit ·· PR URL / stack trace → suggest a /phx: command
      ▼
  Claude picks a tool
      │
      ├─ PreToolUse ········ BLOCK destructive bash · deps gate · edit freeze
      ▼
    tool runs ──────────────────┐
      │                         │ (failed)
      │ (ok)                    ▼
      │                    PostToolUseFailure ·· mix hints → loop critic
      ▼
      ├─ PostToolUse ······· format · Iron Laws · debug stmts · security
      │                      plan STOP · edit metrics · reset loop critic
      │
      ├─ SubagentStart ····· inject Iron Laws into every spawned agent
      ▼
  context compacted
      │
      ├─ SessionStart ······ (matcher compact) re-inject phase rules +
      │                      scratchpad dead ends, re-read the active plan
      ▼
  turn ends
      │
      ├─ Stop ·············· warn about background tasks / crons
      └─ StopFailure ······· log API failure for next session's resume
```

## Full hook list

### `PreToolUse` — can block

| Hook | Fires on | Does |
|---|---|---|
| `block-dangerous-ops` | every `Bash` | Denies `mix ecto.reset/drop`, force push, `MIX_ENV=prod` |
| `deps-audit-gate` | `mix deps.*` | Tiered supply-chain gate (cache hit <200 ms, fast rules <2 s) |
| `freeze-gate` | `Edit`/`Write`/`NotebookEdit` | Enforces `/phx:freeze` edit-scope locks |

### `PostToolUse` — advises after the edit

| Hook | Fires on | Does |
|---|---|---|
| `format-elixir` | `*.ex`, `*.exs` | Warns if unformatted. Never rewrites — that would break Claude's file state |
| `iron-law-verifier` | `*.ex`, `*.exs` | Scans **only the lines you just wrote** for 7 Iron Laws |
| `debug-statement-warning` | `*.ex` (not tests) | Flags `IO.inspect`, `dbg()`, `IO.puts` |
| `security-reminder` | auth-ish filenames | Re-states the 4 security Iron Laws |
| `plan-stop-reminder` | `Write(*plan.md)` | Hard-stops before implementation |
| `log-progress` | any `Edit`/`Write` | Appends edit metrics JSONL for `/skill-monitor` |

### `PostToolUseFailure` — when `mix` fails

| Hook | Does |
|---|---|
| `elixir-failure-hints` | Command-specific hints for `compile` / `test` / `credo` / `ecto` |
| `error-critic` | Counts consecutive repeats per session. Attempt 2 warns; attempt 3+ consolidates the error history and blocks the retry reflex. Also runs on `PostToolUse` to reset the count when the command succeeds |

### `UserPromptSubmit` / `SubagentStart` — context injection

| Hook | Does |
|---|---|
| `route-intent` | PR URL → `/phx:pr-review`; stack trace or Tidewave page context → `/phx:investigate`. Once per category per session, never on an explicit slash command |
| `inject-iron-laws` | Injects all 26 Iron Laws into every spawned subagent |

### `SessionStart`

| Hook | Does |
|---|---|
| `setup-dirs` | Creates `.claude/{plans,reviews,solutions,audit,skill-metrics,research}` |
| `detect-tidewave` | Probes localhost:4000 — **only if `tidewave` is a dependency** |
| `detect-ash` | Detects Ash, prints codegen rules, checks `usage_rules` config |
| `check-scratchpad` | Surfaces dead-end notes; seeds a scratchpad template |
| `check-resume` | `↻ Plan 'x' has N remaining tasks. Resume with: /phx:work …` |
| `check-branch-freshness` | Warns when your branch is behind `main` |

### Compaction and exit

| Hook | Event | Does |
|---|---|---|
| `compact-rules` | `SessionStart` (`compact`) | Re-injects the active phase's rules plus scratchpad dead ends after compaction |
| `compact-verify` | `SessionStart` (`compact`) | Tells Claude to re-read the plan if tasks remain |
| `stop-failure-log` | `StopFailure` | Writes an API-failure note to the scratchpad |
| `check-pending-plans` | `Stop` | Warns about running background tasks and scheduled crons |

## Two rules that govern all of them

### Everything Elixir-specific is gated on `mix.exs`

Every hook checks for `mix.exs` before doing anything. Open a Rust or Python
repo with the plugin installed globally and it is inert — no directories
created, no Phoenix Iron Laws injected, no banners.

The single deliberate exception is the **force-push block**, which is dangerous
in any repository and stays global.

This gating (added in v2.10.1, issue #55) is what makes it safe to enable the
plugin globally rather than per-project.

### Hooks fail open, never closed

No hook uses `set -e`. Denials are expressed as JSON data, never as an exit
code, and the always-on Bash gate is registered as `script.sh || exit 0`.
Every registered command quotes its `${CLAUDE_PLUGIN_ROOT}` path, so a plugin
installed under a directory with a space still runs its hooks instead of
failing open.

This is not theoretical. The safety script once got corrupted by
merge-conflict markers, and because bash exited non-zero, **every Bash command
in the session was blocked**. A broken hook must degrade to "the guard is off",
never to "the session is unusable".

## Turning hooks off

The plugin does not ship a global switch, and most hooks are advisory — they
print a message and get out of the way. For the ones that block:

| Hook | Escape hatch |
|---|---|
| `deps-audit-gate` | `PHX_SKIP_DEPS_AUDIT=1 mix deps.get` |
| `freeze-gate` | `/phx:freeze off` (dormant unless you turned it on) |
| `block-dangerous-ops` | By design, none — run the command yourself in your terminal. In Claude Code, prefix with `!` |

To disable a hook outright, remove its entry from
`plugins/elixir-phoenix/hooks/hooks.json` in your installed copy, or uninstall
the plugin. `/reload-plugins` picks up the change without a restart.

## Deep dives

Each group has a reference page with the patterns, the failure modes they were
built from, and the exact output you see:

| Page | Covers |
|---|---|
| [Safety Gates](plugins/elixir-phoenix/hooks/docs/safety-gates.md) | The three blocking hooks, the fail-open contract, whitespace-evasion anchoring |
| [Code Quality](plugins/elixir-phoenix/hooks/docs/code-quality.md) | The 7 verified Iron Laws, blame-aware scanning, why formatting only warns |
| [Failure Recovery](plugins/elixir-phoenix/hooks/docs/failure-recovery.md) | The escalation ladder and the Critic→Refiner pattern |
| [Context Injection](plugins/elixir-phoenix/hooks/docs/context-injection.md) | Intent routing, subagent Iron Laws, `omitClaudeMd` vs Iron Laws |
| [Session Lifecycle](plugins/elixir-phoenix/hooks/docs/session-lifecycle.md) | All six `SessionStart` hooks and their gating |
| [Workflow State](plugins/elixir-phoenix/hooks/docs/workflow-state.md) | Plan STOP, compaction survival, the `StopFailure` breadcrumb |

Contributors adding or changing a hook should start with
[the contributor guide](plugins/elixir-phoenix/hooks/README.md), which carries
the per-event output-channel table and the shared conventions.
