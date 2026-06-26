# Claude Code Skill Template

Use this template when generating project-specific skills.

## Standard Skill Structure

```markdown
---
name: domain-naming-conventions
description: Enforce naming conventions for this project. Load when creating new modules, functions, or contexts.
---

# Domain Naming Conventions

## Iron Laws

1. **Finance modules MUST be in Finance context** — `lib/app/finance/`
2. **Bot modules MUST contain "Bot" in name** — `ChatBot`, `NotificationBot`
3. **Worker modules MUST end with "Worker"** — `EmailWorker`, `SyncWorker`

## Naming Patterns

| Domain | Module Pattern | Function Pattern |
|--------|---------------|-----------------|
| Finance | `Finance.*` | `calculate_`, `process_` |
| Users | `Accounts.*` | `get_user`, `list_users` |

## When Creating New Modules

1. Check which context the module belongs to
2. Follow the naming pattern for that context
3. Add @moduledoc with domain context
4. Create corresponding test file
```

## Key Rules for Generated Skills

1. **SKILL.md under 100 lines** — be concise
2. **Include Iron Laws section** — non-negotiable rules first
3. **Include concrete examples** — not abstract guidance
4. **Use tables for patterns** — easy to scan
5. **Description must trigger auto-loading** — describe when to load
6. **No triggers: field** — use description for auto-loading
