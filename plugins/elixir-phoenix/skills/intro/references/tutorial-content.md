# Plugin Tutorial Content

Content for each section of the `/phx:intro` tutorial.
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
/phx:plan → /phx:work → /phx:verify → /phx:review → /phx:compound
   |             |            |              |              |
   v             v            v              v              v
 Research &   Execute     Full check     Parallel       Capture what
 plan tasks   tasks       compile/test   code review    you learned
```

Each phase reads from the previous phase's output. Plans become checkboxes. Checkboxes track progress. Reviews catch mistakes. Compound knowledge makes future work faster.

### What You Get

| Feature | What It Does |
|---------|-------------|
| 20 specialist agents | Ecto, LiveView, security, OTP, Oban, deployment experts |
| 38 skills | Commands for every phase of development |
| 22 Iron Laws | Non-negotiable rules enforced automatically |
| Auto-loaded references | Context-aware docs loaded when you edit relevant files |
| Tidewave integration | Runtime debugging when Tidewave MCP is connected |

---

## Section 2: Core Workflow Commands

### The Full Cycle

For features that need planning and review:

```bash
# 0. Brainstorm (optional) — explore requirements interactively
/phx:brainstorm Add some kind of notification system

# 1. Plan — spawns research agents, outputs checkbox plan
/phx:plan Add user avatars with S3 upload

# 1b. Brief (optional) — understand the plan before starting
/phx:brief .claude/plans/user-avatars/plan.md

# 2. Work — executes plan, checks off tasks, runs mix compile
/phx:work .claude/plans/user-avatars/plan.md

# 3. Review — parallel agents check idioms, security, tests, and
#    cross-check implementation vs. requirements (auto-detected from
#    branch/commits, or pass `ENA-123` / `#42` / a plan/spec path)
/phx:review

# 4. Compound — capture what you learned for future reference
/phx:compound Fixed S3 upload timeout with multipart streaming
```

### Shortcuts

Not everything needs the full cycle:

| Command | When to Use | Time |
|---------|------------|------|
| `/phx:quick` | Bug fixes, small features (<100 lines) | ~2 min |
| `/phx:full` | New features, autonomous plan-work-verify-review | ~10 min |
| `/phx:investigate` | Debugging — checks obvious things first | ~3 min |

### Decision Guide

```text
Is it a bug?
  Yes --> /phx:investigate
  No  --> Do you know what you want?
            No  --> /phx:brainstorm
            Yes --> Is it < 100 lines?
                      Yes --> /phx:quick
                      No  --> Do you want full autonomy?
                                Yes --> /phx:full
                                No  --> /phx:plan then /phx:work
```

### Deepening an Existing Plan

Already have a plan but want to add research or refine tasks?

```bash
/phx:plan --existing .claude/plans/user-avatars/plan.md
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

### Iron Laws (22 Rules, Always Enforced)

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
| `/phx:verify` | Full check: compile, format, credo, test, dialyzer |
| `/phx:audit` | 5-agent project health audit with scores |
| `/phx:deps-audit` | Audit Hex dep updates for supply-chain risk |
| `/phx:deps-vet` | Record vetted Hex packages in hex_vet.exs ledger |
| `/ecto:n1-check` | Detect N+1 query patterns |
| `/lv:assigns` | Audit LiveView socket assigns for memory |
| `/phx:boundaries` | Check Phoenix context boundary violations |
| `/phx:perf` | Performance analysis (Ecto, LiveView, OTP) |

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
| Iron Laws injection | Any subagent spawns | Injects all 22 Iron Laws into subagents via `additionalContext` |
| PreCompact rules | Before context compaction | Re-injects workflow rules via JSON `systemMessage` |

Format check **warns only** — it doesn't auto-fix (that would cause race conditions with the editor).

The PreCompact hook detects active workflow phases (`/phx:plan`, `/phx:work`, `/phx:full`) and re-injects their critical rules
before context compaction. This prevents "rule amnesia" where Claude loses behavioral constraints after context is compressed.

