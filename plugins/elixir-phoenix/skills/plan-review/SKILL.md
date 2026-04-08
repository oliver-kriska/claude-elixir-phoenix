---
name: phx:plan-review
description: Use after /phx:plan to review plan documents with parallel persona agents. Catches bad requirements, scope creep, and feasibility issues before implementation.
effort: high
argument-hint: "[mode:headless] [path/to/plan.md]"
---

# Plan Review — Multi-Persona Document Analysis

Review plan and requirements documents through parallel persona
agents. Catches issues before they become bad code.

Inspired by Compound Engineering's document-review, adapted for
Elixir/Phoenix with Iron Laws and BEAM-aware feasibility checks.

## Usage

```
/phx:plan-review                                    # Review most recent plan
/phx:plan-review .claude/plans/auth/plan.md          # Review specific plan
/phx:plan-review mode:headless .claude/plans/auth/plan.md  # No interaction
```

## How This Differs from /phx:review

| Aspect | `/phx:review` | `/phx:plan-review` |
|--------|---------------|---------------------|
| **Reviews** | Code (git diff) | Plans and requirements docs |
| **Agents** | Elixir code specialists | Document analysis personas |
| **Catches** | Bugs, anti-patterns, Iron Law violations | Scope creep, contradictions, infeasibility |
| **When** | After implementation | After planning, before work |

## Phase 1: Get and Classify Document

If path provided, read it. Otherwise, find most recent in
`.claude/plans/*/plan.md` via Glob.

Classify as **requirements** (from brainstorm) or **plan** (from
`/phx:plan`). Check for Elixir-specific content (Ecto schemas,
LiveView, OTP, Oban) for agent selection.

## Phase 2: Select and Dispatch Persona Agents

**Always dispatch:**

- **Coherence reviewer** — Contradictions, terminology drift,
  section mismatches, wrong counts
- **Feasibility reviewer** — Can this actually be built? Check
  against codebase patterns, Phoenix conventions, OTP constraints

**Conditionally dispatch based on plan content:**

- **Security reviewer** — Auth, sessions, tokens, API endpoints,
  user input handling. Checks against Security Iron Laws (10-12)
- **Scope guardian** — Multiple priority tiers, >8 requirements,
  scope boundary misalignment, unnecessary abstractions
- **Elixir architecture reviewer** — Ecto schema design, context
  boundaries, LiveView lifecycle, OTP supervision, Oban job design.
  Checks plan against Ecto (4-6, 15, 17, 19) and LiveView (1-3, 18, 21) Iron Laws

Announce which reviewers and why, then dispatch ALL in parallel
using the Agent tool. Each agent receives the full document.

**Agent prompt template:**

```
You are reviewing an Elixir/Phoenix {plan|requirements} document.
Analyze for {persona focus}. Return findings as structured text:

For each finding:
- Section: [which section]
- Issue: [what's wrong or missing]
- Severity: P0 (must fix) | P1 (should fix) | P2 (consider)
- Type: error (wrong) | omission (missing)
- Fix: auto (one clear fix) | present (needs judgment)
- Suggested fix: [if auto, the specific fix]
- Evidence: [quote from document]

Also check against these Iron Laws: {relevant laws}

Document path: {path}
Document content: {content}
```

## Phase 3: Synthesize Findings

1. **Validate** — Drop findings missing required fields
2. **Deduplicate** — Merge when same section + same issue across
   agents. Keep highest severity and confidence
3. **Resolve contradictions** — When agents disagree, present both
   perspectives as a tradeoff for user decision
4. **Route** — `auto` findings applied silently; `present` findings
   shown to user for judgment

## Phase 4: Apply and Present

**Apply auto-fixes** to the plan document in a single pass.
List what changed so user can verify.

**Present remaining findings** grouped by severity (P0 -> P2),
then by type (errors before omissions). Include coverage table
showing which agents ran and finding counts.

**Headless mode** (`mode:headless`): Skip all interaction. Apply
auto-fixes, return structured text summary, exit immediately.

## Phase 5: Next Action

Ask the user:

1. **Refine again** — Fix findings, re-review
2. **Review complete** — Proceed to `/phx:work`

After 2 refinement passes, recommend completion.

## Iron Laws

1. **Review is analysis, not rewriting** — Do not add new
   requirements or sections the user didn't discuss
2. **Auto-fix only when one clear fix** — If multiple valid
   approaches exist, present to user
3. **Elixir architecture agent checks Iron Laws** — Plan tasks
   that would violate Iron Laws are P0 findings
4. **NEVER skip feasibility** — Always check plan against actual
   codebase patterns and Phoenix conventions

## Integration

```text
/phx:plan → /phx:plan-review (YOU ARE HERE) → /phx:work → /phx:review → /phx:compound
```

## References

- `${CLAUDE_SKILL_DIR}/references/review-output-template.md`
