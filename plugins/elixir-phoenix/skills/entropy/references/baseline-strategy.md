# Baseline Strategy

When to save, reset, and manage entropy baselines.

## Saving a Baseline

Save when project is in a known-good state:

```
/phx:entropy --save-baseline
```

**Good times to save**:
- After `/phx:audit` returns score ≥ 80/100
- After resolving all compile warnings
- After fixing all Credo priority A/B issues
- After major release (known working state)
- After comprehensive test run passes

**Bad times to save**:
- Mid-feature (baseline will include WIP entropy)
- Right after adding a dependency (noise from new code)
- When tests are failing (locks in failures as "normal")

## Resetting a Baseline

Reset when the old baseline is no longer meaningful:

```
/phx:entropy --reset-baseline
```

**When to reset**:
- After major Elixir/Phoenix version upgrade
- After large-scale refactoring (50+ files)
- After changing project structure
- After adding/removing major dependencies
- When baseline is >3 months old

## Decision Tree

```
Is there a baseline?
├── No → Run /phx:entropy (current metrics only)
│        → If metrics look clean: --save-baseline
│        → If not: fix issues first
└── Yes → Run /phx:entropy --compare
         ├── HEALTHY → Continue working
         ├── DEGRADED → Fix regressions, then --save-baseline
         └── CRITICAL → /phx:audit --full → fix → --save-baseline
```

## Baseline File Location

`.claude/metrics/baseline.json` — tracked in git (shared across
team if using the plugin). Include in `.gitignore` if you want
per-developer baselines instead.
