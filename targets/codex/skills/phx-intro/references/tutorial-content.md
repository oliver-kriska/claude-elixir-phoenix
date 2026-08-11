# Plugin Tutorial Content

Content for each section of the `$elixir-phoenix:phx-intro` tutorial.
Present ONE section at a time with AskUserQuestion between sections.
IMPORTANT: Present ALL content in each section — every paragraph, table, and code block. Do NOT abbreviate or summarize.

## Contents

- [Section 1: Welcome](#section-1-welcome)
- [Section 2: Core Workflow Commands](#section-2-core-workflow-commands)
- [Section 3: Knowledge & Safety Net](#section-3-knowledge--safety-net)
- [Section 4: Hooks & Behavioral Rules](#section-4-hooks--behavioral-rules)
- [Section 5: Init, Review & Gaps](#section-5-init-review--gaps)
- [Section 6: Cheat Sheet & Next Steps](#section-6-cheat-sheet--next-steps)

---

## Section 1: Welcome

### What This Plugin Does

This plugin adds **specialist Elixir/Phoenix agents**, **auto-loaded knowledge**, and **Iron Laws** to Claude Code. It turns a general-purpose AI into an opinionated Elixir pair programmer.

### The Core Concept

Everything revolves around a 4-phase workflow cycle:

```text
$elixir-phoenix:phx-plan → $elixir-phoenix:phx-work → $elixir-phoenix:phx-verify → $elixir-phoenix:phx-review → $elixir-phoenix:phx-compound
   |             |            |              |              |
   v             v            v              v              v
 Research &   Execute     Full check     Parallel       Capture what
 plan tasks   tasks       compile/test   code review    you learned
```

Each phase reads from the previous phase's output. Plans become checkboxes. Checkboxes track progress. Reviews catch mistakes. Compound knowledge makes future work faster.

### What You Get

| Feature | What It Does |
|---------|-------------|
| 26 specialist agents | Ecto, LiveView, security, OTP, Oban, Ash, deployment experts |
| 51 skills | Commands for every phase of development |
| 26 Iron Laws | Non-negotiable rules enforced automatically |
| Auto-loaded references | Context-aware docs loaded when you edit relevant files |
| Tidewave integration | Runtime debugging when Tidewave MCP is connected |

---

## Section 2: Core Workflow Commands

### The Full Cycle

For features that need planning and review:

```bash
# 0. Brainstorm (optional) — explore requirements interactively
$elixir-phoenix:phx-brainstorm Add some kind of notification system

# 1. Plan — spawns research agents, outputs checkbox plan
$elixir-phoenix:phx-plan Add user avatars with S3 upload

# 1b. Brief (optional) — understand the plan before starting
$elixir-phoenix:phx-brief .claude/plans/user-avatars/plan.md

# 2. Work — executes plan, checks off tasks, runs mix compile
$elixir-phoenix:phx-work .claude/plans/user-avatars/plan.md

# 3. Review — parallel agents check idioms, security, tests, and
#    cross-check implementation vs. requirements (auto-detected from
#    branch/commits, or pass `ENA-123` / `#42` / a plan/spec path)
$elixir-phoenix:phx-review

# 4. Compound — capture what you learned for future reference
$elixir-phoenix:phx-compound Fixed S3 upload timeout with multipart streaming
```

### Shortcuts

Not everything needs the full cycle:

| Command | When to Use | Time |
|---------|------------|------|
| `$elixir-phoenix:phx-quick` | Bug fixes, small features (<100 lines) | ~2 min |
| `$elixir-phoenix:phx-full` | New features, autonomous plan-work-verify-review | ~10 min |
| `$elixir-phoenix:phx-investigate` | Debugging — checks obvious things first | ~3 min |

### Decision Guide

```text
Is it a bug?
  Yes --> $elixir-phoenix:phx-investigate
  No  --> Do you know what you want?
            No  --> $elixir-phoenix:phx-brainstorm
            Yes --> Is it < 100 lines?
                      Yes --> $elixir-phoenix:phx-quick
                      No  --> Do you want full autonomy?
                                Yes --> $elixir-phoenix:phx-full
                                No  --> $elixir-phoenix:phx-plan then $elixir-phoenix:phx-work
```

### Deepening an Existing Plan

Already have a plan but want to add research or refine tasks?

```bash
$elixir-phoenix:phx-plan --existing .claude/plans/user-avatars/plan.md
```

This spawns specialist agents to analyze your existing plan and enhance it with research findings.

---

## Section 3: Knowledge & Safety Net

### Auto-Loaded Knowledge

The plugin loads relevant reference docs based on what you're editing:

| You're editing... | Plugin loads... |
|-------------------|----------------|
| `*_live.ex` | LiveView patterns, async/streams, components |
| `*_test.exs` | ExUnit patterns, Mox, factory patterns |
| `migrations/*` | Migration patterns, safe operations |
| `*auth*`, `*session*` | Security patterns, authorization rules |
| `router.ex` | Routing patterns, plug patterns, scopes |
| `*_worker.ex` | Oban patterns, idempotency rules |

This means you don't need to explicitly load anything — open a LiveView file and the plugin already knows the patterns.

### Iron Laws (26 Rules, Always Enforced)

Iron Laws are non-negotiable rules that every agent enforces. If your code violates one, the plugin stops and explains before proceeding.

**Examples:**

| Law | Why |
|-----|-----|
| No unconditional DB queries in mount | Cache-backed branch OK for SEO |
| Use streams for lists >100 items | Regular assigns = O(n) memory per user |
| No `:float` for money | Floating point math loses precision |
| Pin values with `^` in Ecto queries | Prevents SQL injection |
| Jobs must be idempotent | Oban retries on failure |
| No `String.to_atom` with user input | Atom table exhaustion DoS |
| Authorize in EVERY `handle_event` | Mount auth alone is insufficient |

### Analysis & Verification Commands

| Command | What It Does |
|---------|-------------|
| `$elixir-phoenix:phx-verify` | Full check: compile, format, credo, test — plus dialyzer when the project has it configured |
| `$elixir-phoenix:phx-audit` | 5-agent project health audit with scores |
| `$elixir-phoenix:phx-deps-audit` | Audit Hex dep updates for supply-chain risk |
| `$elixir-phoenix:phx-deps-vet` | Record vetted Hex packages in hex_vet.exs ledger |
| `$elixir-phoenix:ecto-n1-check` | Detect N+1 query patterns |
| `$elixir-phoenix:lv-assigns` | Audit LiveView socket assigns for memory |
| `$elixir-phoenix:phx-boundaries` | Check Phoenix context boundary violations |
| `$elixir-phoenix:phx-perf` | Performance analysis (Ecto, LiveView, OTP) |

### Tidewave Integration

When Tidewave MCP is connected to your running Phoenix app:

```bash
# Get docs for your exact dependency versions
mcp__tidewave__get_docs "Ecto.Query"

# Execute code in your running app
mcp__tidewave__project_eval "MyApp.Repo.aggregate(User, :count)"

# Query your dev database directly
mcp__tidewave__execute_sql_query "SELECT count(*) FROM users"
```

The plugin automatically prefers Tidewave tools over alternatives when available.

---

## Section 4: Hooks & Behavioral Rules

The plugin uses **layered enforcement** — some things run automatically, some depend on Claude following instructions, some are on-demand. Here's what actually happens:

### Layer 1: Hooks (Automatic, Every Edit)

[Claude Code hooks](https://docs.anthropic.com/en/docs/claude-code/hooks) run shell scripts automatically after tool use. These are real automation — no instructions needed:

| Hook | Trigger | What It Does |
|------|---------|-------------|
| Dangerous ops block | Before Bash command | Blocks `mix ecto.reset/drop`, `git push --force`, `MIX_ENV=prod` |
| Format check | Every `.ex`/`.exs` edit | Runs `mix format --check-formatted`, warns via stderr + exit 2 |
| Iron Law verifier | Every `.ex`/`.exs` edit | Scans code content for Iron Law violations with line numbers |
| Debug stmt warning | Every `.ex` edit | Warns about `IO.inspect`/`dbg()`/`IO.puts` in production code |
| Security reminder | Editing auth/session/password files | Outputs relevant Iron Laws via stderr + exit 2 |
| Progress logging | Every file edit | Appends to `.claude/plans/{slug}/progress.md` (async) |
| Failure hints | Bash command fails | Injects debugging hints via `additionalContext` |
| Error critic | Repeated mix failures | Escalates to structured critic analysis after 3+ failures |
| Iron Laws injection | Any subagent spawns | Injects all 26 Iron Laws into subagents via `additionalContext` |
| PreCompact rules | Before context compaction | Re-injects workflow rules via JSON `systemMessage` |

Format check **warns only** — it doesn't auto-fix (that would cause race conditions with the editor).

The PreCompact hook detects active workflow phases (`$elixir-phoenix:phx-plan`, `$elixir-phoenix:phx-work`, `$elixir-phoenix:phx-full`) and re-injects their critical rules
before context compaction. This prevents "rule amnesia" where Claude loses behavioral constraints after context is compressed.

Note: Compilation verification was moved to `$elixir-phoenix:phx-work` phase checkpoints for speed. The `verify-elixir.sh` hook has been removed.

### Layer 2: Iron Laws in Skills (Behavioral)

Each domain skill (ecto-patterns, liveview-patterns, security, etc.) embeds its own Iron Laws.
When Claude loads a skill, the laws become active context.
Claude is instructed to **stop and explain** before writing code that violates them.

This is behavioral — it works because the rules are in Claude's context, not because code enforces them. It's effective but not 100% guaranteed.

### Layer 3: Skill Loading by File Type (Behavioral)

Claude Code supports native `paths:` frontmatter that limits automatic skill
activation to matching files. This plugin uses it on domain skills; CLAUDE.md
also provides an explicit fallback routing table:

```text
*_live.ex       → liveview-patterns (streams, async, components)
*auth*, *session* → security (authorization, XSS, atom safety)
*_worker.ex     → oban (idempotency, string keys, queue config)
*_test.exs      → testing (ExUnit, Mox, factories)
Any .ex file    → elixir-idioms (always)
```

`paths:` is a file-path activation gate, not a dependency predicate. Matching a
path makes a skill eligible, while Claude still selects skills from their
descriptions; activation is not guaranteed merely because a dependency exists
in `mix.lock`. Running `$elixir-phoenix:phx-init` adds the fallback rules to the project.

---

## Section 5: Init, Review & Gaps

### Layer 4: `$elixir-phoenix:phx-init` (Strengthens Everything)

Running `$elixir-phoenix:phx-init` injects enforcement rules **directly into your project's CLAUDE.md**. This is stronger than plugin-level instructions because CLAUDE.md is always read at session
start.

What it adds:

- **Routing table** — which `$elixir-phoenix:phx-*` command fits which kind of request, and what to ask about scope before building
- **Iron Laws with STOP protocol** — explicitly tells Claude to halt on violations
- **Verification rules** — `mix compile --warnings-as-errors && mix format` after code changes
- **Stack-specific rules** — detects Phoenix version, Oban, Ash, Tidewave from `mix.exs`

```bash
$elixir-phoenix:phx-init           # First-time setup
$elixir-phoenix:phx-init --update  # Update after plugin updates
```

If you're finding the plugin inconsistent, running `$elixir-phoenix:phx-init` is the single biggest improvement you can make.

### Layer 5: `$elixir-phoenix:phx-review` + Iron Law Judge (On-Demand)

The `iron-law-judge` agent does **pattern-based violation detection** — it uses Grep to search your changed files for known anti-patterns. But it only runs when you invoke
`$elixir-phoenix:phx-review`.

What it catches with automated detection:

- `String.to_atom(` in lib code
- `field :price, :float` in schemas
- `raw(@variable)` (XSS risk)
- `Repo.` calls in LiveView mount without `connected?` guard
- Missing `^` pin in Ecto query fragments

### Layer 6: Planning Sets Structure Early

The `$elixir-phoenix:phx-plan` phase sets naming conventions, context boundaries, and module structure
**before any code exists**. This is where you prevent Rails-y patterns at the architecture
level — fat controllers, service objects, and ActiveRecord patterns get caught in the plan,
not in code review.

### What's NOT Automated (Yet)

Being honest about the gaps:

| Check | Status | Why |
|-------|--------|-----|
| `mix compile --warnings-as-errors` | `$elixir-phoenix:phx-work` checkpoints + `$elixir-phoenix:phx-full` VERIFYING phase | Compilation runs in workflow steps, not per-edit hooks |
| `mix credo` | `$elixir-phoenix:phx-full` VERIFYING phase + on-demand (`$elixir-phoenix:phx-verify`) | Not run per-task edit, only between phases |
| `mix test` | `$elixir-phoenix:phx-full` VERIFYING phase + on-demand (`$elixir-phoenix:phx-verify`) | Not run per-task, only between phases |
| `mix dialyzer` | On-demand (`$elixir-phoenix:phx-verify`) | Takes minutes, not seconds |
| Iron Law detection during coding | Behavioral only | `iron-law-judge` is review-time only |

### The Honest Summary

```text
AUTOMATIC (hooks):     Format check, security reminders, progress logging, failure hints,
                       Iron Laws in subagents, PreCompact rule preservation
BEHAVIORAL (Claude):   Iron Laws, skill loading, stop-and-explain
ON-DEMAND (commands):  $elixir-phoenix:phx-review (iron-law-judge), $elixir-phoenix:phx-verify (compile/credo/dialyzer)
STRENGTHENED BY:       $elixir-phoenix:phx-init (injects rules into project CLAUDE.md)
```

The plugin works best when all layers are active: `$elixir-phoenix:phx-init` for persistent rules, hooks for automatic checks, and `$elixir-phoenix:phx-review` to catch what the behavioral layer
missed.

---

## Section 6: Cheat Sheet & Next Steps

### Command Reference

**Workflow (use in order):**

| Command | Phase |
|---------|-------|
| `$elixir-phoenix:phx-brainstorm <topic>` | Adaptive requirements gathering |
| `$elixir-phoenix:phx-plan <feature>` | Plan with research agents |
| `$elixir-phoenix:phx-plan --existing <file>` | Enhance existing plan |
| `$elixir-phoenix:phx-brief [plan file]` | Interactive plan walkthrough |
| `$elixir-phoenix:phx-work <plan file>` | Execute plan with verification |
| `$elixir-phoenix:phx-review` | Parallel agent code review |
| `$elixir-phoenix:phx-triage` | Interactive review finding triage |
| `$elixir-phoenix:phx-compound` | Capture solved problem |

**Standalone:**

| Command | Purpose |
|---------|---------|
| `$elixir-phoenix:phx-quick <task>` | Fast implementation, skip ceremony |
| `$elixir-phoenix:phx-full <feature>` | Autonomous plan-work-review cycle; `--codex` adds a cross-model review track |
| `$elixir-phoenix:phx-investigate <bug>` | Structured bug investigation |
| `$elixir-phoenix:phx-verify` | Run all quality checks |
| `$elixir-phoenix:phx-research <topic>` | Research with parallel workers, Tidewave-first |
| `$elixir-phoenix:phx-pr-review <PR#>` | Address PR review threads — fix, reply, resolve |
| `$elixir-phoenix:phx-watch-pr <PR#>` | Background-watch a PR for reviews + CI; `--codex` adds a Codex cloud review loop |
| `$elixir-phoenix:phx-codex-loop` | Fix until Codex CLI review is clean (optional — needs codex CLI) |
| `$elixir-phoenix:phx-deps-update` | Bump outdated Hex deps, grouped PRs |
| `$elixir-phoenix:phx-recall <question>` | Recall prior work from past sessions/git |
| `$elixir-phoenix:phx-permissions` | Scan sessions, recommend safe Bash permissions |
| `$elixir-phoenix:phx-help [description]` | Interactive command advisor — helps pick the right command |

**Analysis:**

| Command | Purpose |
|---------|---------|
| `$elixir-phoenix:phx-audit` | Full project health audit |
| `$elixir-phoenix:phx-deps-audit` | Hex dep update supply-chain audit |
| `$elixir-phoenix:phx-deps-vet` | Hex package audit ledger (`hex_vet.exs`) |
| `$elixir-phoenix:phx-perf` | Performance analysis |
| `$elixir-phoenix:ecto-n1-check` | N+1 query detection |
| `$elixir-phoenix:lv-assigns` | LiveView memory audit |
| `$elixir-phoenix:phx-boundaries` | Context boundary check |
| `$elixir-phoenix:phx-techdebt` | Technical debt analysis |
| `$elixir-phoenix:phx-trace <function>` | Call chain tracing |
| `$elixir-phoenix:ecto-constraint-debug` | Debug Ecto constraint errors |

**Knowledge:**

| Command | Purpose |
|---------|---------|
| `$elixir-phoenix:phx-examples` | Practical walkthroughs |
| `$elixir-phoenix:phx-learn-from-fix` | Capture a lesson from a fix |
| `$elixir-phoenix:phx-challenge` | Rigorous review mode |

### Playing Nicely With Claude Code Built-Ins

The plugin complements — it doesn't replace — CC's built-in features. A few that pair well with the Elixir workflow:

- **Auto mode + xhigh effort (Opus 4.7, v2.1.111)**: run `$elixir-phoenix:phx-full` hands-off. Auto mode routes permission prompts through a safety classifier instead of blocking on you.
- **`/focus` (v2.1.110)**: hides intermediate tool output. Useful during long `$elixir-phoenix:phx-work` or `$elixir-phoenix:phx-full` runs when you only care about the final state.
- **Recap (v2.1.108)**: CC summarizes what happened when you return to a session.
  Our scratchpad (`.claude/plans/{slug}/scratchpad.md`) still captures what recap
  can't — checkbox progress, subagent findings, deliberate handoffs.
- **`/less-permission-prompts` (built-in, v2.1.111)**: generic Bash/MCP allowlist scanner. Use `$elixir-phoenix:phx-permissions` for Elixir-specific recommendations (credo, mix, psql, Tidewave) on top
  of it.

### 3 Tips for Getting the Most Out of the Plugin

1. **Start with `$elixir-phoenix:phx-plan` for any feature that touches multiple files.** The research agents catch architectural issues early, before you've written code that needs rewriting.

2. **Let Iron Laws stop you.** When the plugin flags a violation, read the explanation.
   These rules exist because the Elixir community learned them the hard way
   (atom exhaustion in prod, N+1 queries at scale, double-mount in LiveView).

3. **Use `$elixir-phoenix:phx-compound` after solving hard bugs.** The solution gets indexed and searchable. Next time you hit something similar, the plugin finds your past solution automatically.

### Next Steps

- Try `$elixir-phoenix:phx-plan` with your next feature to see the full workflow
- Run `$elixir-phoenix:phx-verify` to see your project's current health
- Run `$elixir-phoenix:phx-audit` for a comprehensive project assessment
- Check `$elixir-phoenix:phx-examples` for detailed walkthroughs
