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
| `/phx:brief` | Understanding | Plan file | Interactive walkthrough (ephemeral) |
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
├── skill-metrics/             # Skill effectiveness dashboards and recommendations
│   ├── dashboard-{date}.json  # Per-skill aggregate metrics
│   └── recommendations-{date}.md  # Improvement recommendations
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
│       ├── session-scan/            # /session-scan — Tier 1 metrics
│       ├── session-deep-dive/       # /session-deep-dive — Tier 2 analysis
│       └── session-trends/          # /session-trends — trend reporting
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
│       └── skills/                  # 38 skills
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
effort: medium
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
- Set `effort:` to match cognitive load: `low` for haiku/mechanical agents, `medium` for sonnet specialists, `high` for opus orchestrators and security-critical agents
- Review agents are **read-only** (`disallowedTools: Write, Edit, NotebookEdit`)
- Use `permissionMode: bypassPermissions` for all agents — `default` causes "Bash command permission check failed"
  when agents run in background (safety system scans skill content for shell-like patterns)
- Use `memory: project` for agents that benefit from cross-session learning (orchestrators, pattern analysts).
  Note: `memory` auto-enables Read, Write, Edit — only add to agents that already have Write access
- Preload relevant skills via `skills:` field
- Add `omitClaudeMd: true` for read-only agents (no Write tool) — they don't need commit/PR/lint
  guidelines from CLAUDE.md. Iron Laws are injected via SubagentStart hook. Enforced by eval.
  - **Iron Laws injection ≠ CLAUDE.md inclusion.** `omitClaudeMd: true` skips the project
    CLAUDE.md body (commit rules, lint guidance, scope cues). It does NOT suppress Iron Laws —
    the `SubagentStart` hook injects them via `hookSpecificOutput.additionalContext` on every
    subagent spawn. Set `omitClaudeMd: true` freely on read-only agents; Iron Laws stay enforced.
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
- Set `effort:` to match skill complexity: `low` for mechanical (verify, quick, compound), `medium` for reference skills, `high` for complex reasoning (plan, full, investigate, review)
- Use `${CLAUDE_SKILL_DIR}/references/` for reference file paths (not bare `references/`)
- No `triggers:` field (use `description` for auto-loading)
- **Description must be under 250 characters** — this is a plugin-side budget discipline,
  not a hard CC cap. CC raised `MAX_LISTING_DESC_CHARS` from 250 to 1,536 in v2.1.105, but
  the skill-listing budget is still ~1% of the context window (~8K chars default). With
  ~40 skills in this plugin, every description has ~200 chars of listing budget on average.
  Longer descriptions crowd out other skills in the listing, hurting routing accuracy across
  the whole plugin. Target under 200 chars. Enforced by eval.

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
    "PreToolUse": [...],            // Block dangerous ops (ecto.reset, force push, MIX_ENV=prod)
    "PostToolUse": [...],          // Format + Iron Law verify + security + progress + plan STOP + debug stmt
    "PostToolUseFailure": [...],   // Elixir failure hints + error critic for mix commands
    "SubagentStart": [...],        // Iron Laws injection into all subagents
    "SessionStart": [...],         // Setup dirs + Tidewave + resume detection
    "PreCompact": [...],           // Re-inject workflow rules before compaction
    "PostCompact": [...],          // Verify plan state survived compaction
    "StopFailure": [...],          // Log API failures to scratchpad for resume
    "Stop": [...]                  // Warn if uncompleted tasks
  }
}
```

**Current hooks:**

- `PreToolUse` (Bash): Block destructive operations (`mix ecto.reset/drop`, `git push --force`, `MIX_ENV=prod`) before execution
- `PostToolUse` (Edit): Auto `mix format --check-formatted`, **programmatic Iron Law verification**,
  **debug statement detection** — all use `if` conditions to only fire on `.ex`/`.exs` files
  (e.g., `"if": "Edit(*.ex)"`) to avoid unnecessary shell spawns on non-Elixir files
- `PostToolUse` (Write): Same Elixir checks as Edit + plan STOP reminder with `"if": "Write(*plan.md)"`
- `PostToolUse` (Edit|Write): Security Iron Laws for auth files, async progress logging
  (these fire on all file types — no `if` filtering)
- `PostToolUseFailure` (Bash): Elixir-specific debugging hints and **error critic** —
  both use `"if": "Bash(*mix*)"` to only fire on mix command failures (via `additionalContext`)
- `SubagentStart`: Inject all Iron Laws into every spawned subagent via `additionalContext` (addresses zero skill auto-loading gap)
- `PreCompact`: Re-inject workflow rules (plan/work/full) before compaction via JSON `systemMessage`
- `SessionStart` (all): Setup `.claude/` directories + Tidewave detection (`async: true`)
- `SessionStart` (startup|resume only): Scratchpad check + resume workflow detection + branch freshness (`async: true`) + workflow hints
- `PostCompact`: Verify active plan state survived compaction, warn Claude to re-read plan and scratchpad
- `StopFailure`: Log API failure to plan scratchpad for resume detection in next session
- `Stop`: Warn if plans have unchecked tasks

**Hook output patterns (important for contributors):**

- `PostToolUse` stdout is **verbose-mode only** — use `exit 2` + stderr to feed messages to Claude
- `PreCompact` has **no stdout context injection** — use JSON `systemMessage`
- `SessionStart` stdout IS added to Claude's context (one of two exceptions along with `UserPromptSubmit`)
- `SubagentStart` uses `hookSpecificOutput.additionalContext` to inject context into subagents
- `PostToolUseFailure` uses `hookSpecificOutput.additionalContext` for debugging hints
- `PostCompact` uses `exit 2` + stderr to warn Claude (same pattern as PostToolUse)
- `StopFailure` uses `exit 2` + stderr and writes to scratchpad file

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

When editing skills, agents, or hooks mid-session, run `/reload-plugins` to
pick up changes without restarting Claude Code (v2.1.98+). Skills now hot-reload
through this command even when provided by installed plugins.

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

### Quality Commands (use `make`)

```bash
make help          # Show all commands
make lint          # Lint markdown
make lint-fix      # Auto-fix lint
make test          # 52 pytest tests for eval framework
make eval          # Quick: lint + score changed skills/agents + trigger accuracy (cached)
make eval-all      # Score all 40 skills + 20 agents + trigger accuracy
make eval-fix      # Auto-fix lint + show failures + suggest autoresearch
make eval-tournament # Run tournament on weak skills (<75% trigger accuracy)
make ci            # Full CI pipeline: lint + test + eval
```

### Eval Framework (lab/eval/)

The plugin has a deterministic 8-dimension scoring system for skills and
5-dimension scoring for agents. **Run `make eval` after every skill/agent edit.**

**When editing skills/agents, ALWAYS verify your changes pass eval:**

1. Edit the skill or agent file
2. Run `make eval` — checks only changed files
3. If FAIL: run `make eval-fix` to see exact failures and get fix suggestions
4. Fix the issues and re-run until PASS

**What eval checks** (skills — 8 dimensions):

- completeness (sections, Iron Laws, frontmatter)
- accuracy (cross-references valid)
- conciseness (line counts, section limits)
- triggering (description keywords, "Use when..." structure)
- safety (Iron Laws, prohibitions, no dangerous patterns)
- clarity (action density, no duplication, step coverage)
- specificity (code examples, concrete vs vague)
- behavioral (trigger accuracy via cached haiku tests)

**What eval checks** (agents — 5 dimensions):

- completeness (frontmatter: name, description, tools, model, effort)
- accuracy (preloaded skills exist, tools valid)
- conciseness (line limits per agent type)
- safety (bypassPermissions, read-only enforcement)
- consistency (model matches effort level)

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
- [ ] `disallowedTools: Edit, NotebookEdit` for review agents (Write IS allowed so they can save their own findings file — `Edit` blocks source code modification, upholding Review Iron Law #1)
- [ ] `Write` allowed for agents that output reports (research agents, reviewers, context-supervisor). Only agents that neither review nor research should have Write disallowed.
- [ ] `permissionMode: bypassPermissions`
- [ ] `effort:` set (low for haiku, medium for sonnet, high for opus/security)
- [ ] `omitClaudeMd: true` for report-only agents (Write allowed for own report, Edit disallowed). They don't need commit/lint guidelines. Iron Laws injected via SubagentStart hook.
- [ ] Skills preloaded
- [ ] Description under 250 characters
- [ ] Under target (300 lines), hard limit only if justified by inline subagent prompts

### New skill

- [ ] SKILL.md under target (~100 lines), hard limit for command skills (~185)
- [ ] "Iron Laws" section
- [ ] `references/` paths use `${CLAUDE_SKILL_DIR}/references/`
- [ ] `effort:` set (low/medium/high)
- [ ] No `triggers:` field
- [ ] Description under 250 characters (CC internal budget cap)

### New workflow skill

- [ ] Clear input/output artifacts
- [ ] Integration diagram with cycle position
- [ ] State transitions documented
- [ ] References previous/next phases

### Release

- [ ] All markdown passes linting
- [ ] Version bumped in `plugins/elixir-phoenix/.claude-plugin/plugin.json`
- [ ] `CHANGELOG.md` updated with all changes under new version heading
- [ ] README updated
- [ ] `/phx:intro` tutorial content still accurate (commands, agents, features)

### Versioning

The plugin uses [semantic versioning](https://semver.org/):

- **MAJOR**: Breaking changes (workflow redesign, removed commands)
- **MINOR**: New features (new hooks, skills, agents, commands)
- **PATCH**: Bug fixes, doc updates, description improvements

**IMPORTANT**: Users only receive updates when the version in `plugin.json`
changes. If you push code without bumping the version, existing users won't
see the changes due to caching.

When making changes, ALWAYS update `CHANGELOG.md` under the current
`[Unreleased]` section. Use categories: Added, Changed, Fixed, Removed.
On release, rename `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD` and bump
`plugin.json`.

---

# Claude Code Behavioral Instructions

**CRITICAL**: These instructions OVERRIDE default behavior for Elixir/Phoenix projects in this codebase.

## Automatic Skill Loading

When working on Elixir/Phoenix code, ALWAYS load relevant skills based on file context:

| File Pattern | Auto-Load Skills | Check References |
|--------------|------------------|------------------|
| `*_live.ex`, `*_component.ex` | `liveview-patterns` | `references/async-streams.md` |
| `*_channel.ex`, `*socket*` | `liveview-patterns` | `references/channels-presence.md` |
| `*/workers/*`, `*_worker.ex`, `*_worker_test.exs`, `*_job.ex`, `*_agent.ex` | `oban` | `references/worker-patterns.md` |
| `*/migrations/*`, `*_schema.ex`, `*changeset*`, `schema "` | `ecto-patterns` | `references/queries.md`, `references/changesets.md` |
| `*auth*`, `*session*`, `*password*` | `security` | `references/authentication.md`, `references/authorization.md` |
| `*_test.exs`, `*factory*`, `*fixtures*` | `testing` | `references/exunit-patterns.md`, `references/mox-patterns.md`, `references/factory-patterns.md` |
| `config/runtime.exs`, `Dockerfile`, `fly.toml` | `deploy` | `references/docker-config.md` |
| `*/contexts/*`, `lib/*/[a-z]*.ex` | `phoenix-contexts` | `references/context-patterns.md` |
| `lib/mix/tasks/*` | `elixir-idioms` | `references/mix-tasks.md` |
| `*.sface` | `liveview-patterns` | `references/components.md` |
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

The `error-critic.sh` hook automatically detects repeated mix failures and
escalates from generic hints (attempt 1) to structured critic analysis
(attempt 3+). It tracks failure count per command and consolidates error
history. This implements the Critic→Refiner pattern from AutoHarness
(Lou et al., 2026): structured error consolidation before retry prevents
debugging loops more effectively than unstructured retry.

If the hook hasn't triggered (e.g., non-mix failures), manually detect:
when 3+ consecutive Bash commands are `mix compile` or `mix test` with failures,
suggest: "Looks like a debugging loop. Want me to run `/phx:investigate` for structured analysis?"

### LiveView Bug Detection via Tidewave Context

When the user's message contains a `<context name="current-page">` block (injected by Tidewave)
describing a broken form, missing element, or UI issue — proactively suggest:
"This looks like a LiveView bug. Want me to run `/phx:investigate` for structured root-cause analysis?"

### Custom MIX_ENV Awareness

Some projects use non-standard Mix environments (e.g., `MIX_ENV=int_test` for E2E tests). When you see:

- `config/int_test.exs` or other non-standard env config files
- `MIX_ENV=` in mix.exs aliases
- User running `MIX_ENV=<custom> mix compile/test`

Then use that MIX_ENV for ALL compile, test, and format commands on those files. Do NOT use default MIX_ENV for files that only compile under the custom env.

### Scoped Format and Compile Checks

When running `mix format --check-formatted` or `mix compile`, **always scope to the files you changed**
when possible. If a full-project check fails on files you didn't edit, report it as pre-existing
and continue — do NOT waste time debugging unrelated format failures.

### Sibling File Check

When fixing a bug in a file that has named variants (e.g., `seller_account/form.ex`,
`buyer_account/form.ex`, `occupier_account/form.ex`), proactively grep for all sibling files and
check if the same bug exists in each variant. Do this BEFORE implementing the fix, not after.

## Iron Laws Enforcement (NON-NEGOTIABLE)

These rules are NEVER violated. If code would violate them, **STOP and explain** before proceeding:

### LiveView Iron Laws

1. **NO unconditional DB queries in mount** - Mount runs twice. Default: `assign_async`. SEO routes: `connected?` + cache-backed disconnected branch (dead-render IS the crawler-indexed HTML)
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

### LiveView Iron Laws (continued)

21. **NEVER use `assign_new` for values refreshed every mount** - `assign_new` skips the function if the key exists. Use `assign/3` for locale, current user, or any value that must be set on every mount

### Verification Iron Laws

22. **VERIFY BEFORE CLAIMING DONE** - Never say "should work" or "this fixes it." Run `mix compile && mix test` and show the result. If you can't verify, explicitly state what remains unverified

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
| `*/workers/*`, `*_worker.ex`, `*_worker_test.exs`, `*_agent.ex` | oban | worker-patterns.md |
| `use Oban.Worker` | oban | worker-patterns.md, queue-config.md |
| `*auth*`, `*session*` | security | authentication.md, authorization.md |
| `oauth`, `ueberauth` | security | oauth-linking.md |
| `*_test.exs` | testing | exunit-patterns.md |
| `*factory*`, `*fixtures*`, `*_factory.ex` | testing | factory-patterns.md |
| `*_live_test.exs` | testing | liveview-testing.md |
| `Mox.` in tests | testing | mox-patterns.md |
| `lib/*/[a-z]*.ex` (context) | phoenix-contexts | context-patterns.md |
| `*.sface` | liveview-patterns | components.md |
| `router.ex` | phoenix-contexts | routing-patterns.md, plug-patterns.md |
| `*_controller.ex` + JSON | phoenix-contexts | json-api-patterns.md |
| `plug` in router/controller | phoenix-contexts | plug-patterns.md |
| `Dockerfile`, `fly.toml` | deploy | docker-config.md, flyio-config.md |
| `use GenServer` | elixir-idioms | otp-patterns.md |
| `lib/mix/tasks/*` | elixir-idioms | mix-tasks.md |

### Consultation Behavior

1. **Before implementing**, read relevant reference for correct pattern
2. **Silently apply** patterns (don't narrate unless complex)
3. **Check Iron Laws** from skill before and after implementation
4. **Security code ALWAYS gets reference consultation** (authentication.md, authorization.md)

## Command Suggestions

| User Intent | Command |
|-------------|---------|
| "Which command should I use?" | `/phx:help` |
| New to the plugin | `/phx:intro` |
| Bug fix, debug | `/phx:investigate` |
| Small UI fix, CSS tweak, config change | `/phx:quick` |
| Small change (<50 lines) | `/phx:quick` |
| Brainstorm, explore ideas, unclear scope | `/phx:brainstorm` |
| New feature (clear scope) | `/phx:plan` then `/phx:work` |
| Understand a plan | `/phx:brief` |
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
| Reduce permission prompts | `/phx:permissions` |
| Scan sessions for metrics | `/session-scan` |
| Deep-analyze sessions | `/session-deep-dive` |
| View session trends | `/session-trends` |
| Monitor skill effectiveness | `/skill-monitor` |
| Validate plugin against docs | `/docs-check` |

**Workflow Commands**: `/phx:brainstorm` (optional) -> `/phx:plan` -> `/phx:brief` (optional) -> `/phx:plan --existing` (optional) -> `/phx:work` -> `/phx:review` -> `/phx:triage` (optional) -> `/phx:compound`

**Review → Follow-up Plan**: After `/phx:review`, if findings reveal scope gaps or missing coverage, use `/phx:plan .claude/plans/{slug}/reviews/{review}.md` to create a follow-up plan from review output.

**Standalone**: `/phx:quick`, `/phx:full`, `/phx:investigate`, `/phx:verify`, `/phx:research`, `/phx:brainstorm`, `/phx:help`, `/phx:permissions`

**Analysis**: `/ecto:n1-check`, `/lv:assigns`, `/phx:boundaries`, `/phx:trace`, `/phx:techdebt`

**Session Analytics (dev-only, requires ccrider MCP)**: `/session-scan`, `/session-deep-dive`, `/session-trends`

**Skill Monitoring (dev-only)**: `/skill-monitor` — per-skill effectiveness dashboard and improvement recommendations

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

### Interesting Findings Log

When you discover something noteworthy during work — a surprising metric, a
counter-intuitive finding, a useful pattern from research, or a before/after
improvement stat — **append it to `lab/findings/interesting.jsonl`** immediately.

Format (one JSON per line):

```json
{"date": "2026-03-25", "category": "behavioral", "title": "Plan skill has 0% recall", "detail": "Haiku never routes 'build a chat feature' to plan skill despite description saying 'multi-file feature'. Use-case phrases needed, not technical terms.", "source": "trigger_scorer.py", "tags": ["autoresearch", "trigger", "description"]}
```

Categories: `behavioral`, `performance`, `research`, `pattern`, `bug`, `metric`, `user-insight`

This log feeds blog posts, release notes, and Twitter threads. Don't filter —
write anything that made you think "that's interesting". The file is gitignored.
