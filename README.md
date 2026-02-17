# Elixir Phoenix Plugin for Claude Code

> **Early Stage** -- This plugin is under active development. Features may change, and rough edges are expected. Feedback and contributions welcome via [issues](https://github.com/oliver-kriska/claude-elixir-phoenix/issues).

A Claude Code plugin for Elixir/Phoenix/LiveView development with **agentic workflow orchestration**, 20 specialist agents, and Tidewave MCP integration.

Instead of a single AI assistant doing everything in one context window,
this plugin coordinates specialist agents that work in parallel -- each
with its own fresh context, domain expertise, and focused task. The result:
deeper analysis, fewer hallucinations, and no context exhaustion on large features.

## Installation

### From GitHub (recommended)

```bash
# In Claude Code, add the marketplace
/plugin marketplace add oliver-kriska/claude-elixir-phoenix

# Install the plugin
/plugin install elixir-phoenix
```

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

It walks through the workflow, commands, and features in 4 short sections (~3 min).
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

The plugin implements a **Plan, Work, Review, Compound** lifecycle. Each phase produces artifacts in a namespaced directory:

```
/phx:plan → /phx:work → /phx:review → /phx:compound
     │           │            │              │
     ↓           ↓            ↓              ↓
plans/{slug}/  (in namespace) (in namespace) solutions/
```

- **Plan** -- Research agents analyze your codebase in parallel, then synthesize a structured implementation plan
- **Work** -- Execute the plan task-by-task with automatic verification after each change
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

The plugin uses 20 agents organized into 3 tiers:

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

Runs the complete cycle: plan (with research), work, review. Cycles back automatically if review finds issues. Captures learnings on completion.

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
/phx:learn Fixed N+1 query -- always preload associations in context functions
```

This updates the plugin's `common-mistakes.md` knowledge base so the same mistake is prevented in future sessions.

## Iron Laws (Non-Negotiable Rules)

The plugin enforces critical rules and **stops with an explanation** if code would violate them:

**LiveView:** No database queries in disconnected mount. Use streams for lists >100 items. Check `connected?/1` before PubSub subscribe.

**Ecto:** Never use `:float` for money. Always pin values with `^` in queries. Separate queries for `has_many`, JOIN for `belongs_to`.

**Oban:** Jobs must be idempotent. Args use string keys. Never store structs in args.

**Security:** No `String.to_atom` with user input. Authorize in every LiveView `handle_event`. Never use `raw/1` with untrusted content.

**OTP:** No process without a runtime reason.

## Commands Reference

### Workflow

| Command                 | Description                                          |
| ----------------------- | ---------------------------------------------------- |
| `/phx:full <feature>`   | Full autonomous cycle (plan, work, review, compound) |
| `/phx:plan <input>`     | Create implementation plan with specialist agents    |
| `/phx:plan --existing`  | Enhance existing plan with deeper research           |
| `/phx:work <plan-file>` | Execute plan tasks with verification                 |
| `/phx:review [focus]`   | Multi-agent code review (4 parallel agents)          |
| `/phx:compound`         | Capture solved problem as reusable knowledge         |
| `/phx:triage`           | Interactive triage of review findings                 |
| `/phx:document`         | Generate @moduledoc, @doc, README, ADRs              |
| `/phx:learn <lesson>`   | Capture lessons learned                              |

### Utility

| Command                  | Description                                                |
| ------------------------ | ---------------------------------------------------------- |
| `/phx:intro`             | Interactive plugin tutorial (4 sections, ~3 min)           |
| `/phx:init`              | Initialize plugin in a project (auto-activation rules)     |
| `/phx:quick <task>`      | Fast implementation, skip ceremony                         |
| `/phx:investigate <bug>` | Systematic bug debugging (4 parallel investigation tracks) |
| `/phx:research <topic>`  | Research Elixir topics on the web                          |
| `/phx:verify`            | Run full verification (compile, format, credo, test)       |
| `/phx:trace <function>`  | Build call trees to trace function flow                    |
| `/phx:boundaries`        | Analyze Phoenix context boundaries with mix xref           |

### Analysis

| Command              | Description                                       |
| -------------------- | ------------------------------------------------- |
| `/ecto:n1-check`     | Detect N+1 query patterns                         |
| `/lv:assigns <file>` | Audit LiveView assigns for memory issues          |
| `/phx:techdebt`      | Find technical debt and refactoring opportunities |
| `/phx:audit`         | Full project health audit with 5 parallel agents  |
| `/phx:challenge`     | Rigorous review mode ("grill me")                 |

## Agents (20)

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

| Skill               | Triggers On                             |
| ------------------- | --------------------------------------- |
| `elixir-idioms`     | Any `.ex`/`.exs` file                   |
| `phoenix-contexts`  | Context modules, `lib/*/[a-z]*.ex`      |
| `liveview-patterns` | `*_live.ex`, `*_component.ex`           |
| `ecto-patterns`     | Migrations, schemas, `from(` queries    |
| `testing`           | `*_test.exs` files                      |
| `oban`              | `*_worker.ex`, `use Oban.Worker`        |
| `security`          | Auth, session, password code            |
| `deploy`            | `Dockerfile`, `fly.toml`, `runtime.exs` |

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

PRs welcome! See [CLAUDE.md](CLAUDE.md) for development conventions.

### Development rules

- Skills: ~100 lines SKILL.md + `references/` for details
- Agents: under 300 lines, `disallowedTools` for reviewers
- All markdown passes `npm run lint`

### Analyze your sessions to improve the plugin

The plugin includes session analysis tools that help identify improvement opportunities.
If you use this plugin (or work on Elixir/Phoenix projects with Claude Code),
you can analyze your own sessions to find patterns that the plugin should handle better.

**Setup:**

1. Clone this repo: `git clone https://github.com/oliver-kriska/claude-elixir-phoenix.git`
2. Install [ccrider MCP](https://github.com/neilberkman/ccrider): `claude mcp add ccrider -- npx @neilberkman/ccrider`

**Available tools** (dev-only, not shipped with the plugin):

```bash
# Browse and search your sessions
/find-sessions
/find-sessions "LiveView errors"
/find-sessions --project myapp

# Analyze a specific session
/analyze-session abc12345
/analyze-session --last

# Full pipeline: search + analyze + synthesize
/session-insights "all my Elixir Phoenix sessions"
/session-insights --project myapp
/session-insights "debugging sessions" --after 2026-01-15

# Batch analysis (Python-based, for large-scale analysis)
/analyze-sessions 20 --synthesize
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

## Sources and Inspiration

This plugin was built with insights from these articles, repositories, and tools:

- <https://github.com/tidewave-elixir/tidewave>
- <https://tidewave.ai/blog/the-future-of-coding-agents-is-vertical-integration>
- <https://github.com/neilberkman/ccrider>
- <https://github.com/VoltAgent/awesome-claude-code-subagents>
- <https://github.com/shanraisshan/claude-code-best-practice>
- <https://github.com/anthropics/claude-code>
- <https://github.com/anthropics/claude-plugins-official>
- <https://basecamp.com/shapeup>
- <https://pragprog.com/titles/jwpaieng/common-sense-guide-to-ai-engineering/>
- <https://allanmacgregor.com/posts/setting-up-tidewave-beam-introspection>
- <https://theengineeringmanager.substack.com/p/councils-of-agents>
- <https://x.com/heynavtoor>

## License

MIT
