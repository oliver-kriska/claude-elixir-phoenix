# Plugin Development Guide

Development documentation for the Elixir/Phoenix Claude Code plugin.

## Overview

This plugin provides **agentic workflow orchestration** with specialist agents and reference skills for Elixir/Phoenix/LiveView development.

## Workflow Architecture

The plugin implements a **Plan → Work → Review → Compound** lifecycle:

```
/phx:plan → /phx:work → /phx:review → /phx:compound
     │           │            │              │
     ↓           ↓            ↓              ↓
plans/{slug}/  (in namespace) (in namespace) solutions/
```

> **Migration note**: The `--depth` flag replaces the old
> `--detail` flag. Use `quick|standard|deep` instead of
> `minimal|more|comprehensive`.

**Key principle**: Filesystem is the state machine. Each phase reads from previous phase's output. Solutions feed back into future cycles.

### Workflow Commands

| Command | Phase | Input | Output |
|---------|-------|-------|--------|
| `/phx:plan` | Planning | Feature description | `plans/{slug}/plan.md` |
| `/phx:plan --existing` | Enhancement | Plan file | Enhanced plan with research |
| `/phx:work` | Execution | Plan file | Updated checkboxes, `plans/{slug}/progress.md` |
| `/phx:review` | Quality | Changed files | `plans/{slug}/reviews/` |
| `/phx:compound` | Knowledge | Solved problem | `solutions/{category}/{fix}.md` |
| `/phx:full` | All | Feature description | Complete cycle with compounding |

### Artifact Directories

Each plan owns all its artifacts in a namespace directory:

```
.claude/
├── plans/{slug}/              # Everything for ONE plan
│   ├── plan.md                # The plan itself
│   ├── research/              # Research agent output
│   ├── reviews/               # Review agent output (individual tracks)
│   ├── summaries/             # Context-supervisor compressed output
│   ├── progress.md            # Progress log
│   └── scratchpad.md          # Auto-written decisions, dead-ends, handoffs
├── audit/                     # Audit namespace (not plan-specific)
│   ├── reports/               # 5 specialist agent outputs
│   └── summaries/             # Supervisor compressed output
├── reviews/                   # Fallback for ad-hoc reviews (no plan)
└── solutions/{category}/      # Global compound knowledge (unchanged)
    ├── ecto-issues/
    ├── liveview-issues/
    └── ...
```

### Context Supervisor Pattern

Orchestrators that spawn multiple sub-agents use a generic
`context-supervisor` (haiku) to compress worker output before
synthesis. This prevents context exhaustion in the parent:

```
Orchestrator (thin coordinator)
  └─► context-supervisor reads N worker output files
      └─► writes summaries/consolidated.md
          └─► Orchestrator reads only the summary
```

Used by: planning-orchestrator, parallel-reviewer, audit skill, docs-validation-orchestrator.

## Structure

```
claude-elixir-phoenix/
├── .claude-plugin/
│   └── marketplace.json
├── .claude/                         # Contributor tooling (NOT distributed)
│   ├── agents/
│   │   ├── phoenix-project-analyzer.md  # Analyze external codebases
│   │   └── docs-validation-orchestrator.md  # Plugin docs compatibility
│   ├── commands/
│   │   ├── psql-query.md
│   │   └── techdebt.md
│   └── skills/
│       ├── docs-check/              # /docs-check — validate against Claude Code docs
│       ├── find-sessions/
│       ├── analyze-session/
│       └── session-insights/
├── scripts/
│   └── fetch-claude-docs.sh         # Download Claude Code docs for validation
├── plugins/
│   └── elixir-phoenix/
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── agents/                  # 20 specialist agents
│       │   ├── workflow-orchestrator.md   # Full cycle coordination
│       │   ├── planning-orchestrator.md
│       │   ├── context-supervisor.md     # Generic output compressor (haiku)
│       │   └── ...
│       ├── hooks/
│       │   └── hooks.json           # Format, progress tracking, Stop warning
│       └── skills/                  # 33 skills
│           ├── work/                # Execution phase
│           ├── full/                # Autonomous cycle
│           ├── plan/                # Planning + deepening (--existing)
│           ├── review/              # Enhanced: Todo creation
│           ├── compound/            # Knowledge capture phase
│           ├── compound-docs/       # Solution documentation system
│           ├── investigate/
│           └── ...
├── CLAUDE.md
└── README.md
```

## Conventions

### Agents

Agents are specialist reviewers that analyze code without modifying it.

**Frontmatter:**

