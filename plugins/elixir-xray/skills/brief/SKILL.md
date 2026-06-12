---
name: xray:brief
description: >
  Walk through X-Ray scan findings interactively — explains each Ecto,
  LiveView, or Credo finding with evidence, impact, and suggested fix. Use
  after /xray:scan to understand results or get a guided review before
  /xray:apply.
effort: low
argument-hint: "[report-path]"
---

# X-Ray Brief — Findings Walkthrough

Interactive section-by-section explanation of `/xray:scan` results.

## Usage

```
/xray:brief                              # Uses .claude/xray/report.md
/xray:brief .claude/xray/report.md  # Explicit path
```

## Prerequisites

Must have run `/xray:scan` first. Report file must exist.

## Workflow

### Step 1: Load Report

Read `.claude/xray/report.md` (or path from `$ARGUMENTS`).
If not found: "No report found. Run `/xray:scan` first."

### Step 2: Present Overview

Show the dashboard table from the report. Then:

"I found **{N} findings** across **{layers} layers**. {critical} are critical, {automatable} can be automated. Want me to walk through them by category?"

### Step 3: Walk Through by Category

For each category with findings (sorted by priority):

```
## Category: {name} ({count} findings)

### Finding 1: {title} [{severity}]
**Why it matters**: {impact explanation}
**Evidence**: {2-3 examples from the evidence array}
**Suggested fix**: {artifact type} — {what it would do}
**Effort**: {effort estimate}

[Continue to next finding? / Skip to next category? / Stop?]
```

Use AskUserQuestion to let user control pace:

- "Next finding" (default)
- "Skip to next category"
- "Jump to applying fixes"
- "Stop"

### Step 4: Wrap Up

After all categories (or user stops):

"Reviewed {N}/{total} findings. Ready to generate artifacts? Run `/xray:apply` or `/xray:apply --pick` to choose specific ones."

## Iron Laws

1. **NEVER modify the report** — brief is read-only, DO NOT write or edit any scan files
2. **Let user control pace** — MUST NOT dump all findings at once; use AskUserQuestion
3. **Show evidence** — every finding needs concrete examples, not abstract claims
4. **Suggest next action** — end with clear `/xray:apply` recommendation

## References

- `${CLAUDE_SKILL_DIR}/../scan/references/finding-schema.md` — Finding YAML frontmatter format
- `${CLAUDE_SKILL_DIR}/../scan/references/report-template.md` — Report structure reference
