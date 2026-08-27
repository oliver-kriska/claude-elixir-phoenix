# Resolution Template

Use this template when creating solution documentation in `.claude/solutions/`.

## Filename Convention

```
{sanitized-symptom}-{module}-{YYYYMMDD}.md
```

- Lowercase, hyphen-separated
- Special characters removed
- Truncated under 80 characters
- Example: `association-not-loaded-accounts-20251201.md`

## Full Template

````markdown
---
module: "{Module or context name}"
date: "{YYYY-MM-DD}"
problem_type: {enum from schema}
component: {enum from schema}
symptoms:
  - "{Observable symptom 1}"
  - "{Observable symptom 2}"
root_cause: {enum from schema}
severity: {critical|high|medium|low}
tags: [{tag1}, {tag2}, {tag3}]
---

# {Descriptive Title}

## Symptoms

What was observed. Include:
- Error messages (exact text)
- Unexpected behavior description
- Where it manifested (which LiveView, which context, which test)

## Investigation

What was tried and what happened:

1. **Hypothesis 1**: {what you thought} — {result}
2. **Hypothesis 2**: {what you thought} — {result}
3. **Root cause found**: {the actual cause}

## Root Cause

Detailed explanation of WHY this happened. Connect to the
underlying Elixir/Phoenix concept.

```elixir
# The problematic code
problematic_code()
```

## Solution

The fix that resolved it.

```elixir
# The working code
fixed_code()
```

### Files Changed

- `lib/my_app/accounts.ex:42` — Added preload
- `test/my_app/accounts_test.exs:15` — Added test for preload

## Prevention

How to prevent this from recurring:

- [ ] Add to Iron Laws? (if foundational pattern)
- [ ] Add to agent checks? (if detectable by reviewer)
- [ ] Add to test patterns? (if testable)
- Specific guidance: "{actionable advice}"

## Related

- `.claude/solutions/{related-file}.md` — Similar issue in different context
- Iron Law #{n}: {description} (if applicable)
````

## Category Directories

Create the file in the appropriate subdirectory:

| problem_type | Directory |
|-------------|-----------|
| `build_error` | `build-issues/` |
| `test_failure` | `testing-issues/` |
| `runtime_error` | `phoenix-issues/` |
| `performance_issue` | `performance-issues/` |
| `database_issue` | `ecto-issues/` |
| `security_issue` | `security-issues/` |
| `liveview_bug` | `liveview-issues/` |
| `oban_issue` | `oban-issues/` |
| `otp_issue` | `otp-issues/` |
| `integration_issue` | `phoenix-issues/` |
| `logic_error` | `phoenix-issues/` |
| `deployment_issue` | `deployment-issues/` |
| `iron_law_violation` | mapped by Iron Law domain |

## Quality Checklist

Before saving, verify:

- [ ] YAML frontmatter validates against schema
- [ ] All enum values are exact matches
- [ ] Symptoms are specific (include error text)
- [ ] Root cause explains WHY, not just WHAT
- [ ] Solution includes code examples
- [ ] Prevention has actionable next steps
- [ ] File is in correct category directory
