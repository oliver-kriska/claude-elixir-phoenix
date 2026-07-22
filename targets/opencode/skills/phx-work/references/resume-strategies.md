# Resume Strategies

## How State Works

**Plan checkboxes ARE the state.** No separate JSON state files.

- `[x]` = completed
- `[ ]` = pending; `[ ] ... [BLOCKED] ...` = blocked and still incomplete
- Phase status `[COMPLETED|IN_PROGRESS|PENDING|BLOCKED]` tracks phase progress
- `[BLOCKED]` on the plan row is authoritative; progress records preserve blocker evidence

## Resume Modes

### Default: Auto-detect

```
/phx-work  # Resume at first unchecked non-[BLOCKED] task; stop if an earlier blocker exists
```

### From Specific Task

```
/phx-work .claude/plans/auth/plan.md --from P2-T3
```

Targets P2-T3 regardless of earlier unchecked tasks. If it is `[BLOCKED]`, this explicitly retries it and clears the tag when starting.

### Skip Blockers

```
/phx-work .claude/plans/auth/plan.md --skip-blockers
```

Skips rows visibly tagged `[BLOCKED]`; it does not infer blockers from prose or progress history.

## Resume from Interrupted Session

On resume, the plan file itself shows progress:

```markdown
## Phase 1: Schema Design [COMPLETED]
- [x] [P1-T1][ecto] Create users migration
- [x] [P1-T2][ecto] Add indexes

## Phase 2: Context Module [IN_PROGRESS]
- [x] [P2-T1][direct] Generate context
- [ ] [P2-T2][ecto] Add password_hash     <-- Resumes here
- [ ] [P2-T3][direct] Implement register_user/1
```

No state file to parse. Select the first unchecked row not tagged `[BLOCKED]`, but stop when an unresolved blocker precedes it unless `--skip-blockers` was supplied.

## Consistency Check

On resume, validate:

- Tasks before the target must be `[x]`, or visibly `[BLOCKED]` when
  `--skip-blockers` was explicitly supplied
- If another earlier task is unchecked, warn and ask the user:
  - Skip them (mark as done)?
  - Go back and complete them?
  - Something else?

## Idempotent Task Execution

Tasks should be safe to re-execute:

| Task Type | Idempotent Approach |
|-----------|---------------------|
| Migration | Use `create_if_not_exists` or check schema |
| Schema | Write complete module, don't patch |
| Context | Write/replace function entirely |
| LiveView | Write complete component module |
| Test | Write complete test module |
| Route | Check route existence before adding |

If re-executing a task creates duplicate code, the task was not
idempotent. Write whole modules, not patches.
