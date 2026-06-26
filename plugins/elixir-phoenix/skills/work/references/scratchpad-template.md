# Structured Scratchpad Template

When creating or appending to `.claude/plans/{slug}/scratchpad.md`, use these sections.
The Reflexion paper shows structured "why" tracking improves retry success by 11 percentage points.

## Template

```markdown
# Scratchpad — {plan slug}

## Dead Ends (DO NOT RETRY)

<!-- Append failed approaches with WHY they failed. -->
<!-- This prevents the #1 waste pattern: retrying the same wrong fix. -->

## Decisions

<!-- Append key decisions with reasoning. -->
<!-- Helps future sessions understand WHY, not just WHAT. -->

## Hypotheses

<!-- Track hypotheses tested during debugging/investigation. -->
<!-- Mark as [confirmed] or [rejected] with evidence. -->

## Open Questions

<!-- Things to investigate or ask the user about. -->

## Handoff

<!-- Auto-filled on session end or interruption. -->
- Branch: (current branch)
- Plan: (active plan path)
- Last task: (what was being worked on)
- Next: (what should happen next)
```

## Section Usage

### Dead Ends

Most critical section. Write when:

- An approach failed after trying it
- A test strategy didn't work
- A library/pattern turned out unsuitable

Format:

```markdown
### Approach: {what was tried}
**Result**: Failed
**Why**: {specific reason — not just "didn't work"}
**Avoid**: {what to NOT retry}
```

### Decisions

Write when:

- Choosing between implementation approaches
- User confirms a direction
- Architecture choice is made

Format:

```markdown
### Decision: {what was decided}
**Alternatives considered**: {other options}
**Reason**: {why this was chosen}
```

### Hypotheses

Write during investigation:

```markdown
- [confirmed] N+1 in list_users — preload fixed it
- [rejected] Timeout from database — actually from external API
- [testing] Memory leak from unbounded assigns — need to verify
```

### Handoff

Auto-populated by StopFailure hook and session end.
Should contain enough info for a fresh session to continue.
