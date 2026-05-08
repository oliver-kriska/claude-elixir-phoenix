# Error Recovery

## Verification Rules

Verification is tiered to balance speed and safety:

**Per-task** (after each task):

| Change Type | Verification Steps |
|-------------|-------------------|
| Any .ex/.exs | `mix format` + `mix compile --warnings-as-errors` |
| Schema/migration | Above + `mix ecto.migrate` (dev) |

**Per-phase** (after all tasks in a phase):

| Scope | Verification Steps |
|-------|-------------------|
| Always | `mix compile --warnings-as-errors` |
| Always | `mix test <affected_test_files>` |
| Always | `mix credo --strict` |

**Final gate** (after all phases): `mix test` (full suite)

## When Verification Fails

1. **Compile error**: Read error, fix, retry
2. **Test failure**: Analyze failure, fix code or test
3. **Credo warning**: Auto-fix if possible, else flag
4. **After 3 retries**: Log blocker, skip task, continue

## BLOCKER Format

```markdown
## BLOCKER: Task could not be completed

**Task ID**: P2-T3
**Task**: Implement register_user/1
**Attempts**: 3
**Last Error**: Test assertion failed - expected {:ok, user} got {:error, changeset}
**Files**: lib/my_app/accounts.ex:45

**Action Required**: Human review needed
**Resume**: `/phx:work plan.md --from P2-T3`
```

**Also write a DEAD-END entry** to the scratchpad so future
sessions don't re-try the same failed approach:

```markdown
### [HH:MM] DEAD-END: {task description}
Tried: {approach attempted}. Failed because: {root cause}.
Attempts: 3. See BLOCKER in progress.md for full error.
```

Append to `.claude/plans/{slug}/scratchpad.md`.

## Recovery After BLOCKER

When user resolves a blocker and resumes:

1. Re-read the plan file for current checkbox state
2. Start from the previously blocked task
3. Verify the fix compiles and tests pass
4. Mark checkbox and continue
