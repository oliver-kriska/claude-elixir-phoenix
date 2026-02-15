# Execution Guide

Step-by-step execution details for `/phx:work`.

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

## Task Routing

### Primary: Parse Agent Annotation

Task format: `- [ ] [Pn-Tm][agent] Description`

```markdown
- [ ] [P2-T2][ecto] Add password_hash field to schema
                ^^^^
           Parse this annotation -> spawn ecto-schema-designer
```

### Routing Table

| Annotation | Agent | Verification |
|------------|-------|--------------|
| `[ecto]` | ecto-schema-designer | migrate + test |
| `[liveview]` | liveview-architect | test + browser |
| `[oban]` | oban-specialist | test + manual |
| `[otp]` | otp-advisor | test |
| `[security]` | security-analyzer | test + audit |
| `[test]` | testing-reviewer | test only |
| `[direct]` | (none) | compile + format |

### Fallback: Keyword Matching (Legacy Plans)

If no `[agent]` annotation, fall back to keywords:

| Keywords (priority order) | Agent |
|---------------------------|-------|
| auth, login, password, token, permission | security-analyzer |
| schema, migration, field, changeset | ecto-schema-designer |
| worker, job, queue, oban | oban-specialist |
| genserver, supervisor, process | otp-advisor |
| liveview, component, mount | liveview-architect |
| test, assert, mock | testing-reviewer |
| (no match) | (direct execution) |

**Security priority**: Security keywords ALWAYS win, even if other
patterns match.

### `[direct]` Task Guidance

Tasks annotated `[direct]` are simple and don't need a specialist:

- **Config changes**: Adding env vars, updating `config/runtime.exs`
- **Dependencies**: Adding libraries to `mix.exs`, running `mix deps.get`
- **Scaffolding**: Creating directory structure, empty modules
- **Simple wiring**: Adding routes, imports, aliases
- **File operations**: Moving, renaming, or deleting files

Implement these directly without spawning a Task agent. Run
verification (compile + format) after each one.

## Parallel Task Execution

Tasks under `### Parallel:` header execute via subagents:

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

### Spawning Pattern

Spawn ALL parallel tasks in ONE message using the Task tool:

```
Task({
  subagent_type: "general-purpose",
  prompt: "Implement P2-T1: Add currency/area unit selectors to
    occupier deal form at lib/.../occupier_deal/.../details_form.ex.
    [full task context here]",
  run_in_background: true,
  mode: "bypassPermissions"
})
Task({
  subagent_type: "general-purpose",
  prompt: "Implement P2-T2: Add selectors to landlord deal form...",
  run_in_background: true,
  mode: "bypassPermissions"
})
// ... one per parallel task
```

### Waiting and Checkpoint

After spawning, wait for ALL agents to complete, then run phase checkpoint:

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

When Tidewave is available, also call
`mcp__tidewave__get_logs level: :error` after code changes to catch
runtime errors invisible to static analysis (supervision tree
failures, config errors, module loading problems).

### After Each Phase (Full)

```bash
mix compile --warnings-as-errors
mix test <affected_test_files>
mix credo --strict
```

### Per-Feature Behavioral Smoke Test (Tidewave)

After completing a feature (all phases for a domain), use
`project_eval` to verify end-to-end behavior. Pick the smoke
test by task annotation:

| Annotation | Smoke Test Pattern |
|------------|-------------------|
| `[ecto]` | `project_eval`: Create record -> fetch -> verify fields match |
| `[liveview]` | `get_logs level: :error` after navigation to the new route |
| `[oban]` | `project_eval`: Enqueue job -> check `oban_jobs` table for state |
| `[security]` | `project_eval`: Test unauthenticated access returns error |
| `[direct]` | `get_logs level: :error` to verify no regressions |

Use `project_eval` with transaction + rollback to verify without
persisting data. This catches issues unit tests miss: association
loading, default values, database constraints, and trigger behavior.

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

When a task adds fields to `@required_fields` in a schema changeset,
BEFORE running tests:

1. Grep for all factories/fixtures that build the affected struct:

   ```bash
   grep -rn "build(:deal" test/ --include="*.exs"
   grep -rn "insert(:deal" test/ --include="*.exs"
   grep -rn "params_for(:deal" test/ --include="*.exs"
   ```

2. Also check factory definitions:

   ```bash
   grep -rn "def deal_factory" test/ --include="*.exs"
   ```

3. Add the new required fields with sensible defaults to EVERY factory
4. THEN run the test suite

This prevents cascading test failures (the ENA-7980 session hit 21
failures from missing factory fields that took ~3 min to debug).

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
2. **Update phase status**: If all tasks done, change to `[COMPLETED]`
3. **Log progress**: Append to `.claude/plans/{feature}/progress.md`
4. **Continue**: Move to next unchecked task

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

### Branch Strategy (for /phx:full)

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

After 3 failures, create blocker in progress file:

```markdown
## BLOCKER

**Task ID**: P2-T3
**Description**: Implement register_user/1
**Attempts**: 3

**Error History**:
1. Compile error: undefined function hash_password/1
2. Test failure: expected {:ok, _} got {:error, changeset}
3. Test failure: changeset errors [:email, "has already been taken"]

**Suggested Actions**:
- Review test setup (database not cleaned?)
- Check hash_password/1 implementation
- Verify unique constraint handling

**Resume**: `/phx:work plan.md --from P2-T3`
```