```yaml
---
name: my-agent
description: Description with "Use proactively when..." guidance
tools: Read, Grep, Glob, Bash
disallowedTools: Write, Edit, NotebookEdit
permissionMode: bypassPermissions
model: sonnet
memory: project
skills:
  - relevant-skill
---
```

**Rules:**

- Use `sonnet` model by default (Sonnet 4.6 achieves near-opus quality at lower cost)
- Use `opus` for primary workflow orchestrators and security-critical agents only
- Use `sonnet` for secondary orchestrators (investigation, tracing) and judgment-heavy tasks
- Use `haiku` for mechanical tasks: compression, verification, dependency analysis
- Review agents are **read-only** (`disallowedTools: Write, Edit, NotebookEdit`)
- Use `permissionMode: bypassPermissions` for all agents — `default` causes "Bash command permission check failed"
  when agents run in background (safety system scans skill content for shell-like patterns)
- Use `memory: project` for agents that benefit from cross-session learning (orchestrators, pattern analysts).
  Note: `memory` auto-enables Read, Write, Edit — only add to agents that already have Write access
- Preload relevant skills via `skills:` field
- Keep under 300 lines

### Skills

Skills provide domain knowledge with progressive disclosure.

**Structure:**

```
skills/{name}/
├── SKILL.md           # ~100 lines max
└── references/        # Detailed content
    └── *.md
```

**Rules:**

- SKILL.md: ~100 lines max (~500 tokens)
- Include "Iron Laws" section for critical rules
- Move detailed examples to `references/`
- No `triggers:` field (use `description` for auto-loading)

### Workflow Skills

Workflow skills (plan, work, review, compound, full) have special structure:

- Define clear input/output artifacts
- Reference other workflow phases
- Include integration diagram showing position in cycle
- Document state transitions

### Compound Knowledge Skills

The compound system captures solved problems as searchable institutional knowledge:

- `compound-docs` — Schema and reference for solution documentation
- `compound` (`/phx:compound`) — Post-fix knowledge capture skill
Solution docs use YAML frontmatter (see `compound-docs/references/schema.md`).

### Hooks

Defined in `hooks/hooks.json`:

```json
{
  "hooks": {
    "PostToolUse": [...],   // Format + progress logging
    "SessionStart": [...],  // Directory setup + Tidewave detection
    "Stop": [...]           // Warn if uncompleted tasks
  }
}
```

**Current hooks:**

- `PostToolUse`: Auto `mix format` + `mix compile --warnings-as-errors` (silent on success) + security Iron Laws reminder for auth files + append to progress file + plan STOP reminder on plan.md write
- `PreCompact`: Re-inject Iron Laws and critical planning rules before context compaction (prevents rule loss)
- `SessionStart`: Tidewave detection, create `.claude/` directories, scratchpad check, resume workflow detection, workflow hints
- `Stop`: Warn if plans have unchecked tasks

### Tidewave Integration

When Tidewave MCP available:

- Prefer `mcp__tidewave__get_docs` over web search
- Prefer `mcp__tidewave__project_eval` over test scripts
- Prefer `mcp__tidewave__execute_sql_query` over psql

## Development

### Testing locally

```bash
# Option A: Test plugin directly
claude --plugin-dir ./plugins/elixir-phoenix

# Option B: Add as local marketplace
/plugin marketplace add .
/plugin install elixir-phoenix
```

### Testing workflow

```bash
# Test individual workflow phase
/phx:plan Test feature for workflow
# Check: .claude/plans/ has checkbox plan

/phx:work .claude/plans/test-feature/plan.md
# Check: Checkboxes update, progress logged in plans/test-feature/progress.md
```

### Adding new agent

1. Create `plugins/elixir-phoenix/agents/{name}.md`
2. Add frontmatter with all required fields
3. Keep under 300 lines

### Adding new skill

1. Create `plugins/elixir-phoenix/skills/{name}/SKILL.md` (~100 lines)
2. Create `references/` with detailed content
3. For workflow skills, document integration with cycle

### Setup

```bash
npm install  # Pre-commit hooks + linting
```

### Linting

```bash
npm run lint       # Check all markdown
npm run lint:fix   # Auto-fix issues
```

## Size Guidelines

