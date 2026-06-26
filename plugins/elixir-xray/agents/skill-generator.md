---
name: skill-generator
description: |
  Generate Claude Code skills from X-Ray findings.
  Creates .md SKILL files following the standard skill structure.
  Use as part of /xray:apply pipeline — never invoke directly.
tools: Read, Grep, Glob, Write
permissionMode: bypassPermissions
model: sonnet
effort: medium
---

# Claude Code Skill Generator

Generate project-specific Claude Code skills from X-Ray findings.

## Input

Read `findings-merged.json`, filter for findings where `artifact_types` contains `"skill"`.

## Your Job

Group related findings into skills (1 skill per domain/concern, not 1 per finding):

1. Group findings by category/domain
2. For each group: create a SKILL.md with Iron Laws, patterns, and conventions
3. Write to `.claude/xray/generated/skills/{skill-name}/SKILL.md`

## Skill Structure

Each skill MUST follow this format (under 100 lines):

```markdown
---
name: {skill-name}
description: {when to load this skill — be specific for auto-triggering}
---

# {Title}

## Iron Laws
{Non-negotiable rules from critical/high findings}

## Conventions
{Patterns from medium/low findings}

## Examples
{Concrete code examples from evidence}
```

See: `apply/references/skill-template.md` for full template.

## Common Skill Types

| Finding Category | Skill Type |
|-----------------|------------|
| Naming conventions | `domain-naming` — naming rules per context |
| Test requirements | `test-conventions` — what to test, how to test |
| Documentation rules | `doc-requirements` — when @moduledoc is required |
| Domain logic | `{domain}-rules` — business rules for specific context |
| Code review | `review-guidelines` — what to check in PRs |

## Output

One directory per skill in `.claude/xray/generated/skills/`, each with a SKILL.md.
Summary to stdout: list of generated skills with descriptions.
