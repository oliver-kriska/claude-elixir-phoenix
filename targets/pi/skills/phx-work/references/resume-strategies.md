# Resume Strategies

## How State Works

**Plan checkboxes ARE the state.** No separate JSON state files.

- `[x]` = completed
- `[ ]` = pending
- Phase status `[COMPLETED|IN_PROGRESS|PENDING]` tracks phase progress
- BLOCKERs in progress file track failed tasks

## Resume Modes

### Default: Auto-detect

```
/phx:work  # Find most recent IN_PROGRESS plan, resume from first [ ]
```

### From Specific Task

```
/phx:work .claude/plans/auth/plan.md --from P2-T3
```

Skips directly to P2-T3 regardless of earlier unchecked tasks.

### Skip Blockers

```
/phx:work .claude/plans/auth/plan.md --skip-blockers
```

Continues past tasks that previously failed with BLOCKER status.

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

No state file to parse. Just find first `[ ]` and continue.

## Consistency Check

On resume, validate:

- All tasks before the target should be `[x]` in plan
- If earlier tasks are unchecked, warn and ask user:
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
