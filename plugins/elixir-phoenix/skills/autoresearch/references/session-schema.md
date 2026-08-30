# Session Schemas

## State Directory

```
.claude/autoresearch/{slug}/
├── config.json      # Immutable after setup
├── results.jsonl    # Append-only iteration log
├── baseline.json    # Initial measurements
├── progress.md      # Human-readable summary (updated each iteration)
└── scratchpad.md    # Failed approaches, strategy notes
```

## config.json

```json
{
  "slug": "credo-cleanup",
  "goal": "credo",
  "metric_command": "mix credo --strict 2>&1 | tail -1 | grep -oP '\\d+(?= issue)' || echo 0",
  "metric_direction": "lower",
  "target": 0,
  "guard_command": "mix compile --warnings-as-errors && mix test",
  "scope": ["lib/**/*.ex"],
  "immutable": ["test/", "config/", "priv/repo/migrations/", "mix.exs"],
  "max_iterations": 15,
  "created_at": "2026-03-25T12:00:00Z"
}
```

## baseline.json

```json
{
  "metric_value": 47,
  "guard_passed": true,
  "guard_output": "Compiling 0 files (.ex)\n142 tests, 0 failures",
  "timestamp": "2026-03-25T12:00:05Z"
}
```

## results.jsonl (one line per iteration)

```json
{"iteration": 1, "file": "lib/my_app/accounts.ex", "metric_before": 47, "metric_after": 45, "kept": true, "guard_passed": true, "description": "Replace Enum.filter+map with flat_map", "timestamp": "2026-03-25T12:01:00Z"}
{"iteration": 2, "file": "lib/my_app/orders.ex", "metric_before": 45, "metric_after": 45, "kept": false, "guard_passed": true, "description": "Extract helper function — no metric improvement", "timestamp": "2026-03-25T12:02:30Z"}
{"iteration": 3, "file": "lib/my_app/search.ex", "metric_before": 45, "metric_after": 45, "kept": false, "guard_passed": false, "description": "Rename variable — test failure in search_test.exs:42", "timestamp": "2026-03-25T12:04:00Z"}
```

## progress.md (human-readable, updated each iteration)

```markdown
# Autoresearch: credo-cleanup

**Status**: Running (8/15 iterations)
**Metric**: 47 → 23 credo issues (51% reduction)
**Guard**: mix compile --warnings-as-errors && mix test

## Iterations
| # | File | Change | Metric | Kept |
|---|------|--------|--------|------|
| 1 | accounts.ex | filter+map → flat_map | 47→45 | Yes |
| 2 | orders.ex | Extract helper | 45→45 | No |
| 3 | search.ex | Rename variable | GUARD FAIL | No |
...
```

## scratchpad.md (append-only failure log)

```markdown
# Scratchpad — credo-cleanup

## Failed Approaches
- Iteration 2: Extracting helper in orders.ex didn't change credo count (was refactoring, not credo fix)
- Iteration 3: Renaming `result` to `query_result` in search.ex broke test assertion on line 42
  AVOID: Don't rename variables in search.ex without checking search_test.exs assertions

## Strategy Notes
- Credo consistency issues (naming) are safest — fix those first
- Readability issues require more careful test verification
- Skip design issues (missing @moduledoc) — they don't reduce issue count in --strict mode
```
