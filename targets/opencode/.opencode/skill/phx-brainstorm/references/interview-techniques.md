# Interview Techniques Reference

Detailed methodology for the adaptive interview phase of `/phx:brainstorm`.

## Coverage Scoring Algorithm

Each of the 6 dimensions scores 0-2:

| Score | Meaning | Example |
|-------|---------|---------|
| 0 | Uncovered | Dimension not mentioned |
| 1 | Partial | Vague reference ("maybe some caching") |
| 2 | Sufficient | Concrete detail ("Redis cache for session tokens, 15min TTL") |

**Interview sufficient** when total >= 8/12 (at least 4 dimensions fully covered).

### Scoring Rules

- User's initial topic description often covers What (1-2) and Why (0-1) immediately
- Don't re-ask dimensions already at 2 — advance to uncovered ones
- If user gives a comprehensive answer covering 3+ dimensions, score all at once
- After each answer, mentally update scores and pick the lowest-scoring dimension next
- **Ask Scope within the first 3-4 questions** — especially for "optimize X" or
  "improve X" topics where scope (upstream OK? local-only? CI vs dev?) determines
  which research approaches are viable. Don't let scope emerge during research

### Recommended Question Order

1. **What** — almost always first (unless initial description is already concrete)
2. **Why** — understand motivation before narrowing
3. **Scope** — set boundaries EARLY so research doesn't explore out-of-scope approaches
4. **Where/How/Edge** — informed by codebase scans, order by lowest coverage

## Question Templates by Dimension

### What (specific behavior)

- "What exactly should happen when a user {action}? Walk me through the flow."
- "You mentioned {feature} — is that a new page, a component on an existing page,
  or a background process?"
- "Can you describe the happy path end-to-end? User does X, sees Y, system does Z."

### Why (problem and need)

- "What problem does this solve? What's happening today that's painful?"
- "Who benefits from this — end users, admins, or internal team?"
- "What triggered this? A bug report, user feedback, or a new business requirement?"

### Scope (ask early — within first 3-4 questions)

- "What's explicitly NOT part of this? Any features to defer to v2?"
- "Are upstream library changes acceptable, or local-only solutions?"
- "Is this for dev workflow, CI, production, or all three?"
- "Do we need to migrate existing data, or is this for new records only?"

### Where (codebase location)

After scanning the codebase:

- "I see you have contexts: {list}. Which one should own this, or is it a new domain?"
- "Your router has {N} scopes. Where should this route live?"
- "There's an existing {Module} that handles similar things. Should this extend it
  or be separate?"

### How (approach and constraints)

- "Any technical constraints I should know? Performance targets, compatibility,
  specific libraries you want to use or avoid?"
- "I found {existing_pattern} in your codebase. Should we follow the same approach?"
- "Real-time or eventual consistency? Does this need PubSub/LiveView updates?"

### Edge Cases

- "What happens when {operation} fails? Should we retry, notify, or silently log?"
- "How many {items} are we talking about? 10s, 1000s, or millions?"
- "Who has permission to do this? Any authorization checks needed?"

## Codebase Scan Patterns

When the user mentions a topic, scan BEFORE asking the next question:

| User mentions | Grep/Glob pattern | What to look for |
|---------------|-------------------|------------------|
| authentication, auth, login | `**/*auth*.ex`, `**/*session*.ex` | Guardian, Pow, custom plugs |
| real-time, live, updates | `**/*_live.ex`, `**/*channel*.ex` | PubSub topics, socket setup |
| background, jobs, async | `**/*worker*.ex`, `**/workers/**` | Oban workers, queue config |
| upload, files, images | `**/*upload*`, `**/*attachment*` | LiveView uploads, S3 config |
| email, notification | `**/*email*`, `**/*notification*` | Swoosh, mailer config |
| API, endpoint, REST | `**/*controller*.ex`, `**/*json*` | API controllers, JSON views |
| payment, billing | `**/*payment*`, `**/*billing*` | Stripe, decimal fields |
| search, filter | `**/*search*`, `**/*filter*` | Ecto queries, full-text |
| admin, dashboard | `**/*admin*`, `**/admin/**` | Admin routes, auth plugs |
| database, schema, migration | `**/migrations/*.exs`, `**/*schema*` | Recent migrations, schemas |
| test, testing | `test/**/*_test.exs` | Test patterns, factories |
| deploy, production | `config/runtime.exs`, `Dockerfile` | Deploy config, env vars |

