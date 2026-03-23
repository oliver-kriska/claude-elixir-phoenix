# Finding Schema

Every finding produced by Inspector layer agents uses this YAML frontmatter format.

## Schema

```yaml
---
id: L1-001                       # Layer prefix (L1-L6) + sequential number
layer: git-history               # git-history | pr-reviews | code-docs | claude-config | sessions | architecture
category: translation            # translation | naming | testing | architecture | workflow | domain | security | documentation | ci-cd
title: "Short description"       # Human-readable, specific (not "code could be better")
severity: high                   # critical | high | medium | low
effort: small                    # tiny | small | medium | large
automatable: yes                 # yes | partial | no
artifact_types:                  # What can be generated from this finding
  - credo-check                  # credo-check | skill | ci-step | claude-md-rule | review-prompt | mix-task
evidence:                        # Specific proof — commit SHAs, PR numbers, file:line refs
  - "abc1234: fix missing gettext in user profile"
  - "PR #142: reviewer comment 'please add gettext'"
  - "lib/app_web/live/settings.ex:45 — hardcoded string"
frequency: 23                    # How many times this pattern was observed
confidence: high                 # high (3+ layers) | medium (2 layers) | low (1 layer)
confidence_reasoning: "Static analysis counted all 165 events, pattern match is precise"
---

Detailed description of the finding. Include:
- What the pattern is
- Why it matters (impact on team, CI costs, code quality)
- Specific examples from the codebase
- Suggested remediation approach
```

## Severity Guide

| Level | Criteria | Examples |
|-------|----------|---------|
| **critical** | Security risk, data loss, or blocks production | SQL injection, missing auth checks, Ecto reset in prod |
| **high** | Recurring team pain, measurable CI/review cost | Missing gettext (20+ commits), missing tests for contexts |
| **medium** | Code quality improvement, maintainability | Inconsistent naming, missing @moduledoc, unused code |
| **low** | Nice-to-have, style preference | Commit message format, optional tooling |

## Confidence Reasoning

| Field | Description |
|-------|-------------|
| `confidence` | high (3+ layers) / medium (2 layers) / low (1 layer) |
| `confidence_reasoning` | One sentence explaining why confidence is high/medium/low. Examples: "Static grep count, no false positives", "Keyword matching may include non-user strings", "Based on 3+ layer corroboration" |

## Effort Guide

| Level | Time | Examples |
|-------|------|---------|
| **tiny** | <30 min | Add one Credo check, fix one CI step |
| **small** | 1-2 hours | Write Credo check + config, create skill |
| **medium** | Half day | Refactor naming across 10+ modules |
| **large** | 1+ days | Restructure contexts, rewrite architecture |

## Artifact Types

| Type | Generated Output | Where |
|------|-----------------|-------|
| `credo-check` | `.ex` file with Credo.Check implementation | `generated/credo-checks/` |
| `skill` | `.md` SKILL.md file for Claude Code | `generated/skills/` |
| `ci-step` | Shell script or YAML config | `generated/ci-scripts/` |
| `claude-md-rule` | Markdown rules block | `generated/claude-md-rules.md` |
| `review-prompt` | Checklist / system prompt / GH Actions | `generated/review-prompts/` |
| `mix-task` | `.ex` file with Mix.Task implementation | `generated/mix-tasks/` |

## Layer Prefixes

| Prefix | Layer |
|--------|-------|
| L1 | Git History |
| L2 | PR Reviews |
| L3 | Code & Documentation |
| L4 | Claude Config |
| L5 | Claude Sessions |
| L6 | Architecture |
