# Planning Workflow — Detailed Steps

Full step-by-step details for `/phx:plan`. The SKILL.md has a
summary; this reference has the complete workflow.

## Clarification Questions (when requirements are fuzzy)

When the description is vague, unclear, or missing key details,
ask clarifying questions **one at a time** before planning. This
replaces the need for a separate brainstorm command.

**Signals that clarification is needed:**

- Description is under 10 words without specifics
- Contains "some kind of", "maybe", "I think", "not sure"
- Missing WHO (which users), WHAT (specific behavior), or WHY
- Multiple possible interpretations exist
- Security/data implications that need explicit decisions

**Question flow** (ask ONE at a time, not all at once):

1. **Purpose**: "What problem does this solve for users?"
2. **Scope**: "Which specific behavior should this include?"
3. **Users**: "Who will use this? Any role/permission differences?"
4. **Constraints**: "Any technical constraints or preferences?"
5. **Edge cases**: "What should happen when [X]?"

**Stop asking when**: You have enough to write a plan with
concrete tasks. 2-4 questions is usually enough. Don't
interrogate — if the user gives a detailed answer, extract
what you need and move on.

**Capture decisions**: Save all clarification answers to
`.claude/plans/{slug}/scratchpad.md` as DECISION entries for future
reference.

## Depth Detection

If `--depth` not specified, auto-detect from **both** the clarity
of the request and the technical complexity:

| Request Clarity            | Technical Scope                    | Depth                       |
| -------------------------- | ---------------------------------- | --------------------------- |
| Clear + specific           | 1 context, <5 files                | `quick`                     |
| Clear + specific           | 2-3 contexts, schemas/LiveViews    | `standard`                  |
| Clear + specific           | 4+ contexts, security, new workers | `deep`                      |
| Vague (post-clarification) | Any                                | At least `standard`         |
| From review file           | Any                                | `standard` (scope is known) |

**Depth determines agent count AND plan detail:**

| Depth      | Agents             | Clarification           | Plan Detail                          |
| ---------- | ------------------ | ----------------------- | ------------------------------------ |
| `quick`    | 1 (patterns only)  | Skip if clear           | Task list, minimal prose             |
| `standard` | 2-3 specialists    | 1-2 questions if needed | Phased tasks with code patterns      |
| `deep`     | 4+ (full research) | 3-5 questions           | Full system map, risks, alternatives |

**Elixir-specific complexity signals**: New migration? New LiveView?
New Oban worker? Changes Phoenix context boundaries? Multiple
contexts affected? These push toward deeper planning.

## Agent Spawning

Spawn agents using the Task tool based on what's actually needed.
Delegate broad research to agents. You MAY read specific files
(CI config, a single module) for plan detail, but do NOT do the
agents' job -- let them handle pattern discovery.

**Agent count scales with depth:**

- `quick`: 1 agent (phoenix-patterns-analyst only)
- `standard`: 2-3 agents (patterns + relevant specialists)
- `deep`: 4+ agents (patterns + specialists +
  web-researcher + hex-library-researcher)

**Always spawn:**

- `phoenix-patterns-analyst`: Analyze codebase for existing patterns

**Spawn conditionally based on feature needs:**

| Condition                             | Agent                    |
| ------------------------------------- | ------------------------ |
| NEW library needed (not in mix.exs)   | `hex-library-researcher` |
| UI, form, live, real-time features    | `liveview-architect`     |
| Database, schema, table changes       | `ecto-schema-designer`   |
| Job, worker, async, queue             | `oban-specialist`        |
| GenServer, process, state             | `otp-advisor`            |
| Auth, login, permission, security     | `security-analyzer`      |
| Unfamiliar tech, need community input | `web-researcher`         |
| Changing function signatures          | `call-tracer`            |

**hex-library-researcher rules (STRICT):**

- ONLY spawn when evaluating a library NOT already in mix.exs
- Do NOT spawn for: review blockers, refactoring, existing libraries
- To understand an existing library's API, use Read/Grep on
  `deps/{library}/lib/` or use Tidewave's `get_docs` instead

**CRITICAL**: Spawn ALL applicable agents in ONE Tool Use block
(parallel) with `run_in_background: true`. Minimum 1 agent spawned.

**Agent prompts must be FOCUSED.** Scope each prompt to the
relevant directories, files, and patterns. Do NOT give vague
prompts like "analyze the codebase."

