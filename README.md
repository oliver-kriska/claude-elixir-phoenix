# Elixir Phoenix Plugin for Claude Code

**Claude Code is great. But it doesn't know that `assign_new` silently skips on reconnect, that `:float` will corrupt your money fields, or that your Oban job isn't idempotent.**

This plugin does. It coordinates **22 specialist agents** that plan, implement,
review, and verify your Elixir/Phoenix code in parallel -- each with domain
expertise, fresh context, and enforced [Iron Laws](#iron-laws-non-negotiable-rules)
that catch the bugs your tests won't.

```bash
# You describe the feature. The plugin figures out the rest.
/phx:plan Add real-time comment notifications

# 4 research agents analyze your codebase in parallel.
# A structured plan lands in .claude/plans/comment-notifications/plan.md
# Then:

/phx:work .claude/plans/comment-notifications/plan.md
# Implements task by task. Compiles after each change.
# Stops cold if code violates an Iron Law.

/phx:review
# 4 specialist agents audit in parallel:
# idioms, security, tests, compilation.
# Deduplicates findings. Flags pre-existing issues separately.
```

No prompt engineering. No "please check for N+1 queries." The plugin auto-loads
the right domain knowledge based on what files you're editing and enforces rules
that prevent the mistakes Elixir developers actually make in production.

```
┌─────────────────────────────────────────────────────────────────────┐
│  ⚗  Elixir/Phoenix Plugin for Claude Code                           │
│                                                                     │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐           │
│  │    20    │    40    │    96    │    18    │    22    │           │
│  │  Agents  │  Skills  │   Refs   │  Hooks   │Iron Laws │           │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘           │
│                                                                     │
│  AGENTS                          COMMANDS                           │
│  ─────────────────────           ──────────────────────────         │
│  Orchestrators (opus)            Workflow                           │
│    workflow-orchestrator           /phx:plan    /phx:work           │
│    planning-orchestrator           /phx:review  /phx:full           │
│    parallel-reviewer               /phx:compound /phx:quick         │
│    context-supervisor              /phx:brief   /phx:triage         │
│                                                                     │
│  Reviewers (sonnet)              Investigation & Debug              │
│    elixir-reviewer                 /phx:investigate /phx:trace      │
│    testing-reviewer                /ecto:n1-check   /phx:perf       │
│    security-analyzer               /ecto:constraint-debug           │
│    iron-law-judge                  /lv:assigns                      │
│                                                                     │
│  Architecture (sonnet)           Analysis & Review                  │
│    liveview-architect              /phx:audit    /phx:verify        │
│    ecto-schema-designer            /phx:techdebt /phx:boundaries    │
│    phoenix-patterns-analyst        /phx:pr-review /phx:challenge    │
│    otp-advisor                     /phx:research  /phx:document     │
│                                                                     │
│  Investigation (sonnet/haiku)    Knowledge (auto-loaded)            │
│    deep-bug-investigator           liveview-patterns  ecto-patterns │
│    call-tracer                     elixir-idioms      security      │
│    xref-analyzer                   phoenix-contexts   oban          │
│    verification-runner             testing   deploy   tidewave      │
│                                                                     │
│  Domain (sonnet)                 Hooks                              │
│    oban-specialist                 auto-format · auto-compile       │
│    deployment-validator            iron-law-verify · security-scan  │
│    hex-library-researcher          debug-stmt-detect · error-critic │
│    web-researcher                  progress-tracking · block-danger │
│                                                                     │
│  ───────────────────────────────────────────────────────────        │
│  22 Iron Laws · Tidewave MCP · plan→work→verify→review→compound     │
│  github.com/oliver-kriska/claude-elixir-phoenix                     │
└─────────────────────────────────────────────────────────────────────┘
```

> **v2.10.0** -- new framework-agnostic **`catchup`** companion plugin: `/catchup` return-from-absence briefing. [Issues](https://github.com/oliver-kriska/claude-elixir-phoenix/issues) welcome.

## Installation

### From GitHub (recommended)

```bash
# In Claude Code, add the marketplace
/plugin marketplace add oliver-kriska/claude-elixir-phoenix

# Install the plugin
/plugin install elixir-phoenix
```

### Companion plugin: `catchup`

The same marketplace also ships **`catchup`** — a framework-agnostic
`/catchup` return-from-absence briefing (PRs, reviews, git, Linear,
calendar → one prioritized Context Brief, including which upstream
changes touch *your* in-flight files). Independent plugin, separate
manifest, install only if you want it:

```bash
/plugin install catchup@oliver-kriska
```

See `plugins/catchup/README.md`. Not coupled to Elixir/Phoenix.

### From Local Path (for development)

```bash
git clone https://github.com/oliver-kriska/claude-elixir-phoenix.git

# Option A: Add as local marketplace
/plugin marketplace add ./claude-elixir-phoenix
/plugin install elixir-phoenix

# Option B: Test plugin directly
claude --plugin-dir ./claude-elixir-phoenix/plugins/elixir-phoenix
```

## Getting Started

New to the plugin? Run the interactive tutorial:

```bash
/phx:intro
```

It walks through the workflow, commands, and features in 6 short sections (~5 min).
Skip to any section with `/phx:intro --section N`.

## Quick Examples

```bash
# Just describe what you need — the plugin detects complexity and suggests the right approach
> Fix the N+1 query in the user dashboard

# Plan a feature with parallel research agents, then execute
/phx:plan Add email notifications for new comments
/phx:work .claude/plans/email-notifications/plan.md

# Full autonomous mode — plan, implement, review, capture learnings
/phx:full Add user profile avatars with S3 upload

# 4-agent parallel code review (idioms, security, tests, compilation)
/phx:review

# Quick implementation — skip ceremony, just code
/phx:quick Add pagination to the users list

# Structured bug investigation with 4 parallel tracks
/phx:investigate Timeout errors in the checkout LiveView

# Project health audit across 5 categories
/phx:audit
```

The plugin auto-loads domain knowledge based on what files you're editing
(LiveView patterns for `*_live.ex`, Ecto patterns for schemas, security rules for auth code)
and enforces [Iron Laws](#iron-laws-non-negotiable-rules) that prevent common Elixir/Phoenix mistakes.

## How It Works

### The Lifecycle

The plugin implements a **Brainstorm, Plan, Work, Verify, Review, Compound** lifecycle. Each phase produces artifacts in a namespaced directory:

```
/phx:brainstorm → /phx:plan → /phx:work → /phx:verify → /phx:review → /phx:compound
       │               │           │            │              │              │
       ↓               ↓           ↓            ↓              ↓              ↓
  interview.md    plans/{slug}/  (in namespace) (in namespace) (in namespace) solutions/
```

- **Plan** -- Research agents analyze your codebase in parallel, then synthesize a structured implementation plan
- **Work** -- Execute the plan task-by-task with quick compile checks after each change
- **Verify** -- Full verification loop (compile, format, credo, test) before review
- **Review** -- Four specialist agents audit your code in parallel (idioms, security, tests, static analysis)
- **Compound** -- Capture what you learned as reusable knowledge for future sessions

### Key Concepts

- **Filesystem is the state machine.** Each phase reads from the previous phase's output. No hidden state.
- **Plan namespaces.** Each plan owns all its artifacts in `.claude/plans/{slug}/` -- plan, research, reviews, progress, scratchpad.
- **Plan checkboxes track progress.** `[x]` = done, `[ ]` = pending. `/phx:work` finds the first unchecked task and continues.
- **One plan = one work unit.** Large features get split into multiple plans. Each is self-contained.
- **Agents are automatic.** The plugin spawns specialist agents behind the scenes. You don't manage them directly.

### Plan Namespaces

Every plan gets its own directory with all related artifacts:

```
.claude/
├── plans/{slug}/          # Everything for ONE plan
│   ├── plan.md            # The plan itself (checkboxes = state)
│   ├── research/          # Research agent output
│   ├── reviews/           # Review findings (individual tracks)
│   ├── summaries/         # Compressed multi-agent output
│   ├── progress.md        # Session progress log
│   └── scratchpad.md      # Auto-written decisions, dead-ends, handoffs
├── reviews/               # Ad-hoc reviews (no plan context)
└── solutions/             # Compound knowledge (reusable across plans)
```

No more scattered files across `.claude/planning/`, `.claude/progress/`, `.claude/reviews/`. One plan, one directory, everything together.

## Architecture

### Agent Hierarchy

The plugin uses 22 agents organized into 3 tiers:

```
                    ┌──────────────────────────────┐
                    │  Orchestrators (opus model)  │
                    │  Coordinate phases, spawn    │
                    │  specialists, manage flow    │
                    └──────────┬───────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐  ┌───────────────────┐  ┌────────────────────┐
│ workflow-     │  │ planning-         │  │ parallel-          │
│ orchestrator  │  │ orchestrator      │  │ reviewer           │
│ (full cycle)  │  │ (research phase)  │  │ (review phase)     │
└───────────────┘  └───────────────────┘  └────────────────────┘
                               │                      │
                    ┌──────────┼──────────┐    ┌──────┼──────┐
                    ▼          ▼          ▼    ▼      ▼      ▼
             ┌──────────┐ ┌────────┐ ┌──────┐ ... 4 specialist
             │ liveview │ │ ecto   │ │ web  │     review agents
             │ architect│ │ schema │ │ rsch │
             └──────────┘ └────────┘ └──────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
             ┌────────────┐      ┌──────────────┐
             │  context-  │      │ Orchestrator  │
             │ supervisor │ ───► │ reads ONLY    │
             │  (haiku)   │      │ the summary   │
             └────────────┘      └──────────────┘
```

**Orchestrators** (opus) -- Primary workflow coordinators, security-critical analysis.
**Specialists** (sonnet) -- Domain experts, secondary orchestrators, judgment-heavy tasks. Sonnet 4.6 achieves near-opus quality at sonnet pricing.
**Lightweight** (haiku) -- Mechanical tasks: verification, compression, dependency analysis.

### The Context Supervisor Pattern

When an orchestrator spawns 4-8 research agents, their combined output can exceed 50k tokens -- flooding the parent's context window. The **context-supervisor** solves this using an OTP-inspired pattern:

```
┌────────────────────────────────────────────────────┐
│  Orchestrator (thin coordinator, ~10k context)     │
│  Only reads: summaries/consolidated.md             │
└──────────────────┬─────────────────────────────────┘
                   │ spawns AFTER workers finish
┌──────────────────▼─────────────────────────────────┐
│  context-supervisor (haiku, fresh 200k context)    │
│  Reads: all worker output files                    │
│  Applies: compression strategy based on size       │
│  Validates: every input file represented           │
│  Writes: summaries/consolidated.md                 │
└──────────────────┬─────────────────────────────────┘
                   │ reads from
     ┌─────────────┼─────────────┐
     ▼             ▼             ▼
  worker 1      worker 2      worker N
  research/     research/     research/
  patterns.md   security.md   liveview.md
```

**How compression works:**

| Total Output    | Strategy   | Compression | What's Kept                    |
| --------------- | ---------- | ----------- | ------------------------------ |
| Under 8k tokens | Index      | ~100%       | Full content with file list    |
| 8k - 30k tokens | Compress   | ~40%        | Key findings, decisions, risks |
| Over 30k tokens | Aggressive | ~20%        | Only critical items            |

The supervisor also **deduplicates** -- if two agents flag the same issue
(e.g., both the security analyzer and code reviewer find a missing
authorization check), it merges them into one finding with both sources cited.

**Used by:** planning-orchestrator (research synthesis), parallel-reviewer (review deduplication), audit skill (cross-category analysis).

### How Planning Works

When you run `/phx:plan Add real-time notifications`:

```
1. planning-orchestrator analyzes your request
   │
2. Spawns specialists IN PARALLEL based on feature needs:
   ├── phoenix-patterns-analyst  (always -- scans your codebase)
   ├── liveview-architect        (if UI/real-time feature)
   ├── ecto-schema-designer      (if database changes needed)
   ├── security-analyzer         (if auth/user data involved)
   ├── oban-specialist           (if background jobs needed)
   ├── web-researcher            (if unfamiliar technology)
   └── ... up to 8 agents
   │
3. Each agent writes to plans/{slug}/research/{topic}.md
   │
4. context-supervisor compresses all research into one summary
   │
5. Orchestrator reads the summary + synthesizes the plan
   │
6. Output: plans/{slug}/plan.md with [P1-T1] checkboxes
```

### How Review Works

When you run `/phx:review`:

```
1. parallel-reviewer collects your git diff
   │
2. Delegates to 4 EXISTING specialist agents:
   ├── elixir-reviewer      → Idioms, patterns, error handling
   ├── security-analyzer    → SQL injection, XSS, auth gaps
   ├── testing-reviewer     → Test coverage, factory patterns
   └── verification-runner  → mix compile, format, credo, test
   │
3. Each writes to plans/{slug}/reviews/{track}.md
   │
4. context-supervisor deduplicates + consolidates
   │
5. Output: plans/{slug}/summaries/review-consolidated.md
```

## Usage Guide

### Quick tasks (bug fixes, small changes)

Just describe what you need. The plugin auto-detects complexity and suggests the right approach:

```
> Fix the N+1 query in the dashboard

Claude: This is a simple fix (score: 2). I'll handle it directly.
```

Or use `/phx:quick` to skip ceremony:

```
/phx:quick Add pagination to the users list
```

### Medium tasks (new features, refactors)

Use `/phx:plan` to create an implementation plan, then `/phx:work` to execute it:

```
/phx:plan Add email notifications for new comments
```

The plugin will:

1. Spawn research agents to analyze your codebase patterns
2. Show a completeness check (every requirement mapped to a task)
3. Ask you how to proceed (start implementation, review plan, adjust)

When starting implementation, the plugin recommends a **fresh session** for plans with 5+ tasks. The plan file is self-contained, so no context from the planning session is needed:

```
# In a new Claude Code session:
/phx:work .claude/plans/email-notifications/plan.md
```

### Large tasks (new domains, security features)

Use deep research planning:

```
/phx:plan Add OAuth login with Google and GitHub --depth deep
```

This spawns 4+ parallel research agents, then produces a detailed plan.
For security-sensitive features, the plugin will ask clarifying questions
before proceeding. Or use `/phx:full` for fully autonomous development.

### Fixing review issues

After implementing, run a review:

```
/phx:review
```

Four parallel agents check your code (idioms, tests, security, compilation). If blockers are found, the plugin asks whether to replan or fix directly:

```
Review found 2 blockers:
1. Missing authorization in handle_event -- security risk
2. N+1 query in list_comments -- performance issue

Options:
- Replan fixes (/phx:plan --existing)
- Fix directly (/phx:work)
- Handle myself
```

### Project health checks

Run a comprehensive audit with 5 parallel specialist agents:

```
/phx:audit                    # Full audit
/phx:audit --quick            # 2-3 minute pulse check
/phx:audit --focus=security   # Deep dive single area
/phx:audit --since HEAD~10    # Audit recent changes only
```

The audit scores your project across 5 categories (architecture, performance, security, tests, dependencies) and produces an actionable report.

### Full autonomous mode

For hands-off development:

```
/phx:full Add user profile avatars with S3 upload
```

Runs the complete cycle: plan (with research), work, verify, review. After review fixes, re-verifies before cycling back. Captures learnings on completion.

## Workflow Tips

### Context management

- `/phx:plan` creates a **self-contained plan file** with all implementation details
- For 5+ task plans, start `/phx:work` in a **fresh session** to maximize context space
- For small plans (2-4 tasks), continuing in the same session is fine

### Resuming work

Plan checkboxes are the state. If a session ends mid-work:

```
# Just run /phx:work on the same plan -- it finds the first [ ] and continues
/phx:work .claude/plans/my-feature/plan.md
```

### Splitting large features

When a feature has 10+ tasks across different domains, the plugin offers to split into multiple plan files:

```
Created 3 plans (14 total tasks):
1. .claude/plans/auth/plan.md (5 tasks -- login, register, reset)
2. .claude/plans/profiles/plan.md (4 tasks -- avatar, bio, settings)
3. .claude/plans/admin/plan.md (5 tasks -- dashboard, roles)

Recommended order: 1 -> 2 -> 3
```

Execute each plan separately with `/phx:work`.

### Learning from mistakes

After fixing a bug or receiving a correction:

```
/phx:learn-from-fix Fixed N+1 query -- always preload associations in context functions
```

This updates the plugin's `common-mistakes.md` knowledge base so the same mistake is prevented in future sessions.

## Iron Laws (Non-Negotiable Rules)

The plugin enforces critical rules and **stops with an explanation** if code would violate them:

**LiveView:** No database queries in disconnected mount. Use streams for lists >100 items. Check `connected?/1` before PubSub subscribe.

**Ecto:** Never use `:float` for money. Always pin values with `^` in queries. Separate queries for `has_many`, JOIN for `belongs_to`.

**Oban:** Jobs must be idempotent. Args use string keys. Never store structs in args.

**Security:** No `String.to_atom` with user input. Authorize in every LiveView `handle_event`. Never use `raw/1` with untrusted content.

**OTP:** No process without a runtime reason. Supervise all long-lived processes.

**Elixir:** Declare `@external_resource` for compile-time files. Wrap third-party library APIs behind project-owned modules. Never use `assign_new` for values refreshed every mount.

## Commands Reference

### Workflow

| Command                 | Description                                                  |
| ----------------------- | ------------------------------------------------------------ |
| `/phx:full <feature>`   | Full autonomous cycle (plan, work, verify, review, compound) |
| `/phx:brainstorm <topic>` | Adaptive requirements gathering before planning            |
| `/phx:plan <input>`     | Create implementation plan with specialist agents            |
| `/phx:plan --existing`  | Enhance existing plan with deeper research                   |
| `/phx:work <plan-file>` | Execute plan tasks with verification                         |
| `/phx:review [focus]`   | Multi-agent code review (4 parallel agents)                  |
| `/phx:compound`         | Capture solved problem as reusable knowledge                 |
| `/phx:triage`           | Interactive triage of review findings                        |
| `/phx:document`         | Generate @moduledoc, @doc, README, ADRs                      |
| `/phx:learn-from-fix <lesson>`   | Capture lessons learned                                      |
| `/phx:brief <plan>`     | Interactive plan walkthrough                                 |
| `/phx:perf`             | Performance analysis with specialist agents                  |
| `/phx:pr-review`        | Address PR review comments                                   |

### Utility

| Command                  | Description                                                |
| ------------------------ | ---------------------------------------------------------- |
| `/phx:intro`             | Interactive plugin tutorial (6 sections, ~5 min)           |
| `/phx:init`              | Initialize plugin in a project (auto-activation rules)     |
| `/phx:help`              | Interactive command advisor — recommends the right command |
| `/phx:quick <task>`      | Fast implementation, skip ceremony                         |
| `/phx:investigate <bug>` | Systematic bug debugging (4 parallel investigation tracks) |
| `/phx:research <topic>`  | Research Elixir topics on the web                          |
| `/phx:verify`            | Run full verification (compile, format, credo, test)       |
| `/phx:permissions`       | Scan sessions, recommend safe Bash permissions             |
| `/phx:trace <function>`  | Build call trees to trace function flow                    |
| `/phx:boundaries`        | Analyze Phoenix context boundaries with mix xref           |
| `/phx:examples`          | Practical examples and pattern walkthroughs                |
| `/ecto:constraint-debug` | Debug Ecto constraint violations                           |

### Analysis

| Command              | Description                                       |
| -------------------- | ------------------------------------------------- |
| `/ecto:n1-check`     | Detect N+1 query patterns                         |
| `/lv:assigns <file>` | Audit LiveView assigns for memory issues          |
| `/phx:techdebt`      | Find technical debt and refactoring opportunities |
| `/phx:audit`         | Full project health audit with 5 parallel agents  |
| `/phx:challenge`     | Rigorous review mode ("grill me")                 |

### Security & dependencies

| Command                      | Description                                          |
| ---------------------------- | ---------------------------------------------------- |
| `/phx:deps-audit [--base R]` | Hex supply-chain audit (8 rules + CVE + differential) |
| `/phx:deps-vet <pkg> <ver>`  | Manage the `hex_vet.exs` audit ledger (cargo-vet style) |

## Agents (22)

| Agent                        | Model  | Memory  | Role                                         |
| ---------------------------- | ------ | ------- | -------------------------------------------- |
| **workflow-orchestrator**    | opus   | project | Full cycle coordination (plan, work, review) |
| **planning-orchestrator**    | opus   | project | Parallel research agent coordination         |
| **parallel-reviewer**        | opus   | --      | 4-agent parallel code review                 |
| **deep-bug-investigator**    | sonnet | --      | 4-track parallel bug investigation           |
| **call-tracer**              | sonnet | --      | Parallel call tree tracing                   |
| **security-analyzer**        | opus   | --      | OWASP vulnerability scanning                 |
| **context-supervisor**       | haiku  | --      | Multi-agent output compression               |
| **verification-runner**      | haiku  | --      | mix compile, format, credo, test             |
| **iron-law-judge**           | sonnet | --      | Pattern-based Iron Law detection             |
| **xref-analyzer**            | haiku  | --      | Module dependency analysis                   |
| **hex-library-researcher**   | sonnet | --      | Hex.pm library evaluation                    |
| **liveview-architect**       | sonnet | --      | Component structure, streams, async patterns |
| **ecto-schema-designer**     | sonnet | --      | Migrations, data models, query patterns      |
| **phoenix-patterns-analyst** | sonnet | project | Codebase pattern discovery                   |
| **elixir-reviewer**          | sonnet | --      | Code idioms, patterns, conventions           |
| **testing-reviewer**         | sonnet | --      | ExUnit, Mox, LiveView test patterns          |
| **oban-specialist**          | sonnet | --      | Worker idempotency, error handling           |
| **otp-advisor**              | sonnet | --      | GenServer, Supervisor, process design        |
| **deployment-validator**     | sonnet | --      | Docker, Kubernetes, Fly.io config            |
| **web-researcher**           | sonnet | --      | ElixirForum, HexDocs, GitHub research        |

Agents with `project` memory build up knowledge across sessions
in `.claude/agent-memory/<agent-name>/`. Orchestrators remember
architectural decisions; pattern analysts skip redundant discovery.

## Reference Skills (Auto-Loaded)

These load automatically based on file context -- no commands needed:

| Skill                  | Triggers On                                 |
| ---------------------- | ------------------------------------------- |
| `elixir-idioms`        | OTP/BEAM code, GenServer, Supervisor, Task  |
| `phoenix-contexts`     | Context modules, router, plugs, controllers |
| `liveview-patterns`    | `*_live.ex`, mount, handle_event, streams   |
| `ecto-patterns`        | Schemas, migrations, Repo calls, changesets |
| `testing`              | `*_test.exs`, factories, test support       |
| `oban`                 | Oban workers, perform/1, queue config       |
| `security`             | Auth, sessions, CSRF/CSP, input validation  |
| `deploy`               | Dockerfile, fly.toml, runtime.exs, releases |
| `tidewave-integration` | Runtime debugging, live process inspection  |
| `intent-detection`     | First message routing to /phx: commands     |
| `compound-docs`        | Solution documentation lookups              |

## Tidewave MCP Integration

When your Phoenix app runs with [Tidewave](https://github.com/tidewave-elixir/tidewave), the plugin automatically detects it and uses runtime tools:

```elixir
# Add to mix.exs
{:tidewave, "~> 0.1", only: :dev}

# Add to endpoint.ex (in dev block)
plug Tidewave
```

Available runtime tools: execute Elixir code, run SQL queries, get docs for your exact dependency versions, introspect Ecto schemas, read application logs.

## Requirements

- Claude Code CLI
- Elixir/Phoenix project

### Optional

- **Tidewave** for runtime debugging
- **[ccrider](https://github.com/neilberkman/ccrider)** for session analysis (see Contributing)
- **Ralph Wiggum Loop** for autonomous iteration across context resets

## Contributing

PRs welcome! See [CLAUDE.md](CLAUDE.md) for full conventions.

### Quality Gate

Every PR must pass the CI quality gate (lint + test + eval). Run locally before pushing:

```bash
make help             # Show all available commands
make eval             # Quick: lint + score changed skills/agents only
make eval-all         # Full structural: all 45 skills + all 22 agents
make eval-fix         # Auto-fix lint + show failures + suggest autoresearch
make test             # 52 pytest tests for eval framework
make ci               # Full CI: lint + test + eval (same as GitHub Actions)
```

The eval framework scores skills across **8 dimensions** and agents across **5 dimensions**.
Skills must score >= 0.95 to pass. Run `make eval-all` for details.

### Development Rules

- **Skills**: ~100 lines SKILL.md + `references/` for details. Must include Iron Laws, "Use when..." in description.
- **Agents**: under 300 lines, `disallowedTools: Write, Edit, NotebookEdit` for reviewers, `permissionMode: bypassPermissions` always.
- **All markdown** passes `npm run lint`
- **New skills/agents** must pass `npm run eval` before merging
- **Autoresearch**: Run `npm run eval:fix` to auto-detect and fix quality issues

### Autoresearch (Self-Improvement Loop)

The plugin includes an internal eval framework (`lab/eval/`) that scores all skills and agents. When quality drops, the autoresearch loop can fix it:

```bash
# Score everything, show failures, get auto-fix command
npm run eval:fix

# Or run the autoresearch loop directly (targets weakest skill, fixes one issue per iteration)
claude -p 'Run autoresearch...' --allowedTools 'Edit,Read,Write,Bash,Glob,Grep'
```

The eval framework uses 24 deterministic Python matchers + haiku-based behavioral trigger testing. See `lab/eval/` for details.

### Analyze your sessions to improve the plugin

The plugin includes session analysis tools that help identify improvement opportunities.
If you use this plugin (or work on Elixir/Phoenix projects with Claude Code),
you can analyze your own sessions to find patterns that the plugin should handle better.

**Setup:**

1. Clone this repo: `git clone https://github.com/oliver-kriska/claude-elixir-phoenix.git`
2. Install [ccrider MCP](https://github.com/neilberkman/ccrider): `claude mcp add ccrider -- npx @neilberkman/ccrider`

**Available tools** (dev-only, not shipped with the plugin):

```bash
# Tier 1: Discover sessions and compute deterministic metrics
/session-scan
/session-scan --project myapp

# Tier 2: Qualitative analysis of high-signal sessions
/session-deep-dive
/session-deep-dive --date 2026-03-01

# Trends: Windowed aggregates (7d/30d/all) from metrics ledger
/session-trends
/session-trends --compare baseline
/session-trends --html out.html       # HTML report with ASCII bar charts

# Pure context-window stats (max tokens, ctx %, compaction rate) across raw JSONL
python3 .claude/skills/session-scan/references/compute-metrics.py \
  --scan-jsonl ~/.claude/projects/<project-id>/ \
  --since 2026-04-01 --html ctx-stats.html

# Skill effectiveness monitoring (requires session-scan data)
/skill-monitor                  # Dashboard: all skills
/skill-monitor --improve        # Generate improvement recommendations
```

### What session analysis finds

- **Friction points** -- where you got stuck, repeated commands, abandoned approaches
- **Workflow patterns** -- how you work (planning vs diving in, tool usage)
- **Plugin improvement opportunities** -- missing automation, skills, or Iron Laws

Each analysis report includes a **Plugin Improvement Opportunities** section that identifies:

- Manual workflows that could be automated by a new skill or hook
- Code patterns that caused bugs but the plugin doesn't catch (Iron Law candidates)
- Missing skills or agents for common tasks
- Auto-loading gaps where skills should trigger but don't

Share these findings in issues or PRs to help make the plugin better for everyone.

## Roadmap

- **elixir-inspector** (in progress) -- Separate plugin for 6-layer codebase analysis.
  Generates Credo checks, skills, CI steps, and review prompts from your project patterns.
  See the [open PR](https://github.com/oliver-kriska/claude-elixir-phoenix/pulls).
- **Tier 2/3 behavioral eval** -- Instruction-following tests and full A/B skill comparison (with-skill vs without-skill outcome quality).
- **Runtime eval integration** -- Connect session metrics to the eval framework for measuring real-world skill effectiveness.

## Sources and Inspiration

This plugin was built with insights from these articles, repositories, and tools:

### Repositories and Tools

- <https://github.com/tidewave-elixir/tidewave>
- <https://github.com/neilberkman/ccrider>
- <https://github.com/nicobailon/visual-explainer>
- <https://github.com/VoltAgent/awesome-claude-code-subagents>
- <https://github.com/shanraisshan/claude-code-best-practice>
- <https://github.com/anthropics/claude-code>
- <https://github.com/anthropics/claude-plugins-official>
- <https://github.com/anthropics/skills>
- <https://github.com/rjs/shaping-skills>
- <https://github.com/earendil-works/pi/blob/main/scripts/session-context-stats.mjs>
  (badlogic — token usage / context % metrics, per-model + per-day breakdown,
  and ASCII-bar HTML report layout borrowed for `compute-metrics.py --scan-jsonl`
  and `/session-trends --html`)
- <https://github.com/affaan-m/everything-claude-code>
- <https://github.com/blader/theorist>
- <https://github.com/tmchow/tmc-marketplace> (iterative-engineering plugin)
- <https://github.com/SamJHudson01/Carmack-Council> (persona-grounded expert council review)
- <https://github.com/obra/superpowers> (verification discipline, CSO patterns)
- <https://github.com/boshu2/agentops>

### Articles

- <https://www.codecon.sk/search-is-not-magic-with-postgresql>
- <https://peterullrich.com/complete-guide-to-full-text-search-with-postgres-and-ecto>
- <https://peterullrich.com/efficient-name-search-with-postgres-and-ecto>
- <https://elixirmerge.com/p/exploring-postgresql-search-techniques-with-elixir-and-ecto>
- <https://tidewave.ai/blog/the-future-of-coding-agents-is-vertical-integration>
- <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>
- <https://openai.com/index/harness-engineering/>
- <https://www.ignorance.ai/p/the-emerging-harness-engineering>
- <https://martinfowler.com/articles/exploring-gen-ai/harness-engineering.html>
- <https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents>
- <https://boristane.com/blog/how-i-use-claude-code/>
- <https://mitchellh.com/writing/my-ai-adoption-journey>
- <https://www.thepragmaticcto.com/p/no-vibes-allowed-context-engineering>
- <https://basecamp.com/shapeup>
- <https://pragprog.com/titles/jwpaieng/common-sense-guide-to-ai-engineering/>
- <https://allanmacgregor.com/posts/setting-up-tidewave-beam-introspection>
- <https://theengineeringmanager.substack.com/p/councils-of-agents>
- <https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling>
- <https://arxiv.org/abs/2603.03329> (AutoHarness: improving LLM agents by automatically synthesizing a code harness)
- <https://x.com/heynavtoor>

## License

MIT
