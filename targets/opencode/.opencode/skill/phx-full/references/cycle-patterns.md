# Cycle Patterns for Autonomous Development

## State Persistence

### Progress File Schema

```markdown
# Progress: {feature}

## Metadata
- **Feature**: {feature description}
- **Slug**: {feature-slug}
- **State**: WORKING
- **Cycle**: 2/10
- **Started**: 2024-01-15 10:30:00
- **Last Update**: 2024-01-15 11:45:00

## Files

| Type | Path |
|------|------|
| Plan | .claude/plans/{slug}/plan.md |
| Progress | .claude/plans/{slug}/progress.md |
| Review | .claude/plans/{slug}/reviews/{slug}-review.md |

## Phase Progress

| Phase | Status | Tasks | Completed |
|-------|--------|-------|-----------|
| 1. Schema | COMPLETED | 3 | 3 |
| 2. Context | IN_PROGRESS | 4 | 2 |
| 3. LiveView | PENDING | 5 | 0 |
| 4. Tests | PENDING | 4 | 0 |

## Current Task

**Phase**: 2
**Task**: 3/4
**Description**: Implement verify_magic_token/1
**Attempt**: 2/3

## Session Log

### 11:45:00 - Task Failed
- Task: Implement verify_magic_token/1
- Error: Test assertion failed
- Retry: 1/3

### 11:42:00 - Task Completed
- Task: Implement create_magic_token/1
- Files: lib/my_app/auth.ex
- Verification: PASS

### 11:35:00 - Task Completed
- Task: Generate Auth context
- Files: lib/my_app/auth.ex, lib/my_app/auth/magic_token.ex
- Verification: PASS
```

## Recovery Patterns

### Context Window Reset

When context window fills, Claude loses memory. Recovery:

1. **Read progress file** to restore state
2. **Read plan file** to find current task
3. **Continue from checkpoint**

```
# Recovery prompt (auto-generated)
Resume feature development:
- Progress file: .claude/plans/{slug}/progress.md
- Current state: WORKING
- Current phase: 2
- Current task: 3/4
- Last error: {error from progress file}

Continue with /phx:work .claude/plans/{slug}/plan.md
```

### Session Restart

If session ends unexpectedly:

```bash
# Find most recent progress
ls -t .claude/plans/*/progress.md | head -1

# Check state
grep "State:" .claude/plans/*/progress.md | head -1

# Resume
/phx:work .claude/plans/{slug}/plan.md
```

### Blocker Recovery

When human resolves a blocker:

```bash
# Mark blocker resolved in progress file
# Then resume
/phx:work .claude/plans/{slug}/plan.md --from {task-id}
```

## Cycle Optimization

### Fast Path

For simple features (detected during discovery):

```
Simple feature detected (1 context, <5 files)
→ Skip comprehensive research
→ Minimal plan
→ Direct implementation
→ Quick review
```

### Parallel Phases

Some phases can overlap:

```
Phase 2: Context     ████████████
Phase 3: LiveView         ████████████  (starts when context API stable)
Phase 4: Tests                 ████████████  (starts with Phase 2)
```

### Incremental Review

Don't wait until end for review:

```
Phase 1 complete → Quick review
Phase 2 complete → Quick review
All phases complete → Full review
```

## Failure Modes

### Recoverable Failures

| Failure | Recovery |
|---------|----------|
| Test failure | Analyze, fix, retry |
| Compile error | Read error, fix, retry |
| Credo warning | Auto-fix or skip |
| Format issue | Run mix format |

### Non-Recoverable Failures

| Failure | Action |
|---------|--------|
| Schema design flaw | Stop, return to planning |
| Wrong approach | Stop, return to planning |
| External dependency down | Stop, wait, retry later |
| Max retries exceeded | Create blocker, continue |

### Cascade Prevention

Prevent one failure from cascading:

```
IF task fails 3 times:
  - Mark as blocker
  - Check if dependent tasks can proceed
  - IF yes: Continue with independent tasks
  - IF no: Mark phase as blocked, try next phase
```

## Metrics Tracking

Track for learning:

```markdown
## Metrics

| Metric | Value |
|--------|-------|
| Total Duration | 45 minutes |
| Cycles | 2 |
| Tasks Completed | 16 |
| Tasks Blocked | 1 |
| Retries | 4 |
| Review Issues | 3 |
| Tests Added | 12 |
| Test Coverage Delta | +5% |
```

## Advanced: Multi-Feature Coordination

When implementing related features:

```
Feature A: User Registration
Feature B: User Profile (depends on A)
Feature C: User Settings (depends on A)

Execution:
1. Complete Feature A
2. Start B and C in parallel (different agents)
3. Sync at integration points
```

## Integration with CI/CD

On completion, optionally trigger:

```bash
# Create PR
gh pr create --title "feat: {feature}" --body "$(cat .claude/plans/{slug}/reviews/{slug}-review.md)"

# Run CI
gh workflow run ci.yml

# Notify
echo "Feature complete: {feature}" | slack-notify
```
