---
name: phx:entropy
description: Detect quality drift by comparing project metrics against a baseline. Lightweight alternative to full audit for post-workflow health checks.
argument-hint: [--save-baseline|--reset-baseline|--compare]
---

# Entropy Detection

Detect gradual quality degradation (entropy) by comparing current
project metrics against a saved baseline.

## Usage

```
/phx:entropy                  # Compare current metrics to baseline
/phx:entropy --save-baseline  # Save current metrics as baseline
/phx:entropy --reset-baseline # Delete baseline, start fresh
/phx:entropy --compare        # Show comparison without baseline update
```

## What It Detects

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| Compile warnings | 0 | 1-3 | 4+ |
| Credo violations | ≤5 | 6-15 | 16+ |
| Circular deps | 0 | 1 | 2+ |
| Test failures | 0 | 1-2 | 3+ |
| Dead code (unreachable) | ≤3 | 4-10 | 11+ |

## Iron Laws

1. **Entropy checks are NEVER blocking** — purely informational
2. **Baseline is opt-in** — no baseline = no comparison, just current metrics
3. **Skip slow checks** — no Dialyzer, no full test suite (use `/phx:verify` for that)

## When to Run

- After `/phx:full` completions (auto-suggested)
- Before major releases (pair with `/phx:audit`)
- When starting a new session on a project after time away
- When you notice "things feel slower" or "more warnings than usual"

## Baseline Management

Baseline saved to `.claude/metrics/baseline.json`:

```json
{
  "timestamp": "2026-02-24T10:30:00Z",
  "scores": {
    "compile_warnings": 0,
    "credo_violations": 5,
    "circular_deps": 0,
    "test_count": 142,
    "test_failures": 0,
    "dead_code": 2,
    "module_count": 85
  }
}
```

**When to save new baseline**:
- After `/phx:audit` with clean results
- After resolving all regressions
- After major release/milestone

**When to reset**:
- After large refactor changes project structure
- After upgrading Elixir/Phoenix versions

## Health Status

| Status | Meaning | Action |
|--------|---------|--------|
| HEALTHY | No regressions | None needed |
| DEGRADED | 1-2 regressions | Run `/phx:audit --gc` |
| CRITICAL | 3+ regressions | Run `/phx:audit --full` |

## Integration

```text
/phx:full → COMPLETED → /phx:entropy (auto-check)
/phx:audit --gc ← DEGRADED/CRITICAL findings
```

## References

- `references/metrics-glossary.md` — What each metric means
- `references/entropy-patterns.md` — Common drift scenarios
- `references/baseline-strategy.md` — When to save/reset baseline
