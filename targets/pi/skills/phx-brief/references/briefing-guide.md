# Briefing Guide

Detailed templates for each section of the `/phx:brief` interactive
briefing. Two modes: pre-work (plan pending) and post-work (plan
completed or in progress).

## Contents

- [General Rules](#general-rules)
- [Visual Formatting](#visual-formatting)
- [Pre-Work Mode Sections](#pre-work-mode-sections)
- [Post-Work Mode Sections](#post-work-mode-sections)
- [Handling "Ask me a question about this"](#handling-ask-me-a-question-about-this)
- [Edge Cases](#edge-cases)

## General Rules

1. **Each section: max 15-20 lines of output** — scan-friendly
2. **Use tables and bullet points** — no paragraphs of prose
3. **Ground everything in artifacts** — focus on insights specific
   to this plan's research, decisions, and scratchpad entries rather
   than general programming concepts. Quote from plan.md,
   scratchpad.md, and summaries
4. **Translate jargon** — convert `[P2-T3][ecto]` annotations into
   plain English like "Phase 2: set up the database schema"
5. **Highlight trade-offs** — decisions without trade-offs aren't
   interesting; focus on where alternatives existed

## Visual Formatting

Wrap each section in a distinctive briefing block so output is
visually distinct from normal conversation:

```
`★ Briefing ── {Section Title} ───────────────────`

{section content — tables, bullets, etc.}

`──────────────────────────────────────────────────`
```

Rules:

- The `★` marker and box-drawing lines (`─`) create a scannable
  landmark that users learn to recognize across briefings
- Keep the title short — it's the section name from the flow tables
- Content inside follows all normal rules (tables, bullets, max lines)
- The closing line has no label — just the border

---

## Pre-Work Mode Sections

### Section 1: What We're Building

**Source**: plan.md `## Summary` + `## Scope`

**Template:**

```markdown
`★ Briefing ── What We're Building ───────────────`

{Rewrite the Summary in plain language — what does this feature
DO for users? Not what files we'll touch.}

**In scope:**
- {scope item, rephrased as user-facing outcome}

**Out of scope:**
- {boundary, rephrased as "we're NOT doing X because Y"}

**Size:** {N} tasks across {M} phases

`──────────────────────────────────────────────────`
```

**Rules:**

- Rewrite the Summary for a developer who hasn't seen the ticket
- "In scope" items should answer "what will users see/do?"
- "Out of scope" should explain WHY items were excluded, not just
  list them — pull from scratchpad DECISION entries if available
- Include task/phase count so developers gauge effort

### Section 2: Key Decisions

**Source**: plan.md `## Technical Decisions` table +
`.claude/plans/{slug}/scratchpad.md` DECISION entries

**Template:**

```markdown
### Key Decisions

{For each row in Technical Decisions table:}

**{Decision}**: We chose **{Choice}**.
- Why: {Rationale from table}
- Alternative rejected: {From scratchpad DECISION entry, if exists}
- Trade-off: {What we give up with this choice}

{If scratchpad has DECISION entries not in the table, include those too.}
```

**Rules:**

- Max 4 decisions — pick the most architecturally significant
- Always include the rejected alternative and WHY it was rejected
- If no scratchpad exists, use only the table rationale
- If a Decision Council was run (check for
  `summaries/decision-*.md`), mention the consensus/disagreement

### Section 3: Solution Shape

**Source**: plan.md phase headers + `## Data Model` +
`## System Map` (if exists)

**Template:**

```markdown
### Solution Shape

The implementation flows through {M} phases:

| Phase | What Happens | Key Pattern |
|-------|-------------|-------------|
| 1: {Name} | {1-line summary} | {Primary approach} |
| 2: {Name} | {1-line summary} | {Primary approach} |
| ... | ... | ... |

{If Data Model section exists:}
**Data changes:** {1-2 sentences about schema/migration changes}

{If System Map exists:}
**Pages involved:** {List Place names from System Map}
```

**Rules:**

- One line per phase — phase NAME + what it achieves
- "Key Pattern" = the primary technique (e.g., "assign_async for
  lazy loading", "Oban worker with unique constraint")
- Skip verification phase — it's always "run tests"
- If System Map exists, list the Places (LiveView pages) as a
  quick mental model of the UI surface area

### Section 4: Risks & Confidence

**Source**: plan.md `## Risks & Mitigations` +
`## Phase 0: Spikes` (if exists)

**Template:**

```markdown
### Risks & Confidence

{If spikes exist:}
**Unknowns to investigate first:**
- {Spike description — what we don't know yet}

**Key risks:**
| Risk | Our mitigation |
|------|---------------|
| {risk} | {mitigation, rephrased as action} |

**Confidence level:** {HIGH / MEDIUM / LOW}
- {Justify: HIGH = no spikes, familiar patterns, existing tests}
- {MEDIUM = some unknowns but mitigated}
- {LOW = spikes needed, new territory}
```

**Rules:**

- Confidence level is derived, not stated in the plan — assess
  based on: spike count, risk severity, pattern familiarity
- Spikes = unknowns that MUST be resolved before main work
- If no risks section in plan, say "No specific risks identified"
  rather than inventing concerns

---

## Post-Work Mode Sections

### Section 1: What Was Built

**Source**: plan.md `## Summary` + checkbox completion status

**Template:**

```markdown
### What Was Built

{Summary rephrased in past tense — what this feature now DOES.}

**Status:** {done}/{total} tasks completed
{If blockers:} **Blockers:** {list blocked tasks}

**Files changed:** {Count from progress.md or estimate from plan
locations}
```

**Rules:**

- Past tense throughout — "Added", "Created", "Configured"
- Be honest about incomplete tasks and blockers
- If progress.md exists, use it for accurate file counts

### Section 2: Key Decisions & Why

**Source**: Same as pre-work Section 2, plus scratchpad entries
written DURING work (DEAD-END, HANDOFF entries)

**Template:**

```markdown
### Key Decisions & Why

{Same format as pre-work Section 2, but also include:}

{If scratchpad has DEAD-END entries:}
**Approaches that didn't work:**
- {Dead-end description}: {Why it failed, what we did instead}
```

**Rules:**

- Dead-ends are valuable learning — always include them
- Implementation notes on checked tasks (e.g.,
  `[x] [P1-T3] Add user schema — citext for email`) contain
  decisions made DURING work. Extract and explain these

### Section 3: How It Was Built

**Source**: plan.md phases with `[x]` checked tasks +
implementation notes

**Template:**

```markdown
### How It Was Built

| Phase | Result | Notable Detail |
|-------|--------|---------------|
| 1: {Name} | {done}/{total} tasks | {Key implementation note} |
| 2: {Name} | {done}/{total} tasks | {Key implementation note} |
| ... | ... | ... |

{If any tasks have inline implementation notes:}
**Implementation highlights:**
- {Task}: {what was actually done vs what was planned}
```

**Rules:**

- Show completion ratio per phase
- "Notable Detail" = anything that deviated from the plan or
  was particularly interesting
- If implementation notes exist on tasks, surface the most
  important ones — deviations from plan are more interesting
  than tasks that went as expected

### Section 4: Lessons & Patterns

**Source**: plan.md `## Patterns to Follow` + `## Risks` +
scratchpad + progress.md

**Template:**

```markdown
### Lessons & Patterns

**Patterns used:**
- {Pattern from codebase that was followed}

{If risks materialized:}
**Risks that materialized:**
- {Risk}: {What actually happened and how it was handled}

{If dead-ends exist:}
**What to avoid next time:**
- {Lesson from dead-end}

**Compound candidate?** {If this solution involved a non-obvious
fix or architectural decision, suggest `/phx:compound` to capture it.}
```

**Rules:**

- Focus on what FUTURE developers should know
- Dead-ends and risk materializations are the most valuable
  lessons — always surface them
- Suggest `/phx:compound` only when there's genuinely novel
  knowledge worth capturing

---

## Handling "Ask me a question about this"

When the user selects this option between sections:

1. Wait for their question
2. Answer using ONLY information from plan artifacts (plan.md,
   scratchpad.md, summaries, progress.md)
3. If the answer isn't in the artifacts, say so: "The plan doesn't
   cover this — you may want to check with the person who created
   it or run `/phx:plan --existing` to research this aspect"
4. After answering, offer to continue to the next section

## Edge Cases

**Empty scratchpad / no summaries**: Skip rationale deep-dives,
rely only on plan.md Technical Decisions table. Note: "Limited
context available — briefing based on plan document only."

**Plan with 1-2 tasks**: Skip Section 3 (Solution Shape / How It
Was Built) — it would repeat Section 1. Go directly from
decisions to risks/lessons.

**Plan from review file**: Mention the review origin in Section 1:
"This plan addresses findings from a code review" and reference
the review file path.

**Mixed status (partially complete)**: Use post-work mode but
clearly separate completed work from remaining work in each
section.
