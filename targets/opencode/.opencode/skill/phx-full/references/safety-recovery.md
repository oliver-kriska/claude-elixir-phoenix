# Safety Rails & Recovery

## Resume from Interruption

When resuming an interrupted workflow:

1. **Read progress file** `.claude/plans/{slug}/progress.md`
2. **Check plan checkboxes** in `.claude/plans/{slug}/plan.md`:
   - Count `[x]` (completed) vs `[ ]` (pending) tasks
   - Find the first unchecked task to resume from
3. **Validate artifacts**:
   - Ensure plan and progress files exist
   - Ensure completed tasks match checkboxes in plan
4. **Continue from first unchecked task**

Example resume:

```bash
/phx:full --resume magic-link-auth
# Reads .claude/plans/magic-link-auth/plan.md
# Finds first unchecked task: P2-T3
# Resumes from P2-T3
```

Or resume from specific task:

```bash
/phx:work .claude/plans/magic-link-auth/plan.md --from P2-T3
```

## Ralph Wiggum Integration

For fully autonomous execution, use with Ralph Wiggum Loop:

```bash
/ralph-loop:ralph-loop "/phx:full {feature}" --completion-promise "DONE" --max-iterations 50
```

This enables:

- Automatic recovery from context window limits
- Persistent execution across sessions
- True autonomous completion

## Automatic Stops

The cycle stops automatically when:

1. All tasks complete successfully
2. Max cycles reached
3. Max blockers reached
4. Fatal compilation error (unrecoverable)
5. Test suite completely broken (>50% failing)

## Human Checkpoints

Optional checkpoints for human review:

```
/phx:full {feature} --checkpoint-after plan
/phx:full {feature} --checkpoint-after each-phase
```

## Rollback Points

Git commits after each phase enable rollback:

```bash
# If something goes wrong
git log --oneline  # Find last good commit
git reset --hard {commit}
```

## Task-Level Checkpoints

Each completed task creates a git commit:

```bash
# View task history
git log --oneline --grep="wip(${SLUG})"

# Rollback specific task
git revert HEAD  # Reverts last task
git revert HEAD~2  # Reverts task before last

# Or reset to before task
git reset --hard HEAD~1  # Reset last task
```

## State Recovery

Plan checkboxes ARE the state. If progress file is missing,
the plan still contains all state needed to resume:

```bash
# Check current progress from plan checkboxes
COMPLETED=$(grep -c '\[x\]' .claude/plans/${SLUG}/plan.md)
TOTAL=$(grep -c '\[.*\] \[P' .claude/plans/${SLUG}/plan.md)
echo "Progress: $COMPLETED / $TOTAL tasks complete"

# Resume from first unchecked task
/phx:work .claude/plans/${SLUG}/plan.md
```
