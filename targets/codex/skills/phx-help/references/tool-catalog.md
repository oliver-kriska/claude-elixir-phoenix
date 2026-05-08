# Tool Catalog — Complete Command Reference

Full catalog of all plugin commands, skills, and agents for `/phx:help` routing.

## Workflow Commands (the main cycle)

These commands form a connected pipeline — each reads the previous phase's output.

### `/phx:brainstorm <topic>` — Adaptive requirements gathering

- **When**: Vague idea, unclear scope, want to explore before planning
- **Input**: Topic or feature idea (can be very rough)
- **Output**: `.claude/plans/{slug}/interview.md` with structured requirements
- **Next step**: `/phx:plan` (detects interview.md, skips clarification)
- **Agents used**: phoenix-patterns-analyst, web-researcher (research phase only)

**When to use brainstorm vs plan:**

| Signal | Use |
|--------|-----|
| Clear feature, know what you want | `/phx:plan` directly |
| Vague idea, exploring options | `/phx:brainstorm` |
| Multiple possible approaches | `/phx:brainstorm` (research phase) |
| Requirements unclear, need to discuss | `/phx:brainstorm` |

### `/phx:plan <description>` — Create implementation plan

- **When**: New feature, multi-file change, anything needing structure
- **Input**: Feature description in natural language (or brainstorm interview.md)
- **Output**: `.claude/plans/{slug}/plan.md` with checkboxed tasks
- **Flags**: `--depth quick|standard|deep`, `--existing` (enhance existing plan)
- **Next step**: `/phx:work .claude/plans/{slug}/plan.md`
- **Agents used**: planning-orchestrator, research agents

### `/phx:brief <plan-path>` — Interactive plan walkthrough

- **When**: Want to understand a plan before working on it
- **Input**: Path to a plan.md file
- **Output**: Ephemeral (conversation only, no files)
- **Next step**: `/phx:work` or `/phx:plan --existing` to enhance

### `/phx:work <plan-path>` — Execute plan tasks

- **When**: Ready to implement a plan
- **Input**: Path to plan.md with checkboxed tasks
- **Output**: Code changes, updated checkboxes, `progress.md`
- **Flags**: `--continue` (resume from last checkpoint)
- **Next step**: `/phx:review`

### `/phx:review` — Parallel code review

- **When**: Implementation done, want quality check before merging
- **Input**: Git diff (changed files)
- **Output**: `.claude/plans/{slug}/reviews/{feature}-review.md`
- **Agents used**: 3-5 specialist reviewers in parallel
- **Next step**: Fix issues, then `/phx:compound` for lessons learned

### `/phx:triage` — Interactive review triage

- **When**: Review has many findings, need to prioritize
- **Input**: Review file from `/phx:review`
- **Output**: Prioritized action list

### `/phx:compound` — Capture solved problem

- **When**: Just solved a tricky bug or pattern worth remembering
- **Input**: Description of what was solved
- **Output**: `.claude/solutions/{category}/{fix}.md`
- **Why**: Builds searchable knowledge base for future sessions

### `/phx:full <description>` — Autonomous full cycle

- **When**: Large feature, want plan→work→verify→review in one shot
- **Input**: Feature description
- **Output**: All workflow artifacts
- **Caution**: Best for well-defined features; complex ones benefit from manual phase control

## Standalone Commands

### `/phx:quick <description>` — Fast implementation

- **When**: Small change (<50 lines), single file, clear scope
- **Input**: What to change
- **Output**: Direct code changes (no plan artifacts)
- **Examples**: "Add phone field to User schema", "Fix pagination bug in index"

### `/phx:investigate` — Bug investigation

- **When**: Error, crash, unexpected behavior, failing test
- **Input**: Bug description or stack trace
- **Output**: Root cause analysis, fix suggestion
- **Agents used**: deep-bug-investigator (for complex bugs)
- **Checks**: `.claude/solutions/` first for known fixes

### `/phx:verify` — Run all checks

- **When**: Before PR, before deploy, after large changes
- **Runs**: `mix compile --warnings-as-errors`, `mix format`, `mix credo`, `mix test`
- **Output**: Pass/fail report

### `/phx:research <topic>` — Research with parallel workers

- **When**: "How to implement X", "Best practices for Y", "What library for Z"
- **Flags**: `--library <name>` (evaluate a specific Hex package)
- **Output**: Research summary with sources
- **Agents used**: 1-3 web-researcher agents in parallel

### `/phx:pr-review` — Address PR review comments

- **When**: Got review comments on a PR, need to address them
- **Input**: PR number or URL
- **Output**: Code changes addressing each comment

### `/phx:intro` — Interactive plugin tutorial

- **When**: New to the plugin, want to learn what's available
- **Flags**: `--section N` (jump to section 1-6)

### `/phx:init` — Project setup

- **When**: Setting up plugin rules for a new project
- **Output**: Injects rules into project CLAUDE.md

### `/phx:permissions` — Permission analyzer