| Component | Target | Hard Limit | Notes |
|-----------|--------|------------|-------|
| SKILL.md (reference) | ~100 | ~150 | Iron Laws + quick patterns |
| SKILL.md (command) | ~100 | ~185 | Command skills need complete execution flow inline |
| references/*.md | ~350 | ~350 | Detailed patterns |
| agents (specialist) | ~300 | ~365 | Design guidance beyond preloaded skill patterns |
| agents (orchestrator) | ~300 | ~535 | Subagent prompts + flow control must be inline |

### Why orchestrators and command skills exceed targets

Even with `permissionMode: bypassPermissions`, plugin files live in `~/.claude/plugins/cache/` — outside the project.
This means agents **cannot reliably read** skill `references/*.md` at runtime.

Content must be inline (in agent prompt or preloaded SKILL.md) to be available:

| Location | Auto-available? | Reliable? |
|----------|----------------|-----------|
| Agent system prompt | Yes | Yes |
| Preloaded skill SKILL.md (`skills:` field) | Yes | Yes |
| Skill `references/*.md` | No — needs Read call | **No** — permission prompt |

Orchestrators embed subagent prompts (~80 lines × 4 agents = 320 lines minimum).
Command skills drive execution — removing a step breaks the workflow.
Only trim when content is purely informational and not execution-critical.

## Checklist

### New agent

- [ ] Frontmatter complete
- [ ] `disallowedTools: Write, Edit, NotebookEdit` for review agents
- [ ] `Write` allowed for agents that output reports (e.g., research agents, context-supervisor)
- [ ] `permissionMode: bypassPermissions`
- [ ] Skills preloaded
- [ ] Under target (300 lines), hard limit only if justified by inline subagent prompts

### New skill

- [ ] SKILL.md under target (~100 lines), hard limit for command skills (~185)
- [ ] "Iron Laws" section
- [ ] `references/` for details
- [ ] No `triggers:` field

### New workflow skill

- [ ] Clear input/output artifacts
- [ ] Integration diagram with cycle position
- [ ] State transitions documented
- [ ] References previous/next phases

### Release

- [ ] All markdown passes linting
- [ ] Version updated
- [ ] README updated
- [ ] `/phx:intro` tutorial content still accurate (commands, agents, features)

---

# Claude Code Behavioral Instructions

**CRITICAL**: These instructions OVERRIDE default behavior for Elixir/Phoenix projects in this codebase.

## Automatic Skill Loading

When working on Elixir/Phoenix code, ALWAYS load relevant skills based on file context:

| File Pattern | Auto-Load Skills | Check References |
|--------------|------------------|------------------|
| `*_live.ex`, `*_component.ex` | `liveview-patterns` | `references/async-streams.md` |
| `*_channel.ex`, `*socket*` | `liveview-patterns` | `references/channels-presence.md` |
| `*/workers/*`, `*_worker.ex`, `*_job.ex`, `*_agent.ex` | `oban` | `references/worker-patterns.md` |
| `*/migrations/*`, `*_schema.ex`, `*changeset*`, `schema "` | `ecto-patterns` | `references/queries.md`, `references/changesets.md` |
| `*auth*`, `*session*`, `*password*` | `security` | `references/authentication.md`, `references/authorization.md` |
| `*_test.exs`, `*factory*`, `*fixtures*` | `testing` | `references/exunit-patterns.md`, `references/mox-patterns.md`, `references/factory-patterns.md` |
| `config/runtime.exs`, `Dockerfile`, `fly.toml` | `deploy` | `references/docker-config.md` |
| `*/contexts/*`, `lib/*/[a-z]*.ex` | `phoenix-contexts` | `references/context-patterns.md` |
| Any `.ex` or `.exs` file | `elixir-idioms` | Always check Iron Laws |

### Skill Loading Behavior

1. When opening/editing a file matching patterns above, silently load the skill
2. Apply Iron Laws from loaded skills as validation rules
3. If code violates Iron Law, **stop and explain** before proceeding
4. Reference detailed docs from `references/` when making implementation decisions

## Workflow Routing (Proactive)

When the user's FIRST message describes work without specifying a `/phx:` command:

1. Detect intent from their description (see `intent-detection` skill for routing table)
2. If multi-step workflow detected, suggest the appropriate command
3. Format: "This looks like [intent]. Want me to run `/phx:[command]`, or should I handle it directly?"
4. For trivial tasks (typos, single-line fixes, config changes): skip suggestion, just do it
5. If user already specified a command: follow it, don't re-suggest
6. NEVER block the user — suggestion only, one attempt max

### Debugging Loop Detection

When 3+ consecutive Bash commands are `mix compile` or `mix test` with failures, suggest: "Looks like a debugging loop. Want me to run `/phx:investigate` for structured analysis?"

## Iron Laws Enforcement (NON-NEGOTIABLE)

These rules are NEVER violated. If code would violate them, **STOP and explain** before proceeding:

### LiveView Iron Laws

1. **NO database queries in disconnected mount** - Use `assign_async`
2. **ALWAYS use streams for lists >100 items** - Regular assigns = O(n) memory per user
3. **CHECK `connected?/1` before PubSub subscribe** - Prevents double subscriptions

### Ecto Iron Laws

4. **NEVER use `:float` for money** - Use `:decimal` or `:integer` (cents)
5. **ALWAYS pin values with `^` in queries** - Never interpolate user input
6. **SEPARATE QUERIES for `has_many`, JOIN for `belongs_to`** - Avoids row multiplication

### Oban Iron Laws

7. **Jobs MUST be idempotent** - Safe to retry
8. **Args use STRING keys, not atoms** - Pattern match `%{"user_id" => id}`
9. **NEVER store structs in args** - Store IDs, not `%User{}`

### Security Iron Laws

10. **NO `String.to_atom` with user input** - Atom exhaustion DoS
11. **AUTHORIZE in EVERY LiveView `handle_event`** - Don't trust mount authorization
12. **NEVER use `raw/1` with untrusted content** - XSS vulnerability

### OTP Iron Laws

13. **NO process without runtime reason** - Processes model concurrency/state/isolation, NOT code structure
14. **SUPERVISE ALL LONG-LIVED PROCESSES** - Never bare `GenServer.start_link`/`Agent.start_link` in production. Use supervision trees

### Ecto Iron Laws (continued)

15. **NO IMPLICIT CROSS JOINS** - `from(a in A, b in B)` without `on:` creates Cartesian product

### Elixir Iron Laws

16. **@external_resource FOR COMPILE-TIME FILES** - Modules reading files at compile time MUST declare `@external_resource`

### Ecto Iron Laws (continued)

17. **DEDUP BEFORE `cast_assoc` WITH SHARED DATA** - Deduplicate shared child records before building changesets, not inside them

### LiveView Iron Laws (continued)

18. **CHECK CHANGESET ERRORS BEFORE UI DEBUGGING** - When a form save produces no visible error but no expected side effect, check `{:error, changeset}` first

### Ecto Iron Laws (continued)

19. **HIDDEN INPUTS FOR ALL REQUIRED EMBEDDED FIELDS** - Every required field in an embedded schema MUST have a `hidden_input` if not directly editable

### Elixir Iron Laws (continued)

20. **WRAP THIRD-PARTY LIBRARY APIs** - Always facade external dependency APIs behind a project-owned module. Enables swapping libraries without touching callers

### Violation Response

When detecting a potential Iron Law violation:

```
STOP: This code would violate Iron Law [number]: [description]