Note: Compilation verification was moved to `/phx:work` phase checkpoints for speed. The `verify-elixir.sh` hook has been removed.

### Layer 2: Iron Laws in Skills (Behavioral)

Each domain skill (ecto-patterns, liveview-patterns, security, etc.) embeds its own Iron Laws.
When Claude loads a skill, the laws become active context.
Claude is instructed to **stop and explain** before writing code that violates them.

This is behavioral — it works because the rules are in Claude's context, not because code enforces them. It's effective but not 100% guaranteed.

### Layer 3: Skill Loading by File Type (Behavioral)

CLAUDE.md instructs Claude to load specific skills based on file patterns:

```text
*_live.ex       → liveview-patterns (streams, async, components)
*auth*, *session* → security (authorization, XSS, atom safety)
*_worker.ex     → oban (idempotency, string keys, queue config)
*_test.exs      → testing (ExUnit, Mox, factories)
Any .ex file    → elixir-idioms (always)
```

This is **not plugin infrastructure** — it's instructions that Claude follows. No hooks trigger skill loading.
This is the plugin's biggest known gap — in practice, skills rarely auto-load from file context alone.
Running `/phx:init` significantly improves this.

---

## Section 5: Init, Review & Gaps

### Layer 4: `/phx:init` (Strengthens Everything)

Running `/phx:init` injects enforcement rules **directly into your project's CLAUDE.md**. This is stronger than plugin-level instructions because CLAUDE.md is always read at session start.

What it adds:

- **7-step mandatory procedure** — complexity scoring, interview questions before coding, reference loading
- **Iron Laws with STOP protocol** — explicitly tells Claude to halt on violations
- **Verification rules** — `mix compile --warnings-as-errors && mix format` after code changes
- **Stack-specific rules** — detects Phoenix version, Oban, Ash, Tidewave from `mix.exs`

```bash
/phx:init           # First-time setup
/phx:init --update  # Update after plugin updates
```

If you're finding the plugin inconsistent, running `/phx:init` is the single biggest improvement you can make.

### Layer 5: `/phx:review` + Iron Law Judge (On-Demand)

The `iron-law-judge` agent does **pattern-based violation detection** — it uses Grep to search your changed files for known anti-patterns. But it only runs when you invoke `/phx:review`.

What it catches with automated detection:

- `String.to_atom(` in lib code
- `field :price, :float` in schemas
- `raw(@variable)` (XSS risk)
- `Repo.` calls in LiveView mount without `connected?` guard
- Missing `^` pin in Ecto query fragments

### Layer 6: Planning Sets Structure Early

The `/phx:plan` phase sets naming conventions, context boundaries, and module structure
**before any code exists**. This is where you prevent Rails-y patterns at the architecture
level — fat controllers, service objects, and ActiveRecord patterns get caught in the plan,
not in code review.

### What's NOT Automated (Yet)

Being honest about the gaps:

| Check | Status | Why |
|-------|--------|-----|
| `mix compile --warnings-as-errors` | `/phx:work` checkpoints + `/phx:full` VERIFYING phase | Compilation runs in workflow steps, not per-edit hooks |
| `mix credo` | `/phx:full` VERIFYING phase + on-demand (`/phx:verify`) | Not run per-task edit, only between phases |
| `mix test` | `/phx:full` VERIFYING phase + on-demand (`/phx:verify`) | Not run per-task, only between phases |
| `mix dialyzer` | On-demand (`/phx:verify`) | Takes minutes, not seconds |
| Iron Law detection during coding | Behavioral only | `iron-law-judge` is review-time only |

### The Honest Summary

```text
AUTOMATIC (hooks):     Format check, security reminders, progress logging, failure hints,
                       Iron Laws in subagents, PreCompact rule preservation
BEHAVIORAL (Claude):   Iron Laws, skill loading, stop-and-explain
ON-DEMAND (commands):  /phx:review (iron-law-judge), /phx:verify (compile/credo/dialyzer)
STRENGTHENED BY:       /phx:init (injects rules into project CLAUDE.md)
```