### Scan Depth Rules

- **First mention of a topic**: Medium scan — Grep + Read 1-2 key files (~5s)
- **Follow-up on same topic**: Light scan — Grep only, check for new patterns (~2s)
- **User asks "what do I have?"**: Full scan — Glob + Grep + Read multiple files (~10s)
- **Never**: spawn an agent for scanning during interview (too slow, breaks flow)

## Signal Detection

### Vague Answer Signals

Detect these patterns in user responses:

- "Something like...", "maybe", "I'm not sure", "kind of"
- Very short answers (< 20 words) to open-ended questions
- Deflection: "whatever you think is best", "the usual way"

**Response**: Probe deeper on the SAME dimension with a more specific question.
Offer concrete options: "Would it be more like A or B?"

### Expertise Signals

Detect when user demonstrates technical knowledge:

- Uses framework-specific terms correctly (GenServer, LiveView, Ecto.Multi)
- References specific modules, functions, or patterns
- Provides implementation-level detail unprompted

**Response**: Skip basic questions. Ask at the implementation level:
"Should this use `assign_async` or a custom `GenServer` for the background fetch?"

### Scope Creep Signals

Detect when an answer introduces too much new scope:

- Answer mentions 3+ new features or systems not in original topic
- "And also we could...", "while we're at it..."
- Answer would require touching 5+ contexts

**Response**: Acknowledge, then gently narrow: "Those are great ideas. For this
brainstorm, should we focus on {core feature} first, and note {extras} as future work?"

### Saturation Signals

Detect when interview is reaching diminishing returns:

- 2 consecutive answers add no new coverage (same dimensions, same scores)
- User answers become shorter or repetitive
- All 6 dimensions at >= 1 (partial coverage everywhere)

**Response**: "I think I have a solid picture. Ready to look at next steps?"
Present Decision Point.

## interview.md Output Format

Write to `.claude/plans/{slug}/interview.md`:

```markdown
# Brainstorm: {Topic}

**Status**: COMPLETE | IN_PROGRESS
**Date**: {YYYY-MM-DD}
**Coverage**: What ██░░ | Why ████ | Where ███░ | How ██░░ | Edge ░░░░ | Scope ████
**Score**: {N}/12

## Summary

{3-5 sentence synthesis of what was gathered. Written as requirements, not as
a transcript recap. Focus on WHAT the user wants, WHY, and key constraints.}

## Coverage Details

### What ({score}/2)

{Synthesized understanding of the desired behavior}

### Why ({score}/2)

{Problem statement and user need}

### Where ({score}/2)

{Affected modules, contexts, routes. Include file paths found during scans.}

### How ({score}/2)

{Technical approach preferences, constraints, patterns to follow}

### Edge Cases ({score}/2)

{Error handling, scale, permissions, failure modes}

### Scope ({score}/2)

{What's in, what's explicitly out, v1 vs future}

## Codebase Context

{Key findings from between-question scans. Existing patterns, relevant modules,
current architecture that informs the plan.}

## Research Findings

{Populated after Research phase. Empty if user chose plan/store without research.}

### Approaches Found

#### Approach 1: {name}
- **Thesis**: {why it works for this codebase}
- **Antithesis**: {why it might not}
- **Key files**: {existing files that would change}

#### Approach 2: {name}
...

## Open Questions

- {Anything still unclear or needing investigation}
- {Topics where research was suggested but not done}

## Transcript

### Q1: {question}
**Context scan**: {what Grep/Glob found before this question}
**Answer**: {verbatim user response}
**Coverage update**: What 0→1, Why 0→1

### Q2: {question}
**Context scan**: {scan results}
**Answer**: {verbatim}
**Coverage update**: Where 0→2

...
```

### Format Notes

- **Summary section** is what `/phx:plan` reads first — must be self-contained
- **Coverage Details** replace `/phx:plan`'s clarification questions
- **Codebase Context** replaces the patterns-analyst research in `/phx:plan`
- **Transcript** at the bottom for audit trail — not consumed by `/phx:plan`
- **Status: COMPLETE** means all dimensions >= 1 and total >= 8
- **Status: IN_PROGRESS** means user chose "Store & exit" before sufficient coverage
