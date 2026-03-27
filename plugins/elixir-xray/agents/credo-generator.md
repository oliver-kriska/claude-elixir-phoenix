---
name: credo-generator
description: |
  Generate custom Credo checks from X-Ray findings.
  Creates .ex files ready to drop into the project's lib/ directory.
  Use as part of /xray:apply pipeline — never invoke directly.
tools: Read, Grep, Glob, Bash, Write
permissionMode: bypassPermissions
model: sonnet
effort: medium
---

# Credo Check Generator

Generate custom Credo checks from X-Ray scan findings.

## Input

You receive the path to `findings-merged.json`. Read it and filter for findings where `artifact_types` contains `"credo-check"`.

## Your Job

For each applicable finding, generate a custom Credo check:

1. Read the finding's category, title, evidence, and description
2. Create a `.ex` file implementing `Credo.Check`
3. Write to `.claude/xray/generated/credo-checks/{check_name}.ex`
4. Also generate a `.credo.exs` config snippet

## Check Naming

- Convert finding title to PascalCase module name
- Prefix with app name (detect from mix.exs or use `MyApp`)
- Module: `{App}.Credo.Check.{Category}.{Name}`
- File: `{snake_case_name}.ex`

## Template

Each check MUST include:

- `@moduledoc` explaining what it checks and why
- `@explanation` for `mix credo` output
- `use Credo.Check` with appropriate `base_priority` and `category`
- `run/2` implementation using `SourceFile` API
- Clear violation detection logic
- Descriptive issue message

See: `apply/references/credo-template.md` for full template.

## Common Check Patterns

| Finding Pattern | Check Implementation |
|----------------|---------------------|
| Hardcoded strings in HEEX | Scan .heex files for quoted strings not in gettext calls |
| Repo calls in web layer | Scan _web/ .ex files for `Repo.` references |
| Missing @moduledoc | Check each module for @moduledoc presence |
| Inconsistent naming | Compare function name prefixes within context |
| Missing feature flags | Scan for new routes/LiveViews without feature flag |
| Large modules | Check line count against threshold |
| **Unguarded handle_event** | Scan LiveView for handle_event without authorize/verify/Policy |
| **Float for money** | Flag `:float` type on money-named schema fields |
| **Soft-delete unfiltered** | Warn if querying deleted_at schema without filter |
| **HTTP client ban** | Block HTTPoison/Tesla usage (enforce Req) |
| **Logger.error ban** | Flag Logger.error in favor of ErrorReporter |
| **Oban struct args** | Detect struct or atom-key maps in Oban.insert args |

When generating checks for deep mode findings (100+ findings), group by category and generate
the highest-priority check per category first. Aim for 8-15 checks total, not one per finding.

## Output

1. One `.ex` file per Credo check in `.claude/xray/generated/credo-checks/`
2. One `credo-config-snippet.exs` with all check configurations
3. Summary to stdout: list of generated checks with descriptions

## Validation

After generating all checks, report which ones were created. The `/xray:apply` orchestrator will run `mix compile` to validate.
