---
name: phx:work
description: Execute implementation from a plan file. Tracks progress with checkboxes, runs verification after each task. Use when a plan.md exists and the user wants to start or resume implementation.
argument-hint: <path to plan file>
---

# Work

Execute tasks from a plan file with checkpoint tracking and verification.

## Usage

```
/phx:work .claude/plans/user-auth/plan.md
/phx:work .claude/plans/user-auth/plan.md --from P2-T3
/phx:work --skip-blockers
/phx:work  # Resumes most recent plan
```

## Arguments

- `<plan-file>` -- Path to plan file (optional, auto-detects recent)
- `--from <task-id>` -- Resume from specific task (e.g., `P2-T3`)
- `--skip-blockers` -- Continue past blocked tasks
- `--continue` -- Resume IN_PROGRESS plan from checkboxes

## Iron Laws (NON-NEGOTIABLE)

1. **NEVER auto-proceed** to /phx:review or any next workflow
   phase -- always ask the user what to do next
2. **AUTO-CONTINUE between plan phases** -- when Phase N completes,
   immediately start Phase N+1. Do NOT stop or ask for permission
   between phases. Only stop at BLOCKERS or when ALL phases are done.
3. **Plan checkboxes ARE the state** -- `[x]` = done, `[ ]` = pending.
   No separate JSON state files. Resume by reading the plan.
4. **Verify after EVERY task** -- never skip verification
5. **Max 3 retries then BLOCKER** -- don't keep retrying forever
6. **Stage specific files** -- never use `git add -A` or `git add .`

## Step 1: Research Decision

For plans with >3 tasks, ask the user:

> This plan has {count} remaining tasks across {count} phases.
>
> 1. **Start working** -- Begin immediately (familiar patterns)
> 2. **Quick research** -- Read source files first (~10 min)
> 3. **Extensive research** -- Web search + docs (~30 min)

Skip for plans with 3 or fewer simple tasks -- just start.

> **Split warning**: Plans with >10 tasks risk 2-3 context
> compactions. Suggest splitting via `/phx:plan` if not already.

## Step 2: Check Context

Check compound docs and scratchpad for prior decisions:

```bash
grep -rl "KEYWORD" .claude/solutions/ 2>/dev/null
grep -A 3 "DECISION\|DEAD-END" .claude/plans/{slug}/scratchpad.md 2>/dev/null
```

Apply findings: skip dead-ends, follow decisions. Don't load
the entire scratchpad — targeted grep only.

## Step 3: Load and Resume

Read plan file, count `[x]` (completed) vs `[ ]` (remaining).
Find first unchecked task by `[Pn-Tm]` ID.

With `--from P2-T3`: Skip to that specific task.

See `references/resume-strategies.md` for all resume modes.

## Step 4: Execute Tasks

For each unchecked task (`- [ ] [Pn-Tm][agent] Description`):

1. **Route** by `[agent]` annotation (see `references/execution-guide.md`)
2. **Implement** the task
3. **Verify**: `mix format` + `mix compile --warnings-as-errors`
   (at phase end, also run `mix test <affected>` — see tiers below)
4. **Mark** checkbox `[x]` on pass, **append implementation note**
   inline: key decisions, gotchas, actual values used. Example:
   `- [x] [P1-T3] Add user schema — citext for email, composite index on [user_id, status]`
   This survives context compaction; the plan is re-read on resume.
5. **On failure**: retry up to 3 times, then create BLOCKER
   and write DEAD-END to scratchpad (see error-recovery.md)

**Parallel groups**: Tasks under `### Parallel:` header spawn
as background subagents. See `references/execution-guide.md`
for spawning pattern, prompt template, and checkpoint flow.

**Verification tiers**:

- Per-task: `mix format` + `mix compile --warnings-as-errors`
  (when Tidewave available, also check `get_logs :error` after edits)
- Per-phase: above + `mix test <affected>` + `mix credo --strict`
- Per-feature (Tidewave): behavioral smoke test via `project_eval`
  (create record, fetch, verify -- see execution-guide.md)
- Final gate: `mix test` (full suite)

> **Linter note**: The PostToolUse hook checks formatting but does
> NOT modify files. Run `mix format` explicitly during verification
> steps or before committing.

## Step 5: Completion

Summarize results with `AskUserQuestion`:

> Implementation complete! {done}/{total} tasks finished.
> {count} files modified across {count} phases.

Options: 1. **Run review** (`/phx:review`) (Recommended),
2. **Get a briefing** (`/phx:brief` — understand what was built),
3. **Commit changes** (`/commit`), 4. **Continue manually**.

With blockers: list them, offer **Replan** (`/phx:plan`),
**Review first** (`/phx:review`), or **Handle myself**.

**After resolving blockers or dead-ends**, suggest:
"Run `/phx:compound` to document what you learned — this captures
the fix as searchable knowledge for future sessions."

**If blockers remain**, auto-write HANDOFF to scratchpad:

```markdown
### [HH:MM] HANDOFF: {plan name}
Status: {done}/{total} tasks. Blockers: {list}.
Next: {first unchecked task ID and description}.
Key decisions: {brief list from this session}.
```

This gives a fresh session context beyond just checkboxes.

**NEVER** auto-start /phx:review or any other phase.

## Step 6: Check for Additional Plans

After completion, check for other pending plans:

```bash
ls .claude/plans/*/plan.md 2>/dev/null
```

If pending plans exist, inform the user. Do NOT auto-start.

## Integration

```text
/phx:plan → /phx:work (YOU ARE HERE) → /phx:review → /phx:compound
                 ↑ ASK USER before each transition
```

## References

- `references/execution-guide.md` -- Task routing, parallel execution, verification
- `references/resume-strategies.md` -- Resume modes and state persistence
- `references/file-formats.md` -- Plan and progress file formats
- `references/error-recovery.md` -- Error handling and blockers
