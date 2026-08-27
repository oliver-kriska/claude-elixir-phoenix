# Plan & Progress File Formats

## Plan File Format

Plans must follow this structure for parsing:

```markdown
# Plan: {Feature Name}

**Status**: IN_PROGRESS
**Created**: {date}
**Last Updated**: {date}

## Phase 1: {Phase Name} [COMPLETED|IN_PROGRESS|PENDING|BLOCKED]

- [x] [P1-T1][ecto] Completed task description — implementation note (key decisions, gotchas)
- [ ] [P1-T2][ecto] Pending task description
- [ ] [P1-T3][direct] [BLOCKED] Blocked task (remains unchecked)

## Phase 2: {Phase Name} [PENDING]

### Parallel: {Group Name}

- [ ] [P2-T1][liveview] Task that can run in parallel
- [ ] [P2-T2][liveview] Another parallel task

### Sequential

- [ ] [P2-T3][security] Task that depends on above
```

**Task format**: `- [ ] [Pn-Tm][concern] Description`; blocked tasks use `- [ ] [Pn-Tm][concern] [BLOCKED] Description`

- `[Pn-Tm]`: Phase n, Task m (for resume)
- `[concern]`: Guidance and verification annotation; never a worker identity

**Task ID format**: `[Pn-Tm]` - Phase n, Task m. Used for:

- Precise resume: `--from P2-T3`
- Blocker references
- Progress tracking

## Progress File Format

```markdown
# Progress: {Feature Name}

**Plan**: .claude/plans/{feature}/plan.md
**Started**: {date}
**Status**: IN_PROGRESS

## Session Log

### {date} {time}

**Task**: {description}
**Result**: PASS | FAIL
**Files**: {list of modified files}
**Started**: {date and time task execution began}
**Notes**: {any observations}

Progress evidence is append-only: never rewrite or delete prior Started, PASS, FAIL, retry, or blocker records.

---

### {date} {time}

**Task**: {description}
**Result**: FAIL
**Error**: {error message}
**Retry**: 1/3
**Resolution**: {what was tried}
```
