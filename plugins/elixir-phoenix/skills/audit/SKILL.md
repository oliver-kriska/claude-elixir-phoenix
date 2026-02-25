---
name: phx:audit
description: Holistic project health audit using 5 parallel specialist subagents. Analyzes architecture, performance, security, test quality, and dependencies. Produces actionable report with health score. Use quarterly or before major releases.
argument-hint: [--quick|--full|--focus=area|--since=commit]
---

# Project Health Audit

Comprehensive project-wide health assessment using 5 parallel specialist subagents.

## Usage

```
/phx:audit              # Full audit (default)
/phx:audit --quick      # 2-3 minute pulse check
/phx:audit --focus=security   # Deep dive single area
/phx:audit --focus=performance
/phx:audit --since abc123   # Incremental audit since commit
/phx:audit --since HEAD~10  # Audit last 10 commits
```

## When to Use

- **Quarterly** health checks
- **Before major releases**
- **After large refactors**
- **New team member onboarding** (understand codebase health)

## Subagent Architecture

Spawn 5 specialists in parallel using Task tool:

| Subagent | Focus | Output File |
|----------|-------|-------------|
| Architecture Reviewer | Structure quality, coupling, cohesion | `arch-review.md` |
| Performance Auditor | N+1, indexes, bottlenecks, scalability | `perf-audit.md` |
| Security Auditor | OWASP scan, auth patterns, secrets | `security-audit.md` |
| Test Health Auditor | Coverage, quality, flaky tests | `test-audit.md` |
| Dependency Auditor | Vulnerabilities, outdated, unused | `deps-audit.md` |

## Workflow

### Step 1: Spawn All 5 Auditors (Parallel)

```
Task(subagent_type: "general-purpose", prompt: "Architecture audit...", run_in_background: true)
Task(subagent_type: "general-purpose", prompt: "Performance audit...", run_in_background: true)
Task(subagent_type: "general-purpose", prompt: "Security audit...", run_in_background: true)
Task(subagent_type: "general-purpose", prompt: "Test health audit...", run_in_background: true)
Task(subagent_type: "general-purpose", prompt: "Dependency audit...", run_in_background: true)
```

**Agent prompts must be FOCUSED.** Scope each prompt to the
relevant directories and patterns. Do NOT give vague prompts
like "analyze the codebase."

### Step 2: Collect Results

Wait for ALL auditors to FULLY complete using TaskOutput. If
TaskOutput shows an auditor is still running, wait and check
again. NEVER proceed while any auditor is still running.

Read reports from `.claude/audit/reports/`.

### Step 3: Compress Findings

After all 5 auditors complete, spawn context-supervisor:

```
Task(subagent_type: "context-supervisor", prompt: """
Compress audit findings.
Input: .claude/audit/reports/
Output: .claude/audit/summaries/
Priority: Health scores per category, critical findings
only, cross-category correlations, deduplicate findings
found by 2+ agents.
""")
```

Read `.claude/audit/summaries/consolidated.md` for synthesis.

### Step 4: Calculate Health Score

Each category scores 0-100. See `references/scoring-methodology.md`.

### Step 5: Generate Report

Write to `.claude/audit/summaries/project-health-{date}.md`.

## Quick Mode (`--quick`)

Only run essential checks (~2-3 minutes):

```bash
mix compile --warnings-as-errors
mix hex.audit && mix deps.audit
mix xref graph --format stats
mix test --trace 2>&1 | tail -20
```

Skip: Full security scan, N+1 analysis, test quality metrics, architecture deep dive.

## Focus Mode (`--focus=area`)

Deep dive single area with full specialist resources:

| Focus | Subagent | Extra Checks |
|-------|----------|--------------|
| `security` | security-analyzer | Full OWASP, sobelow, manual patterns |
| `performance` | (performance subagent) | Profile-level analysis, query explain |
| `architecture` | (arch subagent) | Full xref, coupling matrix, cohesion |
| `tests` | testing-reviewer | Coverage by context, quality metrics |
| `deps` | (deps subagent) | License audit, maintenance status |

## Incremental Mode (`--since <commit>`)

Analyze only changes since a specific commit. Useful for pre-merge checks:

```bash
# Identify changed files
git diff --name-only <commit>...HEAD

# Run targeted audits on changed files only
# Skips full project scan, focuses on modified code
```

Combines with other flags: `/phx:audit --since HEAD~5 --focus=security`

## Output Format

Report at `.claude/audit/summaries/project-health-{date}.md` with:

- Executive Summary: Health Score (A-F, numeric/100), per-category scores table
- Critical Issues + Top Recommendations
- Detailed Findings (per-category from subagents)
- Action Plan: Immediate / Short-term / Long-term with checkboxes

## Garbage Collection Mode (`--gc`)

Lightweight 2-3 minute scan for entropy (quality drift):

```
/phx:audit --gc                  # Quick entropy check
/phx:audit --save-baseline       # Save current scores as baseline
/phx:audit --reset-baseline      # Delete baseline, start fresh
```

**`--gc` checks** (fast, non-blocking):

- Compile warnings count vs baseline
- Credo violation count vs baseline
- Test count and pass rate vs baseline
- Circular dependency check via `mix xref graph --format cycles`

**Output**: HEALTHY / DEGRADED / CRITICAL with delta from baseline.

**Baseline file**: `.claude/metrics/baseline.json` — auto-created
on first `--save-baseline`. Contains scores and metric counts.

See `/phx:entropy` for the full entropy detection system.

## Relationship to Other Commands

| Command | Scope | Frequency |
|---------|-------|-----------|
| `/phx:review` | Changed files (diff) | Every PR |
| `/phx:audit` | Entire project | Quarterly |
| `/phx:audit --gc` | Quick entropy check | After workflows |
| `/phx:entropy` | Full entropy analysis | On-demand |
| `/phx:boundaries` | Context structure | On-demand |
| `/phx:verify` | Compile/test pass | Anytime |

## References

- `references/scoring-methodology.md` - How scores are calculated
- `references/architecture-checks.md` - Detailed architecture criteria