- **When**: Too many "allow?" prompts, permission fatigue, after 5+ prompts in a session
- **Input**: Optional `--days=N` (default: 14), `--dry-run`
- **Output**: Scans session JSONL files for uncovered Bash commands, recommends `settings.json` changes
- **Triage**: Interactive GREEN/YELLOW/RED triage with AskUserQuestion

- **When**: "Fix all credo issues", "improve coverage", "reduce warnings", measurable metric
- **Input**: Target metric and optional strategy
- **Output**: Iterative improvement loop with automatic rollback on failure

### `/phx:challenge` — Rigorous review mode

- **When**: "Grill me", "challenge this", want thorough scrutiny before merging
- **Input**: Changed files (like review)
- **Output**: Aggressive questioning of Ecto changes, LiveView events, PR readiness

### `/phx:document` — Documentation generator

- **When**: Need @moduledoc, @doc annotations, or README updates
- **Input**: Modules or contexts to document
- **Output**: Inline documentation in source files

### `/phx:examples` — Pattern walkthroughs

- **When**: "How do I...", "show me an example of...", learning patterns
- **Input**: Pattern or topic description
- **Output**: Practical examples with working code

### `/ecto:constraint-debug` — Constraint violation debugger

- **When**: unique_constraint, foreign_key_constraint, or check_constraint errors
- **Input**: Error message or constraint name
- **Output**: Traces triggers, checks migrations, finds duplicate data

## Analysis Commands

### `/phx:perf` — Performance analysis

- **When**: "App is slow", "queries are slow", "LiveView is laggy"
- **Covers**: Ecto queries, LiveView renders, OTP bottlenecks

### `/ecto:n1-check` — N+1 query detection

- **When**: Suspect N+1 queries, list pages are slow
- **Output**: Found N+1 patterns with fix suggestions

### `/lv:assigns` — LiveView memory audit

- **When**: LiveView processes using too much memory, large assigns
- **Output**: Assigns size analysis, stream conversion suggestions

### `/phx:audit` — Project health audit

- **When**: Want overall project quality assessment
- **Agents used**: 5 specialist agents in parallel
- **Output**: `.claude/audit/reports/` with findings per area

### `/phx:techdebt` — Technical debt analysis

- **When**: Want to identify and track technical debt
- **Output**: Categorized debt items with severity

### `/phx:boundaries` — Context boundary violations

- **When**: Suspect cross-context coupling, unclear module boundaries
- **Output**: Boundary violation report

### `/phx:trace <function>` — Call chain tracing

- **When**: Need to understand how a function is called and what it calls
- **Agents used**: call-tracer, xref-analyzer

## Decision Helpers

### When to use `/phx:plan` vs `/phx:quick`

| Signal | Use |
|--------|-----|
| 1-2 files, clear change | `/phx:quick` |
| 3+ files or unclear scope | `/phx:plan` |
| New domain concept | `/phx:plan` |
| "Add field to schema" | `/phx:quick` |
| "Add notification system" | `/phx:plan` |

### When to use `/phx:investigate` vs just fixing

| Signal | Use |
|--------|-----|
| Know the cause, small fix | Fix directly |
| Stack trace, unknown cause | `/phx:investigate` |
| Intermittent / race condition | `/phx:investigate` |
| Test failing, obvious assertion | Fix directly |

### When to use `/phx:full` vs manual phases

| Signal | Use |
|--------|-----|
| Well-defined feature, clear scope | `/phx:full` |
| Exploratory, may pivot | `/phx:plan` then decide |
| Want control between phases | Manual: plan → work → review |
| Large feature, new domain | `/phx:full` (handles complexity) |

### When to use `/phx:review` vs `/phx:verify`

| Signal | Use |
|--------|-----|
| Want compile/test/format pass | `/phx:verify` |
| Want architectural feedback | `/phx:review` |
| Pre-PR checklist | Both: `/phx:verify` then `/phx:review` |

## Reference Skills (auto-loaded, not invoked directly)

These load automatically when you edit matching files:

| Skill | Triggers on |
|-------|-------------|
| `liveview-patterns` | `*_live.ex`, `*_component.ex`, `*.sface` |
| `ecto-patterns` | Migrations, schemas, changesets, `from(` |
| `phoenix-contexts` | Context modules, router, controllers |
| `security` | Auth files, session, password |
| `testing` | `*_test.exs`, factories, fixtures |
| `oban` | Workers, `use Oban.Worker` |
| `elixir-idioms` | GenServer, mix tasks, general `.ex` |
| `deploy` | Dockerfile, fly.toml, runtime.exs |

## Workflow Cheat Sheet

```text
New feature:     /phx:plan → /phx:work → /phx:review → /phx:compound
Quick fix:       /phx:quick
Bug:             /phx:investigate
Full auto:       /phx:full
Pre-PR:          /phx:verify → /phx:review
Research:        /phx:research [topic]
Evaluate lib:    /phx:research --library [name]
Resume work:     /phx:work --continue
Post-fix lesson: /phx:compound
Permissions:     /phx:permissions
```
