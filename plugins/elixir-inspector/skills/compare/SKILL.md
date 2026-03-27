---
name: ei:compare
description: >
  Compare current Inspector scan against a previous scan to show Credo, Ecto, and architecture
  improvements, regressions, and trend lines. Use after running /ei:scan twice, or when asking
  did we improve, what changed since last scan, show me progress, compare scans, what got fixed,
  any regressions. Do NOT trigger for single audit or first-time scan.
effort: low
argument-hint: "[previous-scan-path]"
---

# Inspector Compare — Scan Diff

Compare the current scan against a previous scan to track improvement over time.

```
/ei:compare                          # Auto-find most recent history scan
/ei:compare .claude/inspector/history/scan-2026-03-15.json  # Specific baseline
```

## Prerequisites

- `.claude/inspector/findings-merged.json` from a recent `/ei:scan`
- At least one previous scan in `.claude/inspector/history/scan-*.json`
  (created automatically by `/ei:scan` — see scan skill's history saving)

## Iron Laws

1. **Match findings by ID + title similarity** — IDs may shift between scans; use category + title fuzzy match as fallback
2. **Never modify scan files** — comparison is read-only
3. **Show net delta clearly** — user must see at a glance: improving, stable, or regressing

## Workflow

### Step 1: Load Current Scan

Read `.claude/inspector/findings-merged.json`.
If not found: "No current scan results. Run `/ei:scan` first."

Extract: total findings, findings list (each has id, title, category, severity, automatable, priority_score).

### Step 2: Find Previous Scan

If `$ARGUMENTS` provides a path, read that file.

Otherwise, use Glob to find `.claude/inspector/history/scan-*.json` files.
Pick the most recent one (by filename date sort). If none found:
"No scan history found. Run `/ei:scan` again after your changes — the scan auto-saves history."

### Step 3: Compare Findings

For each finding, match between previous and current using this priority:

1. **Exact ID match** (e.g., L3-007 in both)
2. **Category + title similarity** — same category and title overlap >60% (handles ID renumbering)

Classify each finding into one of:

| Status | Meaning |
|--------|---------|
| **Resolved** | In previous, not in current — finding was fixed |
| **New** | In current, not in previous — new issue appeared |
| **Severity changed** | Same finding, different severity (improved or worsened) |
| **Unchanged** | Same finding, same severity — still present |

### Step 4: Compute Metrics Delta

Build a comparison table from both scans:

| Metric | Previous | Current | Delta |
|--------|----------|---------|-------|
| Total findings | `prev.total_findings` | `curr.total_findings` | difference |
| High severity | count where severity=high/critical | same | difference |
| Automatable | `prev.automatable_count` | `curr.automatable_count` | difference |

### Step 5: Present Comparison

Format output as:

```markdown
## Scan Comparison

**Previous**: scan-2026-03-15.json (52 findings)
**Current**: findings-merged.json (48 findings)

| Metric          | Previous (Mar 15) | Current (Mar 21) | Delta           |
|-----------------|--------------------|--------------------|-----------------|
| Total findings  | 52                 | 48                 | -4 (improved)   |
| High severity   | 19                 | 15                 | -4 (improved)   |
| Automatable     | 27                 | 23                 | -4              |

### Resolved (4 findings fixed)
- L1-003: Currency type mismatch — no longer detected
- L3-007: Missing @moduledoc in billing context — fixed

### New (2 findings appeared)
- L6-012: New circular dependency in notifications context
- L3-015: HTTPoison added in new integration module

### Severity Changes
- L3-002: Naming inconsistency — high -> medium (improved)

### Trend: {Improving|Stable|Regressing} (net {delta} findings)
```

### Step 6: Trend Assessment

Summarize with one of:

- **Improving** — net reduction in findings OR reduction in high-severity count
- **Stable** — net change within +/-2 findings and no severity increase
- **Regressing** — net increase in findings OR increase in high-severity count

If 3+ history scans exist, mention the multi-scan trend:
"Over 3 scans: 62 -> 52 -> 48 findings. Consistent improvement."

## References

- Finding schema: `../scan/references/finding-schema.md`
- History saving: `../scan/references/history-saving.md`