What you wrote:
[problematic code]

Correct pattern:
[fixed code]

Should I apply this fix?
```

## Framework Detection

### Ash Framework Detection

If the project uses Ash Framework (detected by `use Ash.Resource` or `use Ash.Domain`):

1. **Warn**: "This project uses Ash Framework. My Ecto-specific patterns may not apply."
2. **Suggest**: "For Ash-specific guidance, consult Ash Framework documentation."
3. **Skip**: Don't apply Ecto Iron Laws to Ash.Resource modules

### Phoenix Version Detection

Check `mix.exs` for Phoenix version:

- **Phoenix 1.8+**: Scopes are available, recommend scope-first patterns
- **Phoenix 1.7.x**: No scopes, use traditional plug-based auth (see `references/scopes-auth.md` Pre-Scopes section)

## Greenfield Project Detection

If project has <10 `.ex` files (new project):

1. **Use simpler planning** (no parallel agents needed)
2. **Suggest initial setup**: Tidewave, Credo, test factories

## Reference Auto-Loading

When working on code, automatically consult relevant reference documentation before implementing.

### Auto-Load Rules

| File/Code Pattern | Skill | References to Consult |
|-------------------|-------|----------------------|
| `*_live.ex` | liveview-patterns | async-streams.md, components.md |
| `*_live.ex` + form code | liveview-patterns | forms-uploads.md |
| `*_live.ex` + JS hooks | liveview-patterns | js-interop.md |
| `*_channel.ex`, `*socket*` | liveview-patterns | channels-presence.md |
| `Presence` in code | liveview-patterns | channels-presence.md |
| `priv/repo/migrations/*` | ecto-patterns | migrations.md |
| `use Ecto.Schema`, `*changeset*` | ecto-patterns | changesets.md |
| `from(` or `Repo.` | ecto-patterns | queries.md |
| `*/workers/*`, `*_worker.ex`, `*_agent.ex` | oban | worker-patterns.md |
| `use Oban.Worker` | oban | worker-patterns.md, queue-config.md |
| `*auth*`, `*session*` | security | authentication.md, authorization.md |
| `oauth`, `ueberauth` | security | oauth-linking.md |
| `*_test.exs` | testing | exunit-patterns.md |
| `*factory*`, `*fixtures*`, `*_factory.ex` | testing | factory-patterns.md |
| `*_live_test.exs` | testing | liveview-testing.md |
| `Mox.` in tests | testing | mox-patterns.md |
| `lib/*/[a-z]*.ex` (context) | phoenix-contexts | context-patterns.md |
| `router.ex` | phoenix-contexts | routing-patterns.md, plug-patterns.md |
| `*_controller.ex` + JSON | phoenix-contexts | json-api-patterns.md |
| `plug` in router/controller | phoenix-contexts | plug-patterns.md |
| `Dockerfile`, `fly.toml` | deploy | docker-config.md, flyio-config.md |
| `use GenServer` | elixir-idioms | otp-patterns.md |

### Consultation Behavior

1. **Before implementing**, read relevant reference for correct pattern
2. **Silently apply** patterns (don't narrate unless complex)
3. **Check Iron Laws** from skill before and after implementation
4. **Security code ALWAYS gets reference consultation** (authentication.md, authorization.md)

## Command Suggestions

| User Intent | Command |
|-------------|---------|
| New to the plugin | `/phx:intro` |
| Bug fix, debug | `/phx:investigate` |
| Small change (<50 lines) | `/phx:quick` |
| New feature (clear scope) | `/phx:plan` then `/phx:work` |
| Enhance existing plan | `/phx:plan --existing` |
| Large feature (new domain) | `/phx:full` |
| Review code | `/phx:review` |
| Triage review findings | `/phx:triage` |
| Capture solved problem | `/phx:compound` |
| Run checks | `/phx:verify` |
| Research topic | `/phx:research` |
| Evaluate a Hex library | `/phx:research --library` |
| Resume work | `/phx:work --continue` |
| N+1 queries | `/ecto:n1-check` |
| LiveView memory | `/lv:assigns` |
| PR review comments | `/phx:pr-review` |
| Performance analysis | `/phx:perf` |
| Project health | `/phx:audit` |
| Find sessions to analyze | `/find-sessions` |
| Analyze a session | `/analyze-session` |
| Full session analysis pipeline | `/session-insights` |
| Validate plugin against docs | `/docs-check` |

**Workflow Commands**: `/phx:plan` -> `/phx:plan --existing` (optional) -> `/phx:work` -> `/phx:review` -> `/phx:triage` (optional) -> `/phx:compound`

**Standalone**: `/phx:quick`, `/phx:full`, `/phx:investigate`, `/phx:verify`, `/phx:research`

**Analysis**: `/ecto:n1-check`, `/lv:assigns`, `/phx:boundaries`, `/phx:trace`, `/phx:techdebt`

**Session Insights (dev-only, requires ccrider MCP)**: `/find-sessions`, `/analyze-session`, `/session-insights`, `/analyze-sessions`

**Plugin Maintenance (dev-only)**: `/docs-check` — validate plugin against latest Claude Code documentation

## Workflow Patterns (from Claude Code team)

### Challenge Mode

When I say "grill me" or "challenge this":

- Review my changes as a senior Elixir engineer would
- Check for: N+1 queries, missing error handling, OTP anti-patterns, untested paths
- Diff behavior between `main` and current branch
- Don't approve until issues are addressed

### Elegance Reset

When I say "make it elegant" or "knowing everything you know now":

- Scrap the current approach
- Implement the idiomatic Elixir solution
- Prefer pattern matching over conditionals
- Prefer `with` chains over nested `case`
- Prefer streams/`Enum` pipelines over imperative loops
- Use proper OTP patterns where applicable

### Auto-Fix Patterns

When I say:

- "fix CI" → Run `mix compile --warnings-as-errors && mix test --failed` and fix all failures
- "fix it" → Look at the error/bug context and autonomously fix without asking questions
- "fix credo" → Run `mix credo --strict` and fix all issues

### Learn From Mistakes

After ANY correction I make:

- Ask: "Should I update CLAUDE.md so this doesn't happen again?"
- If yes, add a concise rule preventing the specific mistake
- Keep rules actionable: "Do NOT X — instead Y"

### Intro Tutorial Maintenance

When adding, removing, or renaming commands/skills/agents, check if
`plugins/elixir-phoenix/skills/intro/references/tutorial-content.md` needs updating.
The tutorial is new users' first impression — stale command references erode trust.
Quick check: does the cheat sheet in Section 4 still match reality?
