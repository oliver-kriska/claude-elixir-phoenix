# Concern Track Selection

Select research by feature concerns, not named agents.

| Feature type | Required concern tracks |
|---|---|
| CRUD or data-heavy | Existing patterns, Ecto/data design |
| Interactive or real-time UI | Existing patterns, LiveView architecture |
| External integration | Existing patterns, OTP boundaries; library evaluation only for a new dependency |
| Background processing | Existing patterns, Oban behavior, OTP supervision |
| Authentication/permissions | Existing patterns, security and negative paths |
| Refactoring/signature changes | Existing patterns, call-site tracing |

Run selected tracks sequentially in the current session by default. Native
generic workers are optional only for independent tracks.

## Dependency Research

Evaluate libraries only when adding a dependency absent from `mix.exs` or
comparing replacements. For an existing dependency, inspect `deps/{library}`
and its installed/version-matched documentation. Optional Tidewave dependency
documentation tools may be used only when independently configured and exposed.

## External Research

Use primary documentation and focused web research for unfamiliar technology,
known issues, or infrastructure questions. Capture URLs, findings, alternatives,
and confidence in `.claude/plans/{slug}/research/`.

## Clarification

Ask at most three focused questions when scope, integration points, performance,
or competing valid approaches cannot be resolved from repository evidence.
