---
name: phx:slfg
description: Swarm-mode autonomous pipeline. Use for parallel execution of plan tasks with concurrent review and verification for faster feature delivery.
argument-hint: <feature description>
disable-model-invocation: true
effort: high
---

# SLFG — Swarm Autonomous Pipeline

Same pipeline as `/phx:lfg` but uses swarm mode for parallel
execution where possible. Faster delivery for well-scoped features.

Inspired by Compound Engineering's SLFG workflow, adapted for
Elixir/Phoenix with parallel specialist agents and Iron Laws.

## Usage

```
/phx:slfg Add multi-tenant organization support
/phx:slfg Implement background email campaign processing
```

## How SLFG Differs from LFG

| Aspect | `/phx:lfg` | `/phx:slfg` |
|--------|------------|-------------|
| **Work phase** | Single agent, sequential | Multiple parallel subagents |
| **Review** | Sequential | Report-only parallel, then autofix |
| **Speed** | Steady | Faster for independent tasks |
| **Best for** | Dependent task chains | Plans with parallel-safe units |

## Pipeline

### Sequential Phase

#### Step 1: Plan

```
/phx:plan $ARGUMENTS
```

**GATE**: Verify plan file in `.claude/plans/`. Re-run if missing.
**Record the plan file path** for later steps.

#### Step 2: Work (Swarm Mode)

```
/phx:work <plan-path-from-step-1>
```

**Use swarm mode**: Create a task list from the plan and launch
parallel subagents for independent implementation units. Units
with dependencies run after their prerequisites complete.

Each subagent receives:

- The full plan file path
- Its specific unit's Goal, Files, Approach, Test scenarios
- Instruction to verify with `mix compile --warnings-as-errors`

**GATE**: All subagents must complete. Verify files were created
or modified beyond the plan. Do NOT proceed if no code changes.

### Parallel Phase

After work completes, launch Steps 3 and 4 as **parallel agents**:

#### Step 3: Review (Report-Only)

```
/phx:review <plan-path-from-step-1>
```

Spawn as background agent in report-only mode. Collects findings
without making changes.

#### Step 4: Verify

```
/phx:verify
```

Spawn as background agent. Run compile, format, credo, test.

Wait for BOTH to complete before continuing.

### Autofix Phase

#### Step 5: Review (Autofix)

Run sequentially after the parallel phase so it can safely mutate
the checkout. Fix any issues found in the report-only review pass.
Re-run `/phx:verify` if changes were made.

### Finalize Phase

#### Step 6: Compound

```
/phx:compound
```

Capture non-trivial solutions in `.claude/solutions/`.

#### Step 7: Done

Output `<promise>DONE</promise>` when all steps complete.

## Iron Laws

1. **NEVER skip the plan** — Even with swarm mode, planning
   structures the parallelism
2. **Swarm only independent units** — Units with shared file
   dependencies must run sequentially to avoid conflicts
3. **Report-only before autofix** — Parallel review reads code;
   sequential autofix mutates it. Never both at once
4. **Re-verify after autofix** — Any code mutation requires
   fresh `mix compile --warnings-as-errors` + `mix test`
5. **ZERO narration** — Just call tools. Only output text for
   decisions, errors, or phase transitions
6. **Compound is not optional** — Knowledge capture completes
   the cycle

## Integration

```text
/phx:slfg pipeline:

Sequential:  /phx:plan → /phx:work (swarm)
                              │
Parallel:    /phx:review (report) ─┬─ wait
             /phx:verify ──────────┘
                              │
Sequential:  /phx:review (autofix) → /phx:verify
                              │
Finalize:    /phx:compound → DONE
```

For fully autonomous execution with Ralph Wiggum Loop:

```bash
/ralph-loop:ralph-loop "/phx:slfg {feature}" --completion-promise "DONE"
```

Start with Step 1 now.
