---
name: phx:autoresearch
description: "Iteratively improve Elixir/Phoenix code against a measurable metric — fix credo issues, improve test coverage, eliminate compile warnings. Use when the user says 'reduce warnings', 'improve coverage', 'fix all credo issues', 'optimize', 'clean up code', or wants automated iterative improvement with automatic rollback on failure."
effort: high
argument-hint: "[--goal credo|coverage|warnings] [--scope lib/**] [--max-iterations 15]"
---

# Autoresearch — Iterative Code Improvement

Improve code against a metric: propose change, run guard, measure, keep or revert.

## Usage

```
/phx:autoresearch --goal credo                    # Fix credo issues
/phx:autoresearch --goal coverage --scope lib/    # Improve test coverage
/phx:autoresearch --goal warnings                 # Zero compile warnings
/phx:autoresearch                                 # Interactive setup wizard
```

## Arguments

| Arg | Default | Description |
|-----|---------|-------------|
| `--goal` | (interactive) | `credo`, `coverage`, `warnings`, or custom |
| `--scope` | `lib/**/*.ex` | Glob pattern for mutable files |
| `--guard` | `mix compile --warnings-as-errors && mix test` | Must always pass |
| `--max-iterations` | 15 | Hard stop (papers show 90% gains in 5-7) |
| `--confirm` | false | Pause before each iteration |
| `--yolo` | false | No summaries, just run |

## Iron Laws

1. **NEVER touch files outside `--scope`** — check before every edit
2. **ALWAYS run guard before AND after mutation** — guard fail = immediate revert
3. **NEVER modify test/, config/, priv/repo/migrations/, mix.exs** — immutable
4. **REVERT on guard failure** — no exceptions
5. **ONE change per iteration** — atomic, reversible
6. **STOP after max iterations** — default 15
7. **AUTO-STOP on plateau** — 3 consecutive iterations <1% improvement
8. **WARN on uncovered code** — suggest tests before editing untested paths

## Step 1: Setup

If `--goal` provided, load preset from `${CLAUDE_SKILL_DIR}/references/presets.md`.
Otherwise run interactive wizard:

1. Ask goal (show 4 presets + custom option)
2. Ask scope (default: `lib/**/*.ex`)
3. Ask guard (default: `mix compile --warnings-as-errors && mix test`)
4. Show cost estimate: ~$0.05/iteration × N iterations

Validate: run guard command. If guard fails, STOP — code must be green before starting.

## Step 2: Baseline

1. Run metric command, capture numeric output → `baseline_value`
2. Run guard command → must PASS
3. Create state directory: `.claude/autoresearch/{slug}/`
4. Write `config.json` (immutable after setup)
5. Write `baseline.json` with metric + guard results
6. Print: `Baseline: {value} | Guard: PASS | Starting {max_iterations} iterations...`

If `--confirm` not set: `Press Enter to start, or type a different scope...`

## Step 3: Iteration Loop

For each iteration (see `${CLAUDE_SKILL_DIR}/references/loop-execution.md`):

1. **Propose**: Spawn `autoresearch-proposer` agent (read-only) with:
   - Current metric value + goal direction
   - Scope constraint
   - Recent failures from scratchpad (avoid repeating)
   - Agent returns: ONE proposed change (file, location, what, why)

2. **Apply**: Implement the proposed change via Edit tool
   - Verify file is within scope
   - Verify file is not in immutable list

3. **Guard**: Run guard command
   - If FAIL: `git checkout -- {file}` immediately, log to scratchpad, continue

4. **Measure**: Run metric command
   - Parse numeric output
   - Compare against previous best

5. **Decide**:
   - If improved: `git add {file} && git commit -m "autoresearch: {description}"`
   - If not improved: `git checkout -- {file}`, log to scratchpad
   - If plateau (3× <1% delta): offer to stop

6. **Log**: Append to `.claude/autoresearch/{slug}/results.jsonl`:

   ```json
   {"iteration": 1, "file": "lib/app/accounts.ex", "metric": 42, "kept": true,
    "description": "Replace filter+map with flat_map", "guard_passed": true}
   ```

7. **Summary** (unless `--yolo`): Print one-line status

## Step 4: Completion

Print final report:

```
AUTORESEARCH_COMPLETE — {kept}/{total} iterations kept
Results: {baseline} → {current} ({improvement}% {direction})
Saved to: .claude/autoresearch/{slug}/
```

Suggest: `/phx:compound` to capture lessons learned.

## References

- `${CLAUDE_SKILL_DIR}/references/presets.md` — 4 preset goals with exact commands
- `${CLAUDE_SKILL_DIR}/references/loop-execution.md` — full protocol + safety
- `${CLAUDE_SKILL_DIR}/references/session-schema.md` — JSON schemas
