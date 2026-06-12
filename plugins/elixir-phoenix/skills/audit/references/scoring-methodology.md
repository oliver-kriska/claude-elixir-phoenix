# Scoring Methodology

How health scores are calculated for each category.

## Score Ranges

| Score | Grade | Status | Meaning |
|-------|-------|--------|---------|
| 90-100 | A | Excellent | No critical issues, minor improvements only |
| 80-89 | B | Good | Few warnings, solid foundation |
| 70-79 | C | Needs Attention | Some issues to address |
| 60-69 | D | Needs Work | Multiple issues, prioritize fixing |
| <60 | F | Critical | Significant problems, immediate action |

## Category Scoring

### Architecture (100 points)

| Criterion | Points | Deductions |
|-----------|--------|------------|
| Context boundaries respected | 25 | -5 per violation |
| Module naming consistency | 15 | -3 per inconsistency |
| Fan-out <5 contexts per module | 15 | -5 per over-coupled module |
| API surface reasonable (<30 funcs/context) | 15 | -5 per bloated context |
| No compile-time circular dependencies | 15 | -10 per cycle |
| Folder structure follows conventions | 15 | -5 per deviation |

**Commands used:**

```bash
mix xref graph --format stats
mix xref graph --format cycles --label compile
find lib -name "*.ex" -type f | wc -l
```

### Performance (100 points)

| Criterion | Points | Deductions |
|-----------|--------|------------|
| No N+1 patterns detected | 30 | -5 per N+1 |
| Indexes for common queries | 20 | -5 per missing index |
| Preloads used appropriately | 15 | -3 per missing preload |
| No GenServer bottlenecks | 15 | -10 per bottleneck |
| LiveView streams for large lists | 10 | -5 per regular assign list |
| Queries avoid SELECT * | 10 | -2 per SELECT * |

**Commands used:**

```bash
grep -B5 -A5 "Enum.map" lib/ -r --include="*.ex" | grep "Repo\."
grep -r "Repo.preload" lib/ --include="*.ex"
grep -r "assign(socket" lib/my_app_web/live/ --include="*.ex"
```

### Security (100 points)

| Criterion | Points | Deductions |
|-----------|--------|------------|
| No sobelow critical issues | 30 | -15 per critical |
| No sobelow high issues | 20 | -5 per high |
| Authorization in all handle_events | 15 | -10 per missing auth |
| No String.to_atom with input | 10 | -10 per violation |
| No raw() with untrusted content | 10 | -10 per violation |
| Secrets in runtime.exs only | 15 | -15 per hardcoded secret |

**Commands used:**

```bash
mix sobelow --exit medium 2>&1 || true
grep -r "String.to_atom" lib/ --include="*.ex"
grep -r "raw(" lib/ --include="*.ex"
grep -r "handle_event" lib/my_app_web/live/ -A10 | grep -v "authorize\|permit"
```

### Test Quality (100 points)

| Criterion | Points | Deductions |
|-----------|--------|------------|
| Coverage >70% | 30 | -5 per 10% below 70% |
| No flaky test patterns | 20 | -5 per Process.sleep in test |
| Async: true where possible | 15 | -2 per missing async |
| verify_on_exit! in Mox tests | 15 | -5 per missing |
| Reasonable test duration (<30s avg) | 10 | -5 if slow |
| Error paths tested | 10 | -5 if only happy path |

**Commands used:**

```bash
mix test --cover 2>&1 | tail -30
grep -r "Process.sleep" test/ --include="*.exs"
grep -r "async: true" test/ --include="*.exs"
grep -r "verify_on_exit!" test/ --include="*.exs"
```

### Dependencies (100 points)

| Criterion | Points | Deductions |
|-----------|--------|------------|
| No hex.audit vulnerabilities | 40 | -20 per vulnerability |
| No deps.audit issues | 20 | -10 per issue |
| No major version behind (>2) | 20 | -5 per outdated |
| No unused dependencies | 10 | -3 per unused |
| Version pinning appropriate | 10 | -5 if all loose |

**Commands used:**

```bash
mix hex.audit 2>&1
mix deps.audit 2>&1
mix hex.outdated 2>&1
```

## Overall Score Calculation

```
overall_score = (
  architecture_score * 0.20 +
  performance_score * 0.25 +
  security_score * 0.25 +
  test_quality_score * 0.15 +
  dependencies_score * 0.15
)
```

**Weighting rationale:**

- Security and Performance weighted highest (25% each) - runtime impact
- Architecture weighted at 20% - long-term maintainability
- Tests and Dependencies at 15% each - important but less immediate

## Grade Assignment

```
if overall_score >= 90: grade = "A"
elif overall_score >= 80: grade = "B"
elif overall_score >= 70: grade = "C"
elif overall_score >= 60: grade = "D"
else: grade = "F"
```

## Critical Issues Override

Regardless of score, flag as CRITICAL if any:

- Security vulnerability detected
- Hardcoded secrets found
- Compile warnings present
- Test suite failing
