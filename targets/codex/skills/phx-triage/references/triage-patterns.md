# Triage Patterns

## Common Triage Decisions

### Always Fix (auto-approve, don't even ask)

Iron Law violations and security issues:

- SQL injection or XSS via `raw/1` with untrusted content
- Missing authorization in `handle_event` (Iron Law 11)
- `String.to_atom` with user input (Iron Law 10)
- `:float` used for money fields (Iron Law 4)
- DB queries in disconnected mount (Iron Law 1)
- Non-idempotent Oban jobs (Iron Law 7)
- `mix compile --warnings-as-errors` failures

### Usually Fix

Common Elixir/Phoenix issues worth addressing:

- N+1 queries — missing `Repo.preload` (Iron Law 6)
- Missing `^` pin in Ecto queries (Iron Law 5)
- Large lists without streams in LiveView (Iron Law 2)
- PubSub subscribe without `connected?/1` (Iron Law 3)
- Oban args with atom keys (Iron Law 8)
- Tests without assertions or using `Process.sleep`
- Missing error handling on external API calls

### Often Skip

Low-impact or cosmetic issues:

- Credo style suggestions (unless `--strict` is required)
- `@moduledoc false` on internal/private modules
- Cosmetic naming improvements
- "Could use `with` chain" style suggestions
- Adding typespecs to private functions

### Context-Dependent

Ask the user for these — the right answer depends on project
stage and priorities:

- Performance optimizations (premature vs. needed)
- Test coverage for edge cases (shipping deadline?)
- Refactoring suggestions (tech debt budget?)
- Documentation improvements (internal vs. public API?)

## Severity Reclassification Guide

### Downgrade from BLOCKER when

- The issue is in code that's not yet reachable
- There's an existing workaround in production
- The fix requires a separate migration/PR
- The issue existed before this change (pre-existing)

### Upgrade from SUGGESTION when

- The pattern will be copied by future developers
- It affects a security-sensitive code path
- It causes confusion in code review
- It violates an Iron Law

## Triage Anti-Patterns

### "Fix everything" without thinking

If you approve every finding, you didn't need triage. Either
skip triage and go straight to `/phx:plan`, or be more
selective about what's worth fixing now.

### "Skip everything" to ship faster

If you skip more than 70% of findings, the review wasn't
useful or you're cutting too many corners. At minimum, fix
all BLOCKERs and most WARNINGs.

### Triaging without reading

Each finding deserves 10-30 seconds of thought. If you're
pattern-matching on severity alone, you're missing context.

## Batch Triage for Large Reviews

When a review has 15+ findings:

1. First pass: Auto-approve all BLOCKERs
2. Second pass: Present WARNINGs for decision
3. Third pass: Batch SUGGESTIONs — "Skip all suggestions?"

This prevents decision fatigue on large reviews.
