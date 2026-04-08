# Plan Review Output Template

Use this format when presenting synthesized review findings.

## Example

```markdown
## Plan Review Results

**Document:** .claude/plans/user-auth/plan.md
**Type:** plan
**Reviewers:** coherence, feasibility, elixir-architecture, security
- security -- plan adds auth flow with session tokens
- elixir-architecture -- plan touches Ecto schemas and LiveView

Applied 3 auto-fixes. 4 findings to consider (2 errors, 2 omissions).

### Auto-fixes Applied

- Fixed unit count from "4 units" to "5 units" to match listed units (coherence)
- Added `mix compile --warnings-as-errors` to verification steps (feasibility)
- Added preload requirement to Unit 3 query approach -- Iron Law 6 (elixir-architecture)

### P0 -- Must Fix

#### Errors

| # | Section | Issue | Reviewer | Confidence |
|---|---------|-------|----------|------------|
| 1 | Unit 2 | Plan uses `String.to_atom(params["role"])` -- Iron Law 10 violation | elixir-architecture | 0.95 |

### P1 -- Should Fix

#### Errors

| # | Section | Issue | Reviewer | Confidence |
|---|---------|-------|----------|------------|
| 2 | Scope | 6 of 8 units build admin UI; only 1 touches stated goal | scope-guardian | 0.82 |

#### Omissions

| # | Section | Issue | Reviewer | Confidence |
|---|---------|-------|----------|------------|
| 3 | Unit 4 | LiveView mount loads all records -- no streams for large lists (Iron Law 2) | elixir-architecture | 0.88 |

### P2 -- Consider Fixing

#### Omissions

| # | Section | Issue | Reviewer | Confidence |
|---|---------|-------|----------|------------|
| 4 | Unit 3 | No mention of Oban job idempotency strategy (Iron Law 7) | elixir-architecture | 0.72 |

### Coverage

| Persona | Status | Findings | Auto | Present |
|---------|--------|----------|------|---------|
| coherence | completed | 2 | 1 | 1 |
| feasibility | completed | 2 | 1 | 1 |
| elixir-architecture | completed | 3 | 1 | 2 |
| security | completed | 2 | 0 | 2 |
```

## Section Rules

- **Summary line**: "Applied N auto-fixes. K findings to consider (X errors, Y omissions)."
- **Auto-fixes Applied**: List all auto-applied fixes with detail. Omit if none.
- **P0-P2 sections**: Only include sections with findings. Separate Errors/Omissions.
- **Coverage**: Always include. Findings = Auto + Present.
