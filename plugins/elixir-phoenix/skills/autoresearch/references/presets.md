# Autoresearch Presets

## Credo Cleanup (`--goal credo`)

```json
{
  "name": "credo-cleanup",
  "metric_command": "mix credo --strict 2>&1 | tail -1 | grep -oP '\\d+(?= issue)' || echo 0",
  "metric_direction": "lower",
  "target": 0,
  "guard_command": "mix compile --warnings-as-errors && mix test",
  "scope_default": "lib/**/*.ex",
  "description": "Fix credo issues one at a time until zero remain"
}
```

**What the proposer should focus on**: Credo categories in priority order:

1. Consistency (naming, formatting) — easiest, safest
2. Readability (complex conditions, long functions) — moderate risk
3. Refactoring opportunities (duplicate code, large modules) — higher risk
4. Design (god modules, missing @moduledoc) — low risk

**Metric parsing**: `mix credo --strict` outputs "Found N issues" on last line.
If zero issues: "no issues found" — parse as 0.

## Test Coverage (`--goal coverage`)

```json
{
  "name": "coverage-improvement",
  "metric_command": "mix test --cover 2>&1 | grep -oP '[\\d.]+(?=%)' | tail -1 || echo 0",
  "metric_direction": "higher",
  "target": null,
  "guard_command": "mix compile --warnings-as-errors && mix test",
  "scope_default": "lib/**/*.ex",
  "description": "Write tests to improve coverage percentage"
}
```

**What the proposer should focus on**:

1. Identify uncovered modules (`mix test --cover` shows per-module %)
2. Target lowest-coverage modules first (biggest delta per test)
3. Write focused tests for public functions
4. Context modules first, then LiveViews, then helpers

**Special**: This preset allows writing to `test/**/*_test.exs` (exception to immutable rule).
Add `test/` to scope automatically: `["lib/**/*.ex", "test/**/*_test.exs"]`

## Zero Warnings (`--goal warnings`)

```json
{
  "name": "zero-warnings",
  "metric_command": "mix compile --warnings-as-errors 2>&1 | grep -c 'warning:' || echo 0",
  "metric_direction": "lower",
  "target": 0,
  "guard_command": "mix test",
  "scope_default": "lib/**/*.ex",
  "description": "Fix compile warnings until zero remain"
}
```

**What the proposer should focus on**:

1. Unused variables — prefix with `_` or remove
2. Unused imports — remove `alias`/`import` lines
3. Deprecated functions — replace with current equivalents
4. Missing return types — add `@spec` if warning requests it

**Note**: Guard uses `mix test` only (not `mix compile --warnings-as-errors`) because
the metric command IS the compile check. Guard prevents test regressions.

## Review Fixes (`--goal review-fixes`)

```json
{
  "name": "review-fixes",
  "metric_command": null,
  "metric_direction": "lower",
  "target": 0,
  "guard_command": "mix compile --warnings-as-errors && mix test",
  "scope_default": null,
  "description": "Fix findings from /phx:review output"
}
```

**Special handling**: This preset reads review files from `.claude/plans/*/reviews/`.
Counts BLOCKER + WARNING findings (skips SUGGESTION). Each iteration fixes one finding.
Metric = remaining unfixed findings count.

**Scope**: Derived from review findings (files mentioned in findings).
