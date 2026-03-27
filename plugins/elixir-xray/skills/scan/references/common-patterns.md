# Common Patterns in Elixir/Phoenix Projects

Reference data for contextualizing X-Ray findings. Based on analysis of
3 production codebases across different domains and sizes.

## Security Patterns

| Pattern | Prevalence | Example | Impact |
|---------|-----------|---------|--------|
| Unguarded handle_event | 3/3 (100%) | 27-281 unguarded events per project | Auth bypass via WebSocket replay |
| No pre-commit security hooks | 3/3 (100%) | Zero PostToolUse hooks in all three | Rules exist as docs, not enforcement |

## Code Quality Patterns

| Pattern | Prevalence | Example | Impact |
|---------|-----------|---------|--------|
| Empty PO translations | 2/3 (67%) | 2,000-4,000 empty msgstr entries | Missing text for non-English users |
| Inconsistent function naming | 3/3 (100%) | Mixed get_/fetch_/find_ prefixes | Review friction, onboarding cost |
| Missing @moduledoc | 2/3 (67%) | Coverage 37-59% across modules | Hard to understand module purpose |
| Test coverage < 50% | 2/3 (67%) | 35-50% coverage across projects | Insufficient safety net for refactors |
| Custom Credo checks untested | 1/3 (33%) | 19 checks, 0 tests | Broken check = silently lost enforcement |

## Architecture Patterns

| Pattern | Prevalence | Example | Impact |
|---------|-----------|---------|--------|
| God context (>50 modules) | 2/3 (67%) | 72 modules, 9923-line facade | Full recompile on any change |
| Circular dependencies | 3/3 (100%) | 37 to 908 nodes in cycles | Compilation coupling, hard to split |
| Repo calls from web layer | 2/3 (67%) | 30+ direct Repo calls in LiveViews | Bypasses context boundaries |
| Generic context names | 2/3 (67%) | Utils/Helpers spanning 64 modules | Catch-all that grows unbounded |
| Flat Oban workers | 1/3 (33%) | 85 workers in one directory | No domain organization |

## Process Patterns

| Pattern | Prevalence | Example | Impact |
|---------|-----------|---------|--------|
| No pre-commit hooks | 3/3 (100%) | Zero hooks in .claude/ | CI failures preventable locally |
| Low PR review coverage | 2/3 (67%) | 0-7% of PRs reviewed | Quality issues reach main unchecked |
| No commit convention enforcement | 3/3 (100%) | Tickets referenced but format varies | Inconsistent history, broken changelogs |
| Missing CI gettext check | 2/3 (67%) | No translation freshness gate | Translations silently drift from source |

## Recurring Bug Patterns (from git history)

| Pattern | Prevalence | Example | Prevention |
|---------|-----------|---------|------------|
| Currency type oscillation | 1/3 (33%) | 7 fix commits, worsening over time | Credo check + canonical money type |
| Nil crashes in handlers | 2/3 (67%) | 8+ fixes across billing/contacts | Credo check for bare Repo.get! |
| Flaky E2E tests | 1/3 (33%) | 14 fix commits for Playwright | Async-aware test patterns |
| Soft-delete filter gaps | 1/3 (33%) | 17 fixes over 18 months | Default scope + Credo check |
| Missing preloads | 1/3 (33%) | 7+ fix commits for assoc errors | Credo check for Repo.get without preload |

## Interpreting Findings

### Prevalence Tiers

- **100% (3/3)**: Universal — every Phoenix project has this. Flag it, but normalize it.
- **67% (2/3)**: Common — most projects hit this as they grow past ~50 modules.
- **33% (1/3)**: Situational — depends on domain (e.g., currency only matters with money).

### How Agents Should Use This Data

1. **Normalize**: "Unguarded handle_event is universal (100% of projects) — yours is typical"
2. **Prioritize**: 100% patterns are systemic; 33% patterns may not apply to every project
3. **Contextualize severity**: a finding at 100% prevalence with a proven fix is high-value
4. **Skip irrelevant**: don't flag currency patterns in projects without money fields

### "How You Compare" Report Section

Generate this in the final report to ground findings in community data:

```
## How You Compare

Your project has {N}/10 of the most common Phoenix patterns:
[x] Unguarded handle_event (100% of projects)
[x] Inconsistent naming (100% of projects)
[x] Circular dependencies (100% of projects)
[x] No pre-commit hooks (100% of projects)
[x] No commit convention (100% of projects)
[x] Empty translations (67% of projects)
[x] God context (67% of projects)
[ ] Float for money (33% of projects) — clean
[ ] Flat Oban workers (33% of projects) — clean
[ ] Flaky E2E tests (33% of projects) — clean

7/10 patterns found. Average across analyzed projects: 6/10.
```

Adjust the checklist items based on actual scan findings. Include the
"clean" annotation for patterns NOT found — positive reinforcement matters.

### Mapping Patterns to Artifacts

| Pattern | Artifact Type | Auto-generatable? |
|---------|--------------|-------------------|
| Unguarded handle_event | Credo check | Yes |
| Inconsistent naming | Credo check + skill | Yes |
| Empty translations | CI script | Yes |
| Circular dependencies | Review prompt | Partially (needs judgment) |
| Repo calls from web | Credo check | Yes |
| Currency oscillation | Credo check + iron law | Yes |
| Nil crashes | Credo check | Yes |
| Missing preloads | Credo check | Yes |
| No pre-commit hooks | CI script + hook config | Yes |
| Soft-delete gaps | Credo check + query audit | Partially |
