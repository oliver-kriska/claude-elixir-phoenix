# Execution Guide

Step-by-step execution details for `/phx-work`.

## Contents

- [Loading a Plan](#loading-a-plan)
- [Concern Guidance](#concern-guidance)
- [Parallel Task Execution](#parallel-task-execution)
- [Verification](#verification)
- [Proactive Patterns](#proactive-patterns)
- [Checkpoint Pattern](#checkpoint-pattern)
- [Phase Transitions](#phase-transitions)
- [Git Integration](#git-integration)
- [Error Recovery](#error-recovery)

## Loading a Plan

Read the plan file and count progress:

```markdown
## Phase 1: Schema Design [COMPLETED]
- [x] [P1-T1][ecto] Create users migration
- [x] [P1-T2][ecto] Add indexes

## Phase 2: Context Module [IN_PROGRESS]
- [x] [P2-T1][direct] Generate context with mix phx.gen.context
- [ ] [P2-T2][ecto] Add password_hash field    <-- NEXT TASK
- [ ] [P2-T3][direct] Implement register_user/1
```

**Task ID format**: `[Pn-Tm]` where n=phase, m=task number.

With `--from P2-T3`: Skip directly to that task.

## Concern Guidance

Annotations such as `[ecto]`, `[liveview]`, `[oban]`, `[otp]`, `[security]`,
`[test]`, and `[direct]` describe implementation concerns and required checks.
They are not custom-agent identities and never route work to a named worker.
Execute in the current session by default. A native generic worker is optional
only for an independent task with disjoint files and a complete verification
contract.

| Annotation | Guidance and required verification |
|---|---|
| `[ecto]` | Ecto safety; migrate/rollback as applicable plus focused tests |
| `[liveview]` | LiveView lifecycle/security; focused LiveView test plus local/manual UI smoke |
| `[oban]` | Idempotency and args; worker test plus enqueue behavior check |
| `[otp]` | Supervision/concurrency; focused process tests |
| `[security]` | Authorization/input handling; negative-path tests and audit |
| `[test]` | Test quality; run the named focused test |
| `[direct]` | General implementation; format and compile plus affected test |

Legacy unannotated tasks use their subject matter to select the same concern
guidance, never a worker identity. Security requirements take priority.

## Parallel Task Execution

Tasks under `### Parallel:` are eligible for optional generic workers or sequential execution:

### Detection

```markdown
## Phase 2: Forms [IN_PROGRESS]

### Parallel: Deal Forms
- [ ] [P2-T1][direct] Add selectors to occupier deal form
- [ ] [P2-T2][direct] Add selectors to landlord deal form
- [ ] [P2-T3][direct] Add selectors to seller deal form

### Sequential
- [ ] [P2-T4][direct] Update shared form helpers
```

Tasks are parallelizable if they:

- Are under a `### Parallel:` header
- Modify different files (check Locations in task description)
- Don't share mutable state (schemas, helpers)

### Execution Pattern

Native generic subagents are optional for tasks that are independent and touch
different files. Give each worker the full task text, locations, constraints,
and verification contract, and wait for all workers before checkpointing.
Do not require annotation-named custom agents.

If native subagents are unavailable, execute every task sequentially in plan
order in this session. This fallback is complete: apply the same domain guidance,
verification, checkbox update, implementation note, and progress-log entry for
each task. Never skip a task because parallel execution is unavailable.

### Waiting and Checkpoint

If optional workers were used, wait for all of them; otherwise, after the sequential tasks complete, run the phase checkpoint:

```bash
mix format lib/**/*.ex lib/**/*.exs
mix compile --warnings-as-errors
mix test <affected_test_files>
mix credo --strict
```

Mark all completed task checkboxes in the plan.

### When NOT to Parallelize

- Tasks that edit the same file
- Tasks that depend on each other's output
- Schema/migration tasks (compilation lock)
- Tasks with `[security]` annotation (need careful review)

## Verification

### After Each Task

```bash
mix format --check-formatted <changed_files>
mix compile --warnings-as-errors
```

When Tidewave is independently configured, optionally inspect error-level runtime logs after code changes to catch
runtime errors invisible to static analysis (supervision tree
failures, config errors, module loading problems).

### After Each Phase (Full)

```bash
mix compile --warnings-as-errors
mix test <affected_test_files>
mix credo --strict
```

### Per-Feature Behavioral Smoke Test

Use Tidewave runtime tools only when they are independently configured and
exposed in the current environment. If available, exercise the main behavior
and inspect errors without persisting test data. Tidewave is optional, never a
completion prerequisite.

Without Tidewave, run all applicable fallbacks:

1. `mix test test/path/to/affected_test.exs`
2. Exercise the public repository/context function in a local test or `mix run`
3. For UI work, start the app locally and perform a manual browser smoke check;
   if that is impossible, record the unverified manual step explicitly

### After ALL Phases (Final Gate)

```bash
mix test  # full suite
```

### Elixir-Specific Verification

After each task, also run domain-appropriate checks:

| After | Extra Verification |
|-------|-------------------|
| `[ecto]` task | Verify migration safety, check `^` pinning |
| `[liveview]` task | Verify `connected?` check, stream usage for lists |
| `[oban]` task | Verify idempotency, string keys, no structs in args |
| `[security]` task | Verify authorization in every handle_event |

If verification fails, fix the issue and re-verify. After 3 failed
attempts, create a BLOCKER (see error-recovery.md).

## Proactive Patterns

### Factory Updates for Required Fields

When a task adds fields to `@required_fields`, BEFORE running tests:
grep for all factories/fixtures that build the affected struct
(`build(:X`, `insert(:X`, `def X_factory`), add new required fields
with sensible defaults to EVERY factory, THEN run the test suite.
Prevents cascading test failures from missing factory fields.

### Module Existence Check

When a plan says "create new module" or "extract to new module":

1. FIRST check if the module already exists:

   ```bash
   grep -rn "defmodule MyApp.ModuleName" lib/
   ```

2. If it exists, add to the existing module instead of creating a
   duplicate file (causes compilation errors from duplicate definitions)

## Checkpoint Pattern

After each task passes verification:

1. **Update plan**: Mark checkbox `- [x] [Pn-Tm]...` and **append
   implementation note** — key decisions, gotchas, actual values.
   Example: `- [x] [P2-T2] Add password_hash — used Bcrypt, 12 rounds, added virtual :password`
   These notes survive context compaction since the plan is re-read on resume.
2. **Log completion**: Append the task ID, changed files, and verification result to `progress.md`.
3. **Update phase status**: If all tasks done, change to `[COMPLETED]`
5. **Start next task**: Log its start, then select the next unchecked
   non-`[BLOCKED]` task. Stop if an unresolved blocker precedes it unless
   `--skip-blockers` was explicitly supplied

### Progress Log Entry

```markdown
## 14:32 - Task Completed [P2-T2]

**Task**: Add password_hash field to schema
**Files Modified**: lib/my_app/accounts/user.ex, priv/repo/migrations/xxx.exs
**Verification**: PASS (compile, format, credo, test)
```

## Phase Transitions

**CRITICAL: Auto-continue between phases.** When all tasks in a
phase complete, mark it `[COMPLETED]` and IMMEDIATELY start the
next phase. Do NOT stop to ask the user. Do NOT output a summary
between phases. Just keep going until all phases are done or a
BLOCKER is hit.

```markdown
# Before
## Phase 1: Schema Design [IN_PROGRESS]
- [x] [P1-T1] Create users migration
- [x] [P1-T2] Add indexes
- [x] [P1-T3] Create schema module

# After
## Phase 1: Schema Design [COMPLETED]
- [x] [P1-T1] Create users migration — citext for email, added password_hash binary field
- [x] [P1-T2] Add indexes — unique on email, composite on [user_id, status]
- [x] [P1-T3] Create schema module — used virtual :password field with redact: true

## Phase 2: Context Module [IN_PROGRESS]  <-- Auto-start immediately
```

## Git Integration

### Commit Strategy

Don't commit after every task. Instead:

1. **After each phase**: Offer to create commit with phase summary
2. **After blockers**: Commit working state before human intervention
3. **After completion**: Ask user about final commit

### Branch Strategy (for /phx-full)

```bash
git checkout -b feature/{feature-slug}
# ... phases execute ...
# On completion, ready for PR
```

## Error Recovery

### Auto-Fix (Common Errors)

| Error Pattern | Auto-Fix |
|--------------|----------|
| `mix format` diff | Run `mix format` |
| Unused variable | Prefix with `_` |
| Missing import | Add import statement |

### Retry with Context

If first attempt fails, retry with error context in the prompt.

### Escalate to BLOCKER

After 3 failures, keep the plan row unchecked, append `[BLOCKED]`, and
optionally mark its phase `[BLOCKED]`. Append the attempts and error evidence to
`.claude/plans/{slug}/progress.md`, write the dead end to `scratchpad.md`, and
stop by default. Continue to later work only with explicit `--skip-blockers`.

```markdown
- [ ] [P2-T3][ecto] [BLOCKED] Implement register_user/1

## BLOCKER: P2-T3
**Attempts**: 3
**Error history**: {commands and first actionable failures}
**Suggested next action**: {evidence-based recommendation}
```

Retry this task explicitly with the native `phx-work` invocation and
`--from P2-T3`; clear `[BLOCKED]` when starting that retry.
