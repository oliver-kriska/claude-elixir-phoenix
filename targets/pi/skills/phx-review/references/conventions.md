# Review Conventions System

After a review, users can mark findings as accepted patterns (suppress
in future reviews) or new conventions (enforce in future reviews).
This prevents repeat noise and compounds review knowledge.

## Convention File

Location: `.claude/conventions.md` (project root, checked into git)

### Entry Format

```markdown
## Convention C{ID}: {Title}

- **Type**: SUPPRESS | ENFORCE
- **Source**: Review of {feature} on {date}
- **Pattern**: {code pattern or description}
- **Rationale**: {why this is accepted/required}
```

### Example Entries

```markdown
## Convention C001: Fire-and-forget analytics OK

- **Type**: SUPPRESS
- **Pattern**: Task.start(fn -> Analytics.track(...) end) without supervision
- **Rationale**: Analytics loss is acceptable, adding supervision adds complexity

## Convention C002: All context functions validate ownership

- **Type**: ENFORCE
- **Pattern**: Every public context function that modifies data must verify
  the caller owns the resource via `authorize_resource/2`
- **Rationale**: Security review found 3 unprotected mutations
```

## How Review Agents Use Conventions

At review start, if `.claude/conventions.md` exists:

1. Read the file
2. **SUPPRESS** entries: Skip findings that match the pattern. Do NOT
   report them as issues — they are intentionally accepted.
3. **ENFORCE** entries: Flag violations of enforced patterns as WARNINGS.
   These are project-specific rules beyond Iron Laws.

## Interactive Extraction Flow

After presenting review findings (Step 5), offer:

```
Any findings to convert to conventions?
- SUPPRESS: "We do this intentionally, stop flagging it"
- ENFORCE: "This should always be done this way going forward"
- Skip: No conventions to add
```

For each accepted convention:

1. Assign next sequential ID (C001, C002, ...)
2. Write to `.claude/conventions.md`
3. Attribute to the review that surfaced it
