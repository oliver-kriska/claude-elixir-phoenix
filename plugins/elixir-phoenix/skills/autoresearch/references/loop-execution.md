# Loop Execution Protocol

## Git Safety

Before first iteration:

```bash
git stash  # Save any uncommitted work
# OR create a branch:
git checkout -b autoresearch/{slug}
```

Per iteration:

1. Edit file(s) within scope
2. Run guard → if FAIL: `git checkout -- {files}` immediately
3. Run metric → if not improved: `git checkout -- {files}`
4. If improved: `git add {files} && git commit -m "autoresearch: {description}"`

On completion: summarize changes, suggest `git stash pop` if stashed.

## Scope Enforcement

Before EVERY edit, verify:

```
1. File matches --scope glob pattern
2. File is NOT in immutable list: test/, config/, priv/repo/migrations/, mix.exs
3. Exception: --goal coverage adds test/**/*_test.exs to allowed scope
```

If edit would touch out-of-scope file: SKIP that proposal, ask proposer for alternative.

## Staged Evaluation (fast-then-full)

Run cheap checks first — skip expensive checks if cheap ones fail.
This prevents wasting 30s+ on `mix test` when `mix compile` already fails.
(From Hyperagents paper: staged eval with threshold saves 60%+ time on bad variants.)

**Stage 1 — Compile (5s)**:

```bash
mix compile --warnings-as-errors
```

If FAIL: revert immediately. Do NOT run further stages.

**Stage 2 — Metric-specific check (5-15s)**:

- `--goal credo`: `mix credo --strict` (is the count lower?)
- `--goal warnings`: already checked in Stage 1
- `--goal coverage`: skip (needs full test suite)

If metric didn't improve: revert. Do NOT run Stage 3.

**Stage 3 — Full guard (30s+)**:

```bash
mix test
```

Only runs if Stages 1-2 passed. This is the expensive step.

## Guard Execution

Guard runs TWICE per iteration:

1. **Pre-mutation guard** (first iteration only): Verify codebase is green before starting
2. **Post-mutation guard**: Staged — compile first, metric second, full test last

Guard failure at ANY stage = immediate revert. Log which stage failed to scratchpad:

```
Iteration 5: STAGE 1 FAIL — mix compile error after editing accounts.ex
Reverted. Skipped credo + test (saved ~35s).

Iteration 8: STAGE 3 FAIL — test/accounts_test.exs:42 failed after editing accounts.ex
Reverted. Avoid: modifying validate_email/1 breaks existing test expectations.
```

## Metric Parsing

Metric command must output a single number. Parsing rules:

- Capture last number in output: `grep -oP '\d+\.?\d*' | tail -1`
- If empty output: treat as error, skip iteration
- If non-numeric: treat as error, skip iteration

Direction interpretation:

- `lower`: new < previous = improvement
- `higher`: new > previous = improvement

## Plateau Detection

Track last 3 metric values. Compute deltas:

```
delta_1 = |metric[n] - metric[n-1]| / metric[n-1]
delta_2 = |metric[n-1] - metric[n-2]| / metric[n-2]
delta_3 = |metric[n-2] - metric[n-3]| / metric[n-3]
```

If all 3 deltas < 0.01 (1%): plateau detected.

Response (unless --yolo):

```
Plateau detected — metric improved <1% in last 3 iterations.
Current: {value} (was {baseline}, {improvement}% total)
[1] Stop here (recommended)
[2] Continue 5 more
[3] Switch to different file/approach
```

## Proposer Integration

Spawn `autoresearch-proposer` agent with this prompt template:

```
You are proposing ONE code improvement for an Elixir/Phoenix project.

GOAL: {goal_description}
METRIC: {metric_name} = {current_value} (target: {target}, direction: {direction})
SCOPE: Only files matching {scope_pattern}
GUARD: {guard_command} must pass after your change

RECENT FAILURES (do NOT repeat these):
{scratchpad_last_5_entries}

PREVIOUS IMPROVEMENTS (build on these):
{last_3_kept_descriptions}

Propose exactly ONE change:
- Which file to edit
- What to change (be specific: line range, function name)
- Why this will improve the metric
- Estimated metric impact

Reply with a JSON block:
{"file": "lib/...", "change": "description", "why": "reason", "risk": "low|medium"}
```

## Scratchpad Management

`.claude/autoresearch/{slug}/scratchpad.md` tracks:

- Failed approaches (with WHY they failed)
- Guard failures (which tests broke)
- Metric regressions (what got worse)
- Strategy notes (what's working, what isn't)

Read scratchpad EVERY iteration. Feed last 5 entries to proposer.
This prevents the #1 failure mode: repeating the same failed fix (Conversational APR paper).

## Autonomy Tiers

| Mode | Behavior |
|------|----------|
| `--confirm` | Before each edit: show proposal, ask Y/n/skip |
| default | Run automatically, print one-line per iteration |
| `--yolo` | No output until completion report |

## Error Recovery

| Error | Response |
|-------|----------|
| Guard fails | Revert immediately, log to scratchpad |
| Metric command fails | Skip iteration, log error |
| Proposer returns empty | Try random file in scope |
| Git conflict | Abort, print state, suggest manual resolution |
| Context exhaustion | Write state to files, print resume command |

## Resume Protocol

On session start, check for `.claude/autoresearch/*/config.json`.
If found and `results.jsonl` shows incomplete (iterations < max):

```
Active autoresearch: "{slug}"
  Progress: {done}/{max} iterations | Metric: {baseline} → {current}
  Resume? [Y/n]
```

Resume reads config.json + results.jsonl + scratchpad.md to continue.
