# Full Cycle Execution Steps

Detailed step-by-step execution for `/phx:full`.

## Step 1: Initialize

```bash
# Create feature slug
FEATURE_SLUG=$(echo "{feature}" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')

# Create directories
mkdir -p .claude/plans/${FEATURE_SLUG}/{research,reviews,summaries}

# Create feature branch (optional)
git checkout -b feature/$FEATURE_SLUG
```

## Step 2: Discovery Phase

**Purpose**: Gather context and offer user choices before committing to workflow depth.

1. **Quick Codebase Scan** (30-60 seconds):
   - Spawn `phoenix-patterns-analyst` for focused analysis
   - Look for: similar features, related contexts, existing patterns

2. **Assess Complexity**:

   | Score | Level | Recommendation |
   |-------|-------|----------------|
   | <= 2 | LOW | "just do it" -> Skip to WORKING |
   | 3-6 | MEDIUM | "plan it" -> Standard planning |
   | 7-10 | HIGH | "research it" -> Comprehensive planning (4+ agents) |
   | > 10 | CRITICAL | "research it" + security focus |

3. **Present Options**:

   ```
   ## Discovery Summary
   **Feature**: {description}
   **Complexity**: {level}
   **What I Found**: {patterns, contexts}

   **Your options**:
   - "just do it" - Quick implementation
   - "plan it" - Create plan first (standard research)
   - "research it" - Comprehensive plan with deep research
   ```

4. **Route Based on Choice**:
   - "just do it" -> Skip to Step 4 (Work Phase)
   - "plan it" -> Continue to Step 3 (Plan Phase, standard)
   - "research it" -> Continue to Step 3 (Plan Phase, comprehensive)
   - Security features -> Cannot skip planning

**Exit condition**: User selects workflow depth.

## Step 3: Plan Phase

Run `/phx:plan {feature}` (with `--detail comprehensive` for "research it"):

- Spawn research agents (1-2 for standard, 4+ for comprehensive)
- Create phased implementation plan
- Write `.claude/plans/{feature}/plan.md`

**Exit condition**: Plan file exists with checkboxes.

## Step 4: Work Phase (Loop)

Run `/phx:work .claude/plans/{feature}/plan.md`:

```
WHILE unchecked tasks exist:
  1. Find next unchecked task
  2. Route to specialist agent
  3. Execute task
  4. Run verification
  5. IF pass: Mark [x], continue
     IF fail after 3 retries: Create blocker, continue
  6. Log to progress file
```

**Exit condition**: All checkboxes marked OR max retries on blocker.

## Step 5: Review Phase

Run `/phx:review`:

Spawn 4 parallel review agents:

| Agent | Focus |
|-------|-------|
| elixir-reviewer | Idioms, patterns, code quality |
| testing-reviewer | Test coverage, patterns |
| security-analyzer | Security issues |
| verification-runner | Full test suite |

**Exit condition**: Review complete.

## Step 6: Handle Review Findings

```
IF critical issues found:
  1. Add fix tasks to plan
  2. Go to Step 4 (Work Phase)

IF only warnings:
  1. Log warnings
  2. Continue to completion

IF clean:
  1. Continue to completion
```

## Step 7: Collect Metrics & Complete

Append metrics to progress file:

```markdown
## Metrics

| Metric | Value |
|--------|-------|
| Total Duration | {time} |
| Cycles | {n} |
| Phases | {n} |
| Tasks Completed | {n} |
| Tasks Blocked | {n} |
| Retries | {n} |
| Review Issues Fixed | {n} |
| Files Modified | {n} |
| Tests Added | {n} |
```

Auto-suggest optional follow-ups:

- `/phx:document` for documentation generation
- `/phx:learn-from-fix` to capture lessons learned

Then output completion:

```markdown
## Feature Complete

**Feature**: {feature}
**Duration**: {time}
**Files Modified**: {count}
**Tests Added**: {count}

### Summary

{Brief description of what was implemented}

### Artifacts

- Plan: .claude/plans/{feature}/plan.md
- Progress: .claude/plans/{feature}/progress.md
- Review: .claude/plans/{feature}/reviews/{feature}-review.md

<promise>DONE</promise>
```
