---
name: phx:document
description: Generate documentation for implemented features - @moduledoc, @doc, README updates, ADRs. Use after implementing a feature or when the user asks for documentation, typespecs, or architecture decision records.
argument-hint: [plan-file OR feature-name]
---

# Document

Generate documentation for newly implemented features.

## Usage

```
/phx:document .claude/plans/magic-link-auth/plan.md
/phx:document magic link authentication
/phx:document  # Auto-detect from recent plan
```

## What Gets Documented

| Output | Description |
|--------|-------------|
| `@moduledoc` | For new modules missing documentation |
| `@doc` | For public functions without docs |
| README section | For user-facing features |
| ADR | For significant architectural decisions |

## Workflow

1. **Identify** new modules from recent commits or plan file
2. **Check** documentation coverage (`@moduledoc`, `@doc`)
3. **Generate** missing docs using templates
4. **Add** README section if user-facing feature
5. **Create** ADR if architectural decision was made
6. **Write** report to `.claude/plans/{slug}/reviews/{feature}-docs.md`

## When to Generate ADRs

| Trigger | Create ADR |
|---------|-----------|
| New external dependency | Yes |
| New database table | Maybe (if schema non-obvious) |
| New OTP process | Yes (explain why process needed) |
| New context | Maybe (if boundaries non-obvious) |
| New auth mechanism | Yes |
| Performance optimization | Yes |

## Integration with Workflow

```text
/phx:plan → /phx:work → /phx:review
       ↓
/phx:document  ← YOU ARE HERE (optional, suggested after review passes)
```

## References

- `references/doc-templates.md` — @moduledoc, @doc, README, ADR templates
- `references/output-format.md` — Documentation report format
- `references/doc-best-practices.md` — Elixir documentation best practices
- `references/documentation-patterns.md` — Detailed documentation patterns
