---
name: ei:brief
description: >
  Interactive walkthrough of Inspector scan findings — explains each finding with evidence,
  impact, and suggested fix. Use after /ei:scan when the user wants to understand results, says
  explain findings, walk me through, what did you find, or has 15+ findings and needs guided
  review before /ei:apply.
argument-hint: "[report-path]"
---

# Inspector Brief — Findings Walkthrough

Interactive section-by-section explanation of `/ei:scan` results.

## Usage

```
/ei:brief                              # Uses .claude/inspector/report.md
/ei:brief .claude/inspector/report.md  # Explicit path
```

## Prerequisites

Must have run `/ei:scan` first. Report file must exist.

## Workflow

### Step 1: Load Report

Read `.claude/inspector/report.md` (or path from `$ARGUMENTS`).
If not found: "No report found. Run `/ei:scan` first."

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

"Reviewed {N}/{total} findings. Ready to generate artifacts? Run `/ei:apply` or `/ei:apply --pick` to choose specific ones."

## Iron Laws

1. **Never modify the report** — brief is read-only
2. **Let user control pace** — don't dump everything at once
3. **Show evidence** — every finding needs concrete examples, not abstract claims
4. **Suggest next action** — end with clear `/ei:apply` recommendation
