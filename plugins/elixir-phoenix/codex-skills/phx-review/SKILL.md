---
name: phx-review
description: "Review Elixir/Phoenix code changes in Codex. Use when the user asks for phx review, /phx:review, Phoenix review, LiveView review, Ecto review, or review of current changes in an Elixir app."
argument-hint: "[optional: diff, PR, branch, or review focus]"
---

# Review Elixir/Phoenix Changes In Codex

This is the Codex-native adapter for the upstream Claude skill at
`../../skills/review/SKILL.md`. Review with a bug-finding posture and lead with
findings.

## Review Scope

1. Inspect `git status` and the relevant diff.
2. Identify whether changes touch Ecto schemas/migrations, contexts,
   LiveViews, controllers, Oban jobs, auth/permissions, external APIs, or tests.
3. Review for correctness, data integrity, authorization, Phoenix conventions,
   LiveView lifecycle bugs, missing tests, and compile/runtime risks.

## Codex Tool Mapping

- Use shell reads and `rg` for inspection.
- Use `git diff`, `git show`, and targeted file reads.
- Do not edit unless the user asks you to resolve findings.
- Do not spawn subagents unless the user explicitly asks for parallel review.

## Output Format

Findings first, ordered by severity. Each finding must include a file and line
reference when available, the concrete failure mode, and why it matters.

Then include:

- Open questions or assumptions
- Test gaps or verification not run
- Brief summary only after findings

If no findings are found, say so clearly and mention residual risk.