The plugin works best when all layers are active: `/phx:init` for persistent rules, hooks for automatic checks, and `/phx:review` to catch what the behavioral layer missed.

---

## Section 6: Cheat Sheet & Next Steps

### Command Reference

**Workflow (use in order):**

| Command | Phase |
|---------|-------|
| `/phx:brainstorm <topic>` | Adaptive requirements gathering |
| `/phx:plan <feature>` | Plan with research agents |
| `/phx:plan --existing <file>` | Enhance existing plan |
| `/phx:brief [plan file]` | Interactive plan walkthrough |
| `/phx:work <plan file>` | Execute plan with verification |
| `/phx:review` | Parallel agent code review |
| `/phx:triage` | Interactive review finding triage |
| `/phx:compound` | Capture solved problem |

**Standalone:**

| Command | Purpose |
|---------|---------|
| `/phx:quick <task>` | Fast implementation, skip ceremony |
| `/phx:full <feature>` | Autonomous plan-work-review cycle |
| `/phx:investigate <bug>` | Structured bug investigation |
| `/phx:verify` | Run all quality checks |
| `/phx:research <topic>` | Research with parallel workers, Tidewave-first |
| `/phx:pr-review <PR#>` | Address PR review comments |
| `/phx:permissions` | Scan sessions, recommend safe Bash permissions |
| `/phx:help [description]` | Interactive command advisor — helps pick the right command |

**Analysis:**

| Command | Purpose |
|---------|---------|
| `/phx:audit` | Full project health audit |
| `/phx:deps-audit` | Hex dep update supply-chain audit |
| `/phx:deps-vet` | Hex package audit ledger (`hex_vet.exs`) |
| `/phx:perf` | Performance analysis |
| `/ecto:n1-check` | N+1 query detection |
| `/lv:assigns` | LiveView memory audit |
| `/phx:boundaries` | Context boundary check |
| `/phx:techdebt` | Technical debt analysis |
| `/phx:trace <function>` | Call chain tracing |
| `/ecto:constraint-debug` | Debug Ecto constraint errors |

**Knowledge:**

| Command | Purpose |
|---------|---------|
| `/phx:examples` | Practical walkthroughs |
| `/phx:learn-from-fix` | Capture a lesson from a fix |
| `/phx:challenge` | Rigorous review mode |

### Playing Nicely With Claude Code Built-Ins

The plugin complements — it doesn't replace — CC's built-in features. A few that pair well with the Elixir workflow:

- **Auto mode + xhigh effort (Opus 4.7, v2.1.111)**: run `/phx:full` hands-off. Auto mode routes permission prompts through a safety classifier instead of blocking on you.
- **`/focus` (v2.1.110)**: hides intermediate tool output. Useful during long `/phx:work` or `/phx:full` runs when you only care about the final state.
- **Recap (v2.1.108)**: CC summarizes what happened when you return to a session.
  Our scratchpad (`.claude/plans/{slug}/scratchpad.md`) still captures what recap
  can't — checkbox progress, subagent findings, deliberate handoffs.
- **`/less-permission-prompts` (built-in, v2.1.111)**: generic Bash/MCP allowlist scanner. Use `/phx:permissions` for Elixir-specific recommendations (credo, mix, psql, Tidewave) on top of it.

### 3 Tips for Getting the Most Out of the Plugin

1. **Start with `/phx:plan` for any feature that touches multiple files.** The research agents catch architectural issues early, before you've written code that needs rewriting.

2. **Let Iron Laws stop you.** When the plugin flags a violation, read the explanation.
   These rules exist because the Elixir community learned them the hard way
   (atom exhaustion in prod, N+1 queries at scale, double-mount in LiveView).

3. **Use `/phx:compound` after solving hard bugs.** The solution gets indexed and searchable. Next time you hit something similar, the plugin finds your past solution automatically.

### Next Steps

- Try `/phx:plan` with your next feature to see the full workflow
- Run `/phx:verify` to see your project's current health
- Run `/phx:audit` for a comprehensive project assessment
- Check `/phx:examples` for detailed walkthroughs