## Waiting for Agents

Call TaskOutput for each background agent. If TaskOutput shows
the agent is still running, **wait and check again**. Do NOT
proceed to plan generation until every agent status is
"completed" (not "still running").

Then read reports from `.claude/plans/{slug}/research/`.

If an agent fails, do the research yourself with Read/Grep
instead of re-spawning.

## Infrastructure Knowledge Persistence

When Explore agents discover **project infrastructure** (not
feature-specific code) — e.g., test helpers, factory patterns,
API endpoint maps, compile environments — write a compact summary
to `.claude/plans/{slug}/scratchpad.md` under a `## Infrastructure`
heading. This prevents re-exploration in follow-up sessions.

Signals that knowledge is infrastructure (not feature-specific):

- Test setup patterns (`test/support/`, `test/int_support/`)
- Custom MIX_ENV configurations
- Factory/fixture patterns
- CI/deployment pipeline structure

## Breadboard System Map (LiveView Features)

**When to breadboard**: The feature touches 2+ LiveView pages or
components, has complex event flows (PubSub, streams, multi-step
forms), or involves navigation between multiple live routes.
**Skip** for single-page CRUD, config changes, or non-LiveView work.

If liveview-architect was spawned, its report should include
affordance tables. Use these to build a system map. See
`references/breadboarding.md` for full details.

## Completeness Check

**MANDATORY when planning from review.** List ALL findings from
the source and verify every one is covered:

> Source has N items. Coverage:
>
> - Finding 1: -> Plan A / Task X
> - Finding 2: -> Plan A / Task Y
>
> All N items are planned.

Every finding gets a task. No exceptions. If the user wants to
exclude something, they must say so explicitly.

**Elixir completeness**: Does the plan include migration if schema
changes? Tests for new public functions? LiveView mount + event
handlers? Context functions for new domain logic?

## Split Decision

**One plan = one MD file = one focused work unit.**

If the feature is small (up to ~8 tasks, same domain), skip this
step and create one plan. Do NOT ask unnecessary questions.

If the feature is large, present OPTIONS with concrete numbers:

> Based on my analysis, this feature has N concerns and ~M tasks.
> How should I structure the plans?
>
> 1. **One plan** -- 1 file, ~M tasks across K phases
> 2. **Split into X plans** -- grouped by domain:
>    - `auth/plan.md` (5 tasks) -- login, register, reset
>    - `profiles/plan.md` (4 tasks) -- avatar, bio, settings

## Requirements Extraction

**Before generating tasks**, enumerate explicit requirements:

1. Extract from user description, research findings, and domain rules
2. Classify as Must / Should / Could (MoSCoW priority)
3. Requirements are STANDALONE — they don't depend on any specific
   implementation approach

```markdown
## Requirements

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| R1 | User can reset password via email | Must | User request |
| R2 | Token expires after 24 hours | Must | Security policy |
| R3 | Rate limit: max 3 resets per hour | Should | Best practice |
```

Every requirement MUST have at least one corresponding task.
This catches gaps before task generation begins.

## Fit-Check Matrix (Contested Decisions)

When the decision council identifies 2+ competing approaches AND
≥3 requirements have been extracted, produce an R × S fit-check grid:

```markdown
## Fit Check: State Management

| Req | Description | Option A: GenServer | Option B: ETS |
|-----|-------------|:---:|:---:|
| R1 | Concurrent access | ✅ | ✅ |
| R2 | Survives restart | ❌ | ❌ |
| R3 | Sub-ms reads | ❌ | ✅ |
| **Score** | | **1/3** | **2/3** |
```

**Rules**: ✅/❌ only — no "maybe" or "partial". Forces clear thinking.
Skip when there's only one viable approach or <3 requirements.

## Demo Statements

Every plan phase MUST include a demo statement declaring what's
observable after completion:

```markdown
## Phase 1: User Registration [PENDING]

**Demo**: After this phase, user can register with email and see a
confirmation message.
```

**Good demos** (observable): "user can log in via OAuth", "admin
dashboard shows user count", "test suite passes for auth module"

**Bad demos** (not observable): "auth module refactored", "schema
updated", "dependencies added"

A phase without a demo statement is a horizontal layer. Suggest
reordering to ensure each phase delivers visible progress.

## Plan Generation

Create plan(s) at `.claude/plans/{feature-slug}/plan.md`.

Key requirements:

