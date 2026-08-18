# Elixir Phoenix Plugin for Claude Code

[![Docs: phxagents.dev](https://img.shields.io/badge/docs-phxagents.dev-6e40c9)](https://phxagents.dev)
[![Security: scanned with SkillSpector](https://img.shields.io/badge/security-scanned%20with%20SkillSpector-2ea44f)](SECURITY.md)

**Docs: [phxagents.dev](https://phxagents.dev)** -- [install guides per runtime](https://phxagents.dev/install/),
the [runtime compatibility matrix](https://phxagents.dev/compatibility/), all
[26 Iron Laws](https://phxagents.dev/iron-laws/), and a browsable
[skill and agent catalog](https://phxagents.dev/catalog/).

**Claude Code is great. But it doesn't know that `assign_new` silently skips on reconnect, that `:float` will corrupt your money fields, or that your Oban job isn't idempotent.**

This plugin does. It coordinates **26 specialist agents** that plan, implement,
review, and verify your Elixir/Phoenix code in parallel -- each with domain
expertise, fresh context, and enforced [Iron Laws](#iron-laws-non-negotiable-rules)
that catch the bugs your tests won't.

**Using Amp?** Install the generated skills-only edition for the same 51 Elixir,
Phoenix, LiveView, Ecto, Oban, testing, and security skills. See
[Use with Amp](#use-with-amp) for the important differences from the full Claude
Code plugin, or the [Amp install guide](https://phxagents.dev/install/amp/) on
phxagents.dev.

**Using Codex?** Install the native generated skills plugin for all 51 skills,
including `$elixir-phoenix:phx-investigate` and
`$elixir-phoenix:phx-review` workflows. See
[Use with Codex](#use-with-codex) or the
[Codex install guide](https://phxagents.dev/install/codex/); a trust-gated
destructive-command safeguard is included, while custom agents are intentionally
not included and Tidewave MCP registration remains external.

**Using Pi?** Install the native generated skills package for all 51 skills,
including Pi-compatible `/skill:phx-investigate` and `/skill:phx-review`
workflows. See [Use with Pi](#use-with-pi) or the
[Pi install guide](https://phxagents.dev/install/pi/); extensions, prompt
templates, MCP, and custom agents are intentionally not included yet. Tidewave
can be used when the Pi host exposes it independently.

**Using OpenCode?** Install the generated skills-only target for all 51 skills,
including `phx-investigate` and `phx-review`. In the tested OpenCode 1.17.2 setup,
they are also available as `/phx-investigate` and `/phx-review`; the skill tool
is the portable explicit interface. See [Use with OpenCode](#use-with-opencode), the
[OpenCode guide](docs/opencode.md), or the
[OpenCode install guide](https://phxagents.dev/install/opencode/).

Compare native invocation, installation, and deliberately deferred capabilities
in the canonical [runtime support matrix](docs/runtime-support.md). Generated
skills support does not imply full Claude Code feature parity.

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
│  │    26    │    51    │   140    │    30    │    26    │           │
│  │  Agents  │  Skills  │   Refs   │Hook Regs │Iron Laws │           │
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
│    security-analyzer (opus)        /ecto:constraint-debug           │
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
│    web-researcher (haiku)          progress-tracking · block-danger │
│                                                                     │
│  ───────────────────────────────────────────────────────────        │
│  26 Iron Laws · Tidewave-aware · plan→work→verify→review→compound   │
│  github.com/oliver-kriska/claude-elixir-phoenix                     │
└─────────────────────────────────────────────────────────────────────┘
```

> **v3.0.0** -- all 51 canonical skill trees have generated distributions
> for Amp, Codex, Pi, and OpenCode. Nine core workflows are fully adapted: the
> six flagship lifecycle workflows plus `phx-trace`, `phx-audit`, and
> `phx-research`. The remaining projections preserve domain knowledge but may
> require the runtime to translate Claude-specific orchestration. Claude Code
> remains the full canonical plugin; hooks, agents, MCP, instructions, and
> workflow portability intentionally vary by runtime. See the
> [support matrix](docs/runtime-support.md) before assuming feature parity.
> [Issues](https://github.com/oliver-kriska/claude-elixir-phoenix/issues) welcome.

## Installation

### Claude Code

#### From GitHub (recommended)

```bash
# In Claude Code, add the marketplace
/plugin marketplace add oliver-kriska/claude-elixir-phoenix

# Install the plugin
/plugin install elixir-phoenix
```

Requires **Claude Code 2.1.110 or newer**. The install name stays
`elixir-phoenix`, while its public workflow commands remain `/phx:*` — Claude
Code namespaces commands by the plugin's manifest name, not its install name.
A fresh install also pulls in two small compatibility namespaces for `/ecto:*`
and `/lv:*` automatically; you do not need to install them separately. After an
update, run `/reload-plugins` before trying the commands in an already-open
session.

#### Updating from v2.x

> [!WARNING]
> **Do not run `claude plugin update` on its own.** v3 introduced two
> compatibility plugins (`ecto`, `lv`) that v2 never declared, and
> `claude plugin update` does not install dependencies a new version newly
> declares. The updated plugin then fails to load entirely — you lose all 36
> `/phx:*` commands, not just `/ecto:*` and `/lv:*`. Install the two
> compatibility plugins **first**, using the exact order below.

```bash
claude plugin marketplace update oliver-kriska
claude plugin install ecto@oliver-kriska
claude plugin install lv@oliver-kriska
claude plugin update elixir-phoenix@oliver-kriska
```

Restart Claude Code afterward. In an already-open session, `/reload-plugins`
reloads the updated skills, agents, and hooks. Confirm that `/phx:help`,
`/ecto:n1-check`, and `/lv:assigns` appear before continuing work.

##### Already updated in the wrong order?

If `claude plugin list` reports `✘ failed to load` with
`Dependency "ecto@oliver-kriska" is not installed`, install the two
compatibility plugins to recover — nothing is lost, and no reinstall is needed:

```bash
claude plugin install ecto@oliver-kriska
claude plugin install lv@oliver-kriska
```

Note that `claude plugin install elixir-phoenix@oliver-kriska` also repairs the
state, but resolves only **one** missing dependency per run, so it needs two
invocations here.

#### Commands are `/phx:*`, not `/elixir-phoenix:*`

Plugin versions before v3.0.0 shipped a manifest named `elixir-phoenix`, so
their commands resolved as `/elixir-phoenix:work` even though `/phx:init` wrote
`/phx:*` into `CLAUDE.md`. v3.0.0 renamed the manifest to `phx`, which is what
makes `/phx:*` correct. If Claude Code reports `/phx:` commands as unknown,
you are on a pre-v3 version — follow the upgrade steps above, then re-run
`/phx:init --update`.

#### Claude Code subagent compatibility

No configuration is required. Claude Code 2.1.219+ defaults to a maximum
subagent spawn depth of 3, so `/phx:full`, deep `/phx:plan`, parallel
`/phx:investigate`, and `/phx:trace` can use their nested orchestrators. Claude
Code 2.1.217–2.1.218 defaulted to depth 1; on those versions, or when you
explicitly configure depth 1–2, the workflows keep orchestration in the main
conversation and spawn leaf specialists directly. They preserve the same
decisions, artifacts, verification, and review gates; only the agent topology
changes.

To explicitly enable the full nested topology, start Claude Code with depth 3:

```bash
CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=3 claude
```

Depth 2 is sufficient for `/phx:trace`'s call-tracer alone. This must be set in
the environment that starts Claude Code; a plugin hook cannot change its parent
process environment.

> **Multi-stack tip — project-scope enable.** This plugin is opinionated for
> Elixir/Phoenix. If you work across multiple language stacks, prefer enabling
> it per-project rather than globally — drop this into `<project>/.claude/settings.json`:
>
> ```json
> { "enabledPlugins": { "elixir-phoenix@oliver-kriska": true } }
> ```
>
> Hooks self-gate on `mix.exs` presence (v2.10.1+), so global enable is safe
> — project-scoping is just a tidiness preference.

#### Companion plugin: `catchup`

The same marketplace also ships **`catchup`** — a framework-agnostic
`/catchup` return-from-absence briefing (PRs, reviews, git, Linear,
calendar → one prioritized Context Brief, including which upstream
changes touch *your* in-flight files). Independent plugin, separate
manifest, install only if you want it:

```bash
/plugin install catchup@oliver-kriska
```

See `plugins/catchup/README.md`. Not coupled to Elixir/Phoenix.

#### From Local Path (for development)

```bash
git clone https://github.com/oliver-kriska/claude-elixir-phoenix.git

# Option A: Add as local marketplace
/plugin marketplace add ./claude-elixir-phoenix
/plugin install elixir-phoenix

# Option B: Test the plugin and its command namespaces directly
claude \
  --plugin-dir ./claude-elixir-phoenix/plugins/elixir-phoenix \
  --plugin-dir ./claude-elixir-phoenix/plugins/ecto \
  --plugin-dir ./claude-elixir-phoenix/plugins/lv
```

Keep all three `--plugin-dir` arguments when testing public command
compatibility. The main directory provides `/phx:*`; the `ecto` and `lv`
directories provide the legacy `/ecto:*` and `/lv:*` aliases.

### Use with Amp

Amp can install the plugin's 51 skills from the generated Agent Skills target.
Project-local installation is recommended because it keeps the Elixir/Phoenix
guidance scoped to the repository where it applies:

```bash
# Install into one Elixir/Phoenix project
cd /path/to/your-phoenix-project
amp skill add \
  https://github.com/oliver-kriska/claude-elixir-phoenix/tree/main/targets/amp/skills \
  --target "$PWD/.agents/skills"

# Or install for every Amp workspace
amp skill add \
  https://github.com/oliver-kriska/claude-elixir-phoenix/tree/main/targets/amp/skills \
  --global
```

Amp copies skills at installation time; it does not update them automatically.
Rerun the same command with `--overwrite` to install the latest version from
`main`. Cloning this repository is only necessary for local development.

Namespaced Claude commands use hyphenated Amp names: `/phx:plan` becomes
`phx-plan`, `/ecto:n1-check` becomes `ecto-n1-check`, and so on. Start a fresh
Amp session after installation. To invoke the equivalent of `/phx:investigate`
reliably, open Amp's command palette with `Ctrl+O` (or type `/` in the CLI), run
`skill: invoke`, and select `phx-investigate`. Amp forces the selected skill to
load with your next message.

You can also name skills explicitly in a prompt, which is convenient for copied
prompts and non-interactive use:

```text
Load phx-investigate and investigate this LiveView filter reset.
```

Exact Claude-style entries such as `/phx:review` are not registered as Amp slash
commands; Amp uses its command palette and native skill invocation instead. Amp
may also select skills automatically from their descriptions, but automatic
selection is model-driven and is not guaranteed on every prompt. The Amp
edition ships skills and their bundled resources, not the Claude-specific
hooks, custom agents, permission settings, or MCP setup. Read the complete
[Amp installation and usage guide](docs/amp.md) for verification, updates,
skill precedence, examples, troubleshooting, and the portability matrix.

### Use with Codex

Codex installs the generated target as a native skills plugin. Registration and
installation are separate steps:

```bash
codex plugin marketplace add oliver-kriska/claude-elixir-phoenix --ref main
codex plugin add elixir-phoenix@oliver-kriska
codex plugin list
```

Start a fresh Codex session, then invoke workflows explicitly with
`$elixir-phoenix:phx-investigate` or `$elixir-phoenix:phx-review`, browse them
with `/skills`, or let Codex select a relevant skill from its description. Codex
namespaces plugin skills; unqualified `$phx-investigate` is not an explicit
alias. This edition also ships one synchronous native hook that blocks destructive
Ecto resets/drops, unguarded force pushes, and accidental `MIX_ENV=prod mix`
commands. Codex requires users to review and trust plugin hooks before they run;
the skills work without it. Custom agents, plugin-root instructions, the remaining
Claude hooks remain deferred; Tidewave MCP registration is external. See the
complete [Codex guide](docs/codex.md) for updates, uninstall, isolation,
troubleshooting, tested version, and capability details.

### Use with Pi

Install the repository as a Pi package globally, or add `-l` to scope it to the
current project:

```bash
pi install git:github.com/oliver-kriska/claude-elixir-phoenix
pi list
```

Start a fresh Pi session, then invoke workflows explicitly with
`/skill:phx-investigate` or `/skill:phx-review`. Pi can also select a skill from
its description automatically. This edition ships skills and their complete
bundled resources only—not extensions, prompt templates, custom agents,
or package-root instructions. Tidewave MCP registration is external. See the
complete [Pi guide](docs/pi.md) for project-local installation, updates,
uninstall, isolation, troubleshooting, tested version, and capability details.

### Use with OpenCode

OpenCode 1.17.2 discovers the generated skills recursively. Install a sparse
checkout into one project (recommended) or the global OpenCode config root:

```bash
git clone --filter=blob:none --sparse https://github.com/oliver-kriska/claude-elixir-phoenix.git .opencode/skills/elixir-phoenix
git -C .opencode/skills/elixir-phoenix sparse-checkout set targets/opencode
```

Start a fresh session and explicitly say “Use the skill tool to load the
phx-investigate skill, then …”. In the tested OpenCode 1.17.2 setup,
`/phx-investigate` and `/phx-review` also work when they do not collide with
existing commands, but the skill tool is the documented portable interface. OpenCode
selects the model implicitly. This target contains skills and complete bundled
resources only—not hooks or custom agents. Tidewave MCP registration is
external. Investigation, review, plan, work, PR-review, and full-lifecycle
workflows are explicitly adapted; some other skills may still describe optional
Claude-specific orchestration APIs. See the
[OpenCode installation and support guide](docs/opencode.md) for global setup,
updates, uninstall, feature-branch review, discovery debugging, and limitations.

## Getting Started

The remainder of this README describes the full Claude Code plugin and uses
Claude Code `/phx:*`, `/ecto:*`, and `/lv:*` syntax. For generated runtimes,
translate invocations using the runtime guide: Amp uses `skill: invoke`, Codex
uses `$elixir-phoenix:<skill>`, Pi uses `/skill:<name>`, and OpenCode uses its
skill tool. Generated editions do not install Claude Code's complete custom
agent, lifecycle-hook, permission, or MCP configuration.

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

The plugin uses 26 agents organized into 3 tiers:

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
**Specialists** (sonnet) -- Domain experts, secondary orchestrators, judgment-heavy tasks. `sonnet` resolves to Sonnet 5 (CC's default, 1M context) -- near-opus quality at sonnet pricing.
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
/phx:learn-from-fix --library ical --scope personal ICal.to_ics output needs CRLF line endings
```

This stores verified general lessons in personal `~/.claude/CLAUDE.md`, project
instructions, or project-keyed memory.
The library route creates or safely updates native background knowledge at
`~/.claude/skills/hex-<package>/SKILL.md` (personal) or
`.claude/skills/hex-<package>/SKILL.md` (project). Claude selects it from its
description; dependency presence alone does not guarantee activation. Cached
plugin files are never modified.

## Iron Laws (Non-Negotiable Rules)

The plugin enforces critical rules and **stops with an explanation** if code would violate them:

**LiveView:** No database queries in disconnected mount. Use streams for lists >100 items. Check `connected?/1` before PubSub subscribe.

**Ecto:** Never use `:float` for money. Always pin values with `^` in queries. Separate queries for `has_many`, JOIN for `belongs_to`.

**Oban:** Jobs must be idempotent. Args use string keys. Never store structs in args.

**Security:** No `String.to_atom` with user input. Authorize in every LiveView
`handle_event`. Treat forms, hooks, and `phx-value-*` as user-controlled. IDs
rendered in HTML or event payloads are public identifiers, not proof of access.
Never use `raw/1` with untrusted content.

**Deployment:** Keep core release secrets required, but gate credentials for
optional services behind the feature that enables them. `runtime.exs` also runs
when an `eval`-based migration boots the release, so unconditional S3 or Redis
requirements can break unrelated migrations.

**OTP:** No process without a runtime reason. Supervise all long-lived processes.

**Elixir:** Declare `@external_resource` for compile-time files. Wrap third-party library APIs behind project-owned modules. Never use `assign_new` for values refreshed every mount.

**Code style:** Comments aren't commit messages — a change's reasoning goes in the commit/PR, not the code. No issue-reference tags inline (`# ENA-1234`).

## Commands Reference

### Workflow

| Command                 | Description                                                  |
| ----------------------- | ------------------------------------------------------------ |
| `/phx:full <feature>`   | Full autonomous cycle (plan, work, verify, review, compound); `--codex` adds a cross-model review track |
| `/phx:brainstorm <topic>` | Adaptive requirements gathering before planning            |
| `/phx:plan <input>`     | Create implementation plan with specialist agents            |
| `/phx:plan --existing`  | Enhance existing plan with deeper research                   |
| `/phx:work <plan-file>` | Execute plan tasks with verification                         |
| `/phx:review [focus]`   | Multi-agent code review (4 parallel agents)                  |
| `/phx:compound`         | Capture solved problem as reusable knowledge                 |
| `/phx:triage`           | Interactive triage of review findings                        |
| `/phx:document`         | Generate @moduledoc, @doc, README, ADRs                      |
| `/phx:learn-from-fix [--library <pkg> --scope personal\|project] <lesson>` | Capture verified general or package lessons |
| `/phx:brief <plan>`     | Interactive plan walkthrough                                 |
| `/phx:perf`             | Performance analysis with specialist agents                  |
| `/phx:pr-review`        | Address PR review threads — fetch, fix, reply, resolve       |
| `/phx:watch-pr <PR#>`   | Background-watch a PR for reviews + CI; `--codex` adds a Codex cloud review loop |
| `/phx:codex-loop`       | Fix until Codex CLI review is clean (optional, needs codex)  |

### Utility

| Command                  | Description                                                |
| ------------------------ | ---------------------------------------------------------- |
| `/phx:intro`             | Interactive plugin tutorial (6 sections, ~5 min)           |
| `/phx:init`              | Initialize plugin in a project (auto-activation rules)     |
| `/phx:help`              | Interactive command advisor — recommends the right command |
| `/phx:quick <task>`      | Fast implementation, skip ceremony                         |
| `/phx:investigate <bug>` | Systematic bug debugging (4 parallel investigation tracks) |
| `/phx:research <topic>`  | Research Elixir topics on the web                          |
| `/phx:verify`            | Run full verification (compile, format, credo, test — plus dialyzer when configured) |
| `/phx:permissions`       | Scan sessions, recommend safe Bash permissions             |
| `/phx:trace <function>`  | Build call trees to trace function flow                    |
| `/phx:boundaries`        | Analyze Phoenix context boundaries with mix xref           |
| `/phx:examples`          | Practical examples and pattern walkthroughs                |
| `/phx:recall <question>` | Recall prior work — solution docs, git history, sessions   |
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
| `/phx:deps-update`           | Bump outdated Hex deps — changelogs, coupled groups, grouped PRs |
| `/phx:deps-audit [--base R]` | Hex supply-chain audit (8 rules + CVE + differential) |
| `/phx:deps-vet <pkg> <ver>`  | Manage the `hex_vet.exs` audit ledger (cargo-vet style) |

## Agents (26)

| Agent                        | Model  | Memory  | Role                                         |
| ---------------------------- | ------ | ------- | -------------------------------------------- |
| **workflow-orchestrator**    | opus   | project | Full cycle coordination (plan, work, review) |
| **planning-orchestrator**    | opus   | project | Parallel research agent coordination         |
| **parallel-reviewer**        | opus   | --      | 4-agent parallel code review                 |
| **deep-bug-investigator**    | opus   | --      | 4-track parallel bug investigation           |
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
| **web-researcher**           | haiku  | --      | ElixirForum, HexDocs, GitHub research        |
| **ash-resource-designer**    | sonnet | --      | Ash resource design (the "Ash Way")          |
| **ash-policy-reviewer**      | sonnet | --      | Ash policy authorization audit               |
| **ash-query-optimizer**      | sonnet | --      | Ash N+1 loads, aggregates vs load            |
| **requirements-verifier**    | sonnet | --      | Implementation vs task-requirement check     |
| **hex-deps-triager**         | sonnet | --      | Hex supply-chain audit finding triage        |
| **codex-reviewer**           | haiku  | --      | Codex CLI bridge — cross-model review (opt.) |

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
| `security`             | Auth, event trust, CSRF/CSP, input validation |
| `deploy`               | Dockerfile, runtime config, releases        |
| `tidewave-integration` | Runtime debugging, live process inspection  |
| `intent-detection`     | First message routing to /phx: commands     |
| `compound-docs`        | Solution documentation lookups              |

## Tidewave MCP Integration

When your Phoenix app runs with
[Tidewave](https://github.com/tidewave-ai/tidewave_phoenix), the plugin detects
the local server and prefers its runtime tools. Add Tidewave to the application:

```elixir
# Add to mix.exs
{:tidewave, "~> 0.6", only: :dev}

# Add to endpoint.ex (in dev block)
plug Tidewave
```

Then register the running endpoint with Claude Code, replacing `$PORT` with the
Phoenix port:

```bash
claude mcp add --transport http tidewave \
  http://localhost:$PORT/tidewave/mcp
```

Use `/mcp` to verify the connection. The plugin does not silently register a
fixed-port MCP endpoint. Once connected, Tidewave can execute Elixir code, run
SQL queries, get documentation for exact dependency versions, introspect Ecto
schemas, and read application logs.

## Requirements

- Claude Code CLI
- Elixir/Phoenix project

### Optional

- **Tidewave** for runtime debugging
- **[ccrider](https://github.com/neilberkman/ccrider)** for session analysis (see Contributing)
- **Ralph Wiggum Loop** for autonomous iteration across context resets
- **[OpenAI Codex](https://developers.openai.com/codex)** as an external reviewer:
  `/phx:review --codex`, `/phx:full --codex`, and `/phx:codex-loop` use the
  local codex CLI; `/phx:watch-pr --codex` uses the Codex GitHub connector.
  Install the shared Elixir review rubric into AGENTS.md via `/phx:init`. Users
  without codex are unaffected — all codex behavior is flag-gated

## Security

This plugin runs skills, agents, and hooks inside Claude Code with your tool
permissions, so it ships a verifiable security posture:

- **Independently scanned** with [NVIDIA SkillSpector](https://github.com/NVIDIA/SkillSpector)
  (static analysis, **zero covert-egress findings**): **66 / 77 components SAFE**, 7 CAUTION,
  4 DO_NOT_INSTALL raw. The four DO_NOT_INSTALL components are documented false
  positives with reviewed baselines, so **after baselines 0 remain and the scan
  gate passes** (the 7 CAUTION-tier components stay documented). A static scanner
  flags the *safety-enforcing* and *security-auditing* skills precisely because
  they name dangerous patterns in order to forbid or detect them (e.g. the line
  literally reads `NEVER bypass security checks for speed`).
- **No telemetry or covert egress**; workflows can make visible, user-authorized
  GitHub, Hex, web-search, or configured MCP calls through the host runtime.
  Review agents are read-only by default (source edits disallowed), and the
  Bash hooks are auditable in `plugins/elixir-phoenix/hooks/`.

Full report, line-by-line triage, and a reproduce-it-yourself command live in
**[SECURITY.md](SECURITY.md)**. Re-run the scan anytime with `make security`.

## Contributing

PRs welcome! See [CLAUDE.md](CLAUDE.md) for full conventions.

### Quality Gate

Every PR must pass the CI quality gate (lint + test + eval). Run locally before pushing:

```bash
make help             # Show all available commands
make eval             # Quick: lint + score changed skills/agents only
make eval-all         # Full structural: all 51 skills + all 26 agents
make eval-fix         # Auto-fix lint + show failures + suggest autoresearch
make test             # Pytest suites for the eval framework and port tooling
make generated-skills-sync # Regenerate and verify all four runtime targets
make ci               # Full CI: lint + test + validate + eval + security (same as GitHub Actions)
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

The eval framework uses 24 deterministic Python matchers plus a separate,
fresh Haiku behavioral gate. `make eval-full` requires every skill to reach 75%
trigger accuracy; ignored local result caches never affect structural CI. See
`lab/eval/` for details.

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

- <https://github.com/tidewave-ai/tidewave_phoenix>
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
- <https://pragprog.com/titles/jwpaieng/a-common-sense-guide-to-ai-engineering/>
- <https://allanmacgregor.com/posts/setting-up-tidewave-beam-introspection>
- <https://theengineeringmanager.substack.com/p/councils-of-agents>
- <https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling>
- <https://arxiv.org/abs/2603.03329> (AutoHarness: improving LLM agents by automatically synthesizing a code harness)
- <https://x.com/heynavtoor>

## License

MIT
