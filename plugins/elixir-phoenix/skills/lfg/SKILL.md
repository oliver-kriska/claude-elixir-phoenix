---
name: phx:lfg
description: Autonomous end-to-end feature pipeline. Use when you want hands-off plan-work-verify-review-compound execution for Elixir/Phoenix features.
argument-hint: <feature description>
disable-model-invocation: true
effort: high
---

# LFG — Autonomous Feature Pipeline

Execute a complete Elixir/Phoenix feature from plan to compound
in strict sequential order. No manual gates between phases.

Inspired by Compound Engineering's LFG workflow, adapted for
Elixir/Phoenix with Iron Laws enforcement and specialist agents.

## Usage

```
/phx:lfg Add user avatars with S3 upload
/phx:lfg Implement real-time notifications with PubSub
```

## How LFG Differs from /phx:full

| Aspect | `/phx:full` | `/phx:lfg` |
|--------|-------------|------------|
| **Flow** | State machine with discovery + cycle-back | Strict linear pipeline |
| **Gates** | Interactive — asks user at transitions | Zero interaction — runs to completion |
| **Complexity** | Handles ambiguous scope, replanning | Requires clear feature description |
| **Best for** | Large/ambiguous features | Clear, well-scoped features |

**Rule of thumb**: If you need discovery or expect replanning, use
`/phx:full`. If you know what to build, use `/phx:lfg`.

## Pipeline (MANDATORY ORDER)

Execute every step in order. Do NOT skip any step. Do NOT jump
ahead to implementation. The plan phase MUST complete before work.

### Step 1: Plan

```
/phx:plan $ARGUMENTS
```

**GATE**: Verify a plan file was created in `.claude/plans/`.
If no plan file exists, run `/phx:plan $ARGUMENTS` again.
Do NOT proceed to Step 2 until a written plan exists.
**Record the plan file path** for use in Steps 2 and 3.

### Step 2: Work

```
/phx:work <plan-path-from-step-1>
```

**GATE**: Verify implementation work was performed — files were
created or modified beyond the plan itself. Do NOT proceed if
no code changes were made.

### Step 3: Verify

```
/phx:verify
```

Run the full verification loop: compile, format, credo, test.
All checks must pass before proceeding.

**GATE**: If verification fails, fix issues and re-run. Do NOT
proceed to review with failing compilation or tests.

### Step 4: Review

```
/phx:review <plan-path-from-step-1>
```

Spawn parallel specialist agents (elixir-reviewer, testing-reviewer,
security-analyzer). If review finds issues, fix them and re-run
`/phx:verify` before proceeding.

### Step 5: Compound

```
/phx:compound
```

Capture any non-trivial problems solved during implementation
as searchable solution documentation in `.claude/solutions/`.

### Step 6: Done

Output `<promise>DONE</promise>` when all steps complete.

## Iron Laws

1. **NEVER skip the plan** — Planning prevents rework. Even obvious
   features benefit from structured task breakdown
2. **NEVER skip verification** — Every phase must pass
   `mix compile --warnings-as-errors` + `mix test`
3. **Fix before proceeding** — Review findings are fixed inline,
   then re-verified. Do not defer fixes to a later step
4. **ZERO narration** — Do NOT write "Let me now...", "Next I
   will..." — just call the tool. Only output text for decisions,
   errors, or phase transitions
5. **Compound is not optional** — Knowledge capture makes the next
   feature faster. Skip only if nothing non-trivial was solved

## Integration

```text
/phx:lfg = /phx:plan → /phx:work → /phx:verify → /phx:review → /phx:compound → DONE
                                         ↑              │
                                         └── fix ───────┘
```

For fully autonomous execution with Ralph Wiggum Loop:

```bash
/ralph-loop:ralph-loop "/phx:lfg {feature}" --completion-promise "DONE"
```

Start with Step 1 now. Plan FIRST, then work. Never skip the plan.
