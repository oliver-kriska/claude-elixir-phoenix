# Compound Workflow — Detailed Steps

## The Compounding Effect

```
Cycle 1: Fix bug → Document solution
Cycle 2: Hit similar bug → Find solution in docs → Fix faster
Cycle 3: Agent finds solution → Prevents bug before it ships
```

Each documented solution reduces future debugging time. After
10-20 solutions, agents can proactively catch known issues.

## Detailed Workflow

### Phase 1: Context Detection

#### From Arguments

```
/phx:compound Fixed N+1 query in UserListLive — was missing preload on posts
```

Extract: module=UserListLive, symptom=N+1, root_cause=missing preload

#### From Session Context

Check these sources in order:

1. **Scratchpad DEAD-END and DECISION entries**:

   ```bash
   grep -A 5 "DEAD-END\|DECISION" .claude/plans/*/scratchpad.md 2>/dev/null | tail -20
   ```

2. **Recent git changes**:

   ```bash
   git log --oneline -5
   git diff HEAD~1 --stat
   ```

3. **Progress file completions**:

   ```bash
   ls -t .claude/plans/*/progress.md 2>/dev/null | head -1
   ```

#### Trivial Fix Filter

Skip documentation for:

- Typo fixes (single character changes)
- Import/alias additions
- Config value changes
- Formatting-only changes
- Changes to fewer than 3 lines with no investigation

### Phase 2: Duplicate Detection

Search existing solutions before creating new:

```bash
grep -rl "NotLoaded\|timeout\|N+1" .claude/solutions/ 2>/dev/null
grep -rl "module: \"Accounts\"" .claude/solutions/ 2>/dev/null
```

If match found, read the file and compare:

- **Same root cause + same module**: Update existing (add new symptom)
- **Same root cause + different module**: Create new with cross-reference
- **Different root cause**: Create new (different problem)

### Phase 3: Information Gathering

```yaml
module: "Accounts"
date: "2025-12-01"
problem_type: runtime_error
component: ecto_query
symptoms:
  - "Ecto.Association.NotLoaded on user.posts"
root_cause: "missing preload on :posts association"
severity: medium
tags: [preload, association, n-plus-one]
```

Gathering strategy:

1. Check session context first (scratchpad, git diff, progress)
2. Fill what you can automatically
3. Ask user ONLY for missing critical fields

### Phase 4: Schema Validation

Validate frontmatter against `compound-docs/references/schema.md`.
Use suggested values when they fit; create descriptive labels when
they don't. Only `severity` is a strict enum.

### Phase 5: File Creation

Create in `.claude/solutions/{category}/` using the template from
`compound-docs/references/resolution-template.md`.

Filename: `{sanitized-symptom}-{module}-{YYYYMMDD}.md`

### Phase 6: Cross-Referencing

After creating the solution file:

1. Search for related solutions by tags
2. Add `related_solutions` to new file if matches found
3. Update related files to reference new solution

### Phase 7: Promotion Check

If the solution matches any of these, suggest promotion:

- **severity: critical** — Suggest adding to Iron Law checks
- **Iron Law violation** — Suggest updating iron-law-judge
- **Recurring pattern** (3+ similar) — Suggest adding to skill reference

## Integration with Other Skills

- `/phx:learn-from-fix` captures quick patterns in `common-mistakes.md`
- `/phx:compound` captures detailed solutions with full context
- `/phx:investigate` searches `.claude/solutions/` before investigating
- `/phx:plan` consults for known risks in planned areas
