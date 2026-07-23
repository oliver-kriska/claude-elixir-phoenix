# Planning Workflow — Detailed Steps

Full step-by-step details for `/skill:phx-plan`. The SKILL.md has a
summary; this reference has the complete workflow.

## Interview Detection (from /skill:phx-brainstorm)

Before asking clarification questions, check for a pre-existing
brainstorm interview:

1. Check the text after the skill name for a path containing `interview.md`
2. Check `.claude/plans/*/interview.md` for recent files (<24h)

If found with `Status: COMPLETE`:

- Read the interview.md Summary and Coverage Details
- Skip clarification questions entirely — the interview IS the clarification
- Use interview content for concern-track selection (depth detection still applies)
- Note in scratchpad: "Requirements from /skill:phx-brainstorm interview"

If found with `Status: IN_PROGRESS`:

- Read what exists, note gaps in coverage
- Ask ONLY about uncovered dimensions (don't re-ask covered ones)

## Clarification Questions (when requirements are fuzzy)

When the description is vague, unclear, or missing key details,
and no brainstorm interview.md exists, ask clarifying questions
**one at a time** before planning.

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

**Depth determines research track counts, concerns, and plan detail:**

| Depth      | Research tracks / concerns | Clarification           | Plan Detail                          |
| ---------- | ------------------ | ----------------------- | ------------------------------------ |
| `quick`    | 1 pattern track  | Skip if clear           | Task list, minimal prose             |
| `standard` | 2-3 concern tracks    | 1-2 questions if needed | Phased tasks with code patterns      |
| `deep`     | 4+ full research tracks | 3-5 questions           | Full system map, risks, alternatives |

**Elixir-specific complexity signals**: New migration? New LiveView?
New Oban worker? Changes Phoenix context boundaries? Multiple
contexts affected? These push toward deeper planning.

## Research Tracks

Select only the concerns the feature needs. Use the canonical selection table
below as concern expertise, not as a requirement for installed named agents.

- `quick`: existing-project-patterns track
- `standard`: patterns plus 1-2 relevant concern tracks
- `deep`: patterns plus all relevant concern and external-research tracks

Native generic subagents are an optional optimization. Give each one a focused
scope and require it to write evidence to `.claude/plans/{slug}/research/`.
When subagents are unavailable, perform the same tracks sequentially in this
session using repository search, dependency documentation, web research when
needed, and optional Tidewave tools when independently configured.

Before any research, create `.claude/plans/{slug}/scratchpad.md` and track progress there:

```markdown
## Research checklist
- [x] Existing project patterns — research/patterns.md
- [ ] Ecto/data design
- [ ] LiveView interaction design
```

Do not generate the plan until every selected track is `[x]`. If a track fails,
record the failure and complete it in the current session instead of dropping
its coverage. Preserve source paths, line evidence, alternatives, and confidence.

## Concern Selection

| Condition | Research concern |
|---|---|
| Always | Existing project patterns and context boundaries |
| NEW library not in `mix.exs` | Hex/library evaluation |
| UI, form, live, real-time | LiveView architecture |
| Database, schema, table | Ecto/data design |
| Job, worker, async, queue | Oban behavior |
| GenServer, process, state | OTP design |
| Auth, permission, secrets | Security |
| Unfamiliar technology | Primary docs and web evidence |
| Function signature changes | Call-site tracing |

Do not research an existing dependency as if selecting a new library. Inspect
its installed source/docs or optional runtime docs instead.

## Completing Research

Wait for every optional subagent to finish, collect its output, and complete any
missing or failed track sequentially. The checklist, research files, and
scratchpad make this state resumable without a runtime task API. Breadboarding
and infrastructure output are synthesized from this evidence, not delegated to
or made conditional on any named worker.

## Infrastructure Knowledge Persistence

When completed research discovers **project infrastructure** (not
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

Synthesize affordance tables and the system map from the completed research-track evidence. See
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

## Plan Generation

Create plan(s) at `.claude/plans/{feature-slug}/plan.md`.

Key requirements:

- Tasks in `- [ ] [Pn-Tm][annotation] Description` format
  (required for `/skill:phx-work`). Valid annotations:
  `[direct]` (most common), `[ecto]`, `[liveview]`, `[oban]`,
  `[otp]`, `[security]`, `[test]`.
  Do NOT use runtime worker names like `[general-purpose]` or
  `[solo]` -- those are not valid annotations.
- Include: Summary, Scope, Technical Decisions, Phased Tasks,
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

For the full plan structure, read
`references/plan-template.md` once when writing
the plan — do not re-read other reference files.

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
count, phase names, key scope). Then ask the user a normal conversational question:

For single plan:

- **Start in fresh session** (recommended for 5+ tasks)
- **Get a briefing** -- interactive walkthrough via `/skill:phx-brief`
- **Start here** -- in current session (fine for small plans)
- **Review or adjust the plan** -- walk through phases, tell me what to change

Do NOT say "Start Phase 1" — `/skill:phx-work` runs the whole plan.

**When user selects "Start in fresh session"**, print clear
step-by-step:

```
1. Run `/new` to start a fresh session
2. Then run one of:
   /skill:phx-work .claude/plans/{slug}/plan.md
   /skill:phx-full .claude/plans/{slug}/plan.md  (includes review + compound)
```

## Deepening an Existing Plan (--existing mode)

1. Load the existing plan and create or update its scratchpad checklist
2. Select thin sections as concern tracks; complete them sequentially in the
   current session by default
3. Optionally use native generic workers only for independent tracks, with
   bounded prompts and `.claude/plans/{slug}/research/{topic}.md` output
4. Synthesize breadboarding and infrastructure notes from the gathered evidence
5. Add detail and verification without deleting or silently changing tasks
6. Present a diff summary and stop for user review

Deepening is useful for unfamiliar code, external integrations, security-sensitive
work, and unresolved spikes. Preserve existing scope and decisions.
