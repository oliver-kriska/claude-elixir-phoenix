---
name: phx:plan
description: Plan an Elixir/Phoenix feature with comprehensive research. Spawns specialist agents and outputs structured plan with checkboxes for /phx:work execution.
argument-hint: <feature description OR path to review/plan file>
disable-model-invocation: true
---

# Plan Elixir/Phoenix Feature

Plan a feature by spawning Elixir specialist agents, then output
structured plan with checkboxes.

## What Makes /phx:plan Different from /plan

1. Spawns Elixir specialist agents for research
2. Plans with `[ecto]`, `[liveview]`, `[oban]` task routing
3. Checks for Iron Law compliance in the plan
4. Includes `mix compile/format/credo/test` verification
5. Understands Phoenix context boundaries

## Usage

```
/phx:plan Add user avatars with S3 upload
/phx:plan .claude/plans/notifications/reviews/notifications-review.md
/phx:plan Implement notifications --depth deep
/phx:plan .claude/plans/auth/plan.md --existing
```

## Arguments

- `$ARGUMENTS` = Feature description, review file, or existing plan
- `--depth quick|standard|deep` = Planning depth (auto-detected)
- `--existing` = Enhance an existing plan with deeper research

## Workflow

1. **Gather context** — File path (skip to agents), clear
   description, or vague/fuzzy (needs clarification)
2. **Clarify if vague** — Ask questions ONE at a time
3. **Detect depth** — Auto-detect quick/standard/deep
4. **Runtime context** (Tidewave) — Gather live schemas, routes,
   and warnings before spawning agents (see planning-orchestrator)
5. **Spawn research agents** — Selective, parallel, based on need
6. **Wait for ALL agents** — Call `TaskOutput(task_id, block: true)`
   for EVERY spawned agent. Do NOT proceed until all return
   "completed". NEVER write plan while any agent is still running
7. **Extract requirements** — Enumerate Rs before task generation
8. **Breadboard** (LiveView) — System map for multi-page features
9. **Fit-check** (when 2+ options) — R × S grid for competing approaches
10. **Completeness check** — MANDATORY when planning from review
11. **Split decision** — One plan or multiple, concrete options
12. **Generate plan** — Checkboxes, phased tasks, **demo statements**, code patterns
13. **Self-check** (deep only) — Three questions in Risks section
14. **Present and ask** — STOP, show summary, let user decide

**When planning from review**: Every finding must appear in the
plan — either as a task OR explicitly deferred by the user.

See `references/planning-workflow.md` for detailed step-by-step.

### --existing Mode (Deepening)

Enhances an existing plan instead of creating a new one:

1. Load plan, search `.claude/solutions/` for known risks
2. Spawn SPECIALIST agents (not Explore) for thin sections.
   Each agent writes to `.claude/plans/{slug}/research/` and
   returns only a 500-word summary. Same agent selection rules
3. Wait for ALL agents (`TaskOutput` with `block: true`)
4. Add implementation detail, resolve spikes, add verification
5. Present diff summary — **NEVER delete existing tasks**

## Iron Laws

1. **NEVER auto-start /phx:work** — Always present plan and ask
2. **Research before assuming** — Web-search unfamiliar tech
3. **Spawn agents selectively** — Only relevant, not all
4. **NEVER write plan while agents still running**
5. **NEVER skip input findings** — Every finding MUST have a task
6. **Do NOT spawn hex-library-researcher for existing deps**

## Integration with Workflow

```text
/phx:plan {feature}  <-- YOU ARE HERE
       |
   /phx:plan --existing (optional enhancement)
       |
   ASK USER -> /phx:work .claude/plans/{feature}/plan.md
       |
/phx:review → /phx:compound
```

### --annotate Mode (Lightweight Refinement)

Iterative plan review using inline annotations:

```
/phx:plan .claude/plans/auth/plan.md --annotate
```

1. User adds `<!-- ANNOTATION: HIGH | SCOPE | Include rate limiting -->` to plan
2. Agent processes annotations in priority order (CRITICAL → LOW)
3. Types: TASK, SCOPE, DECISION, RISK, SPIKE, PATTERN, GENERAL
4. Removes each annotation after addressing
5. Task IDs `[Pn-Tm]` are NEVER deleted (Iron Law)
6. Tracks cycles: `**Annotation Cycles**: n` in plan metadata

**vs. `--existing`**: Annotations are lightweight (no agents spawned),
fast (1-3 min per cycle). `--existing` is for deep research with
agent spawning. Users combine both.

See `references/annotation-guide.md` for full syntax reference.

## Plan Artifacts

Each plan includes:

- `.claude/plans/{slug}/plan.md` — The plan itself (source of truth)
- `.claude/plans/{slug}/plan.json` — Machine-readable sidecar (auto-generated,
  used for validation and recovery in long-running sessions)
- `.claude/plans/{slug}/scratchpad.md` — Decisions, dead-ends, handoffs
- `.claude/plans/{slug}/research/` — Agent research output (deletable)

## Notes

- Plans saved to `.claude/plans/{slug}/plan.md`
- Research reports in `.claude/plans/{slug}/research/` can be deleted after

## CRITICAL: After Writing the Plan

**STOP. Do NOT proceed to implementation.**

After writing `.claude/plans/{slug}/plan.md`:

1. Summarize: task count, phases, key decisions
2. Use `AskUserQuestion` with options:
   - "Start in fresh session" (recommended for 5+ tasks)
   - "Get a briefing" (`/phx:brief` — interactive walkthrough)
   - "Start here"
   - "Review the plan"
   - "Adjust the plan"
3. Wait for user response. Never auto-start work.

**When user selects "Start in fresh session"**, print:

```
1. Run `/new` to start a fresh session
2. Then run one of:
   /phx:work .claude/plans/{slug}/plan.md
   /phx:full .claude/plans/{slug}/plan.md  (includes review + compound)
```

This is Iron Law #1. Violating it wastes user context.

## References (DO NOT read — for human reference only)

- `references/planning-workflow.md` — Detailed step-by-step
- `references/plan-template.md`
- `references/complexity-detail.md`
- `references/example-plan.md`
- `references/agent-selection.md`
- `references/breadboarding.md`