- Tasks in `- [ ] [Pn-Tm][annotation] Description` format
  (required for `/phx:work`). Valid annotations:
  `[direct]` (most common), `[ecto]`, `[liveview]`, `[oban]`,
  `[otp]`, `[security]`, `[test]`.
  Do NOT use subagent_type names like `[general-purpose]` or
  `[solo]` -- those are not valid annotations.
- Include: Source, Requirements, Summary, Scope, Technical Decisions,
  Fit-Check (if contested), Phased Tasks with Demo Statements,
  Patterns, Risks

**Task granularity**: Tasks are logical work units, NOT individual
file edits. Group by PATTERN (what you're doing), list LOCATIONS
within. Each task includes implementation detail (code examples,
before/after). Aim for 3-8 tasks per phase, not 15+.

**Function signature precision**: When a task involves extracting,
refactoring, or renaming functions, ALWAYS specify the exact
`ModuleName.function_name/arity` for both source and target.
Example: "Extract `MyApp.Orders.currency_options/0` from
`MyApp.Orders.Order` to `MyApp.Shared.CurrencyHelpers`".
Never write vague tasks like "extract existing pattern" without
specifying the function signature — this causes compile stalls.

**Scratchpad**: Also create `.claude/plans/{feature-slug}/scratchpad.md`
with initial context (feature name, brief description, plan file
path). This captures planning decisions for future sessions.

**Do NOT read any reference files.** The plan template is inlined
in the planning-orchestrator agent.

## Self-Check (Deep Plans Only)

For `deep` plans, answer these three questions in the plan's
**Risks** section before presenting:

1. **"What was the hardest decision?"** — Which technical choice
   had the most tradeoffs? Document alternatives considered.
2. **"What alternatives were rejected?"** — For each major
   decision, note what else was considered and why it lost.
3. **"What am I least confident about?"** — Flag areas where
   the plan might be wrong. Mark with ⚠️ for user review.

## Presenting the Plan

**STOP and present the plan.** Briefly summarize the plan (task
count, phase names, key scope). Then use `AskUserQuestion`:

For single plan:

- **Start in fresh session** (recommended for 5+ tasks)
- **Get a briefing** -- interactive walkthrough via `/phx:brief`
- **Start here** -- in current session (fine for small plans)
- **Review the plan** -- walk through phases in detail
- **Adjust the plan** -- tell me what to change

Do NOT say "Start Phase 1" — `/phx:work` runs the whole plan.

**When user selects "Start in fresh session"**, print clear
step-by-step:

```
1. Run `/new` to start a fresh session
2. Then run one of:
   /phx:work .claude/plans/{slug}/plan.md
   /phx:full .claude/plans/{slug}/plan.md  (includes review + compound)
```

## Deepening an Existing Plan (--existing mode)

When `--existing` is passed with a plan file path, enhance the
plan with deeper research instead of creating a new one.

### Deepening Workflow

1. **Load plan** -- Parse phases, tasks, annotations, `???` markers
2. **Search compound docs** -- Find known issues in planned areas
   (`grep -rl "KEYWORD" .claude/solutions/`)
3. **Spawn research agents** -- Use SPECIALIST agents (same
   selection rules as main flow), NOT Explore agents. Each agent
   MUST write detailed output to
   `.claude/plans/{slug}/research/{topic}.md` and return ONLY a
   500-word summary. Spawn all in ONE Tool Use block with
   `run_in_background: true`
4. **Wait for ALL agents** -- Call `TaskOutput(task_id, block: true)`
   for every spawned agent. Do NOT proceed until all complete
5. **Enhance plan** -- Add implementation detail, resolve spikes,
   add verification criteria, note risk from compound docs
6. **Present diff summary** -- Show what was enhanced

### When Deepening Adds Value

- Plan has 5+ tasks touching unfamiliar code
- Feature involves external API integration
- Security-sensitive features (auth, payments)
- Plan generated from review findings
- Tasks have `???` or spike markers

### Deepening Rules

- **NEVER delete existing tasks** — Only add detail and risks
- **Preserve task IDs** — `[Pn-Tm]` identifiers must not change
- **Compound docs first** — Check solution docs before spawning
  agents (saves context)
- **Context budget** — `--existing` often runs in sessions with
  prior history. Use specialist agents that write to files and
  return short summaries. Never use Explore agents (they return
  full output inline and exhaust context)
