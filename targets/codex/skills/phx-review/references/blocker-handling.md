# Blocker Handling

## Severity Classification

| Severity | Description | Action |
|----------|-------------|--------|
| **BLOCKER** | Must fix before merge | Explain issue clearly in review |
| **REQUIRES CHANGES** | Tests missing for new code | List untested code, suggest test plan |
| **WARNING** | Should fix | Note in review with recommendation |
| **SUGGESTION** | Nice to have | Brief note, no action needed |

## Review Scope

Review is **findings-only**. It does NOT:

- Create task lists (`- [ ]`)
- Add fix phases to plan files
- Modify any files outside `.claude/plans/{slug}/reviews/`
- Start fixing issues

Task creation and planning happen in `/phx:plan` after the user decides.

## Review Outcomes

**If PASS:**

```
Review complete. No blockers found.
Ready for: /phx:learn-from-fix (capture lessons)
```

**If PASS WITH WARNINGS:**

```
Review complete. {n} warnings noted.
Warnings logged but not blocking.
Ready for: /phx:learn-from-fix (capture lessons)
```

**If REQUIRES CHANGES:**

List untested code with brief descriptions, then ask:

```
Review found {n} untested public functions/callbacks:

1. {Function/callback} in {file} -- no test coverage
2. {Function/callback} in {file} -- no test coverage

How would you like to proceed?

- `/phx:plan` — Plan tests for these functions
- `/phx:work` — Write tests directly
- I'll handle it myself
```

**If BLOCKED:**

List actual blockers with brief descriptions, then ask:

```
Review found {actual count} blockers ({actual count} warnings):

1. {Actual blocker title} -- {one-line impact}
2. {Actual blocker title} -- {one-line impact}

How would you like to proceed?

- `/phx:plan .claude/plans/{slug}/reviews/{file}.md` — Replan fixes
  (best for complex or architectural issues)
- `/phx:work` — Fix directly
  (best for simple, isolated fixes)
- I'll handle it myself
```

Always enumerate actual findings -- never just show a count.

## Pre-existing Issues

Findings on code NOT changed in this diff are marked **PRE-EXISTING**.
Pre-existing issues appear in the report and summary table but do NOT
affect the verdict. A PASS verdict is possible even with pre-existing
blockers, as long as no NEW blockers exist.

## Research Requirement for Infrastructure

When reviewing CI/CD, deployment, or external service configuration:

- **ALWAYS research** how the specific service works before making claims
- Use web search to verify assumptions about CI runners, service containers,
  matrix behavior, caching, etc.
- Do NOT assume behavior based on general knowledge — CI platforms change
- Example: GitHub Actions matrix jobs each get their own service containers,
  not a shared one. This must be verified, not assumed.
