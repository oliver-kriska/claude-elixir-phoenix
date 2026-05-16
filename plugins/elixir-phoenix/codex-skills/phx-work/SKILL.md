---
name: phx-work
description: "Execute an Elixir/Phoenix implementation plan in Codex. Use when the user asks for phx work, /phx:work, or to implement a Phoenix plan."
argument-hint: "<plan path OR task description>"
---

# Work An Elixir/Phoenix Plan In Codex

This is the Codex-native adapter for the upstream Claude skill at
`../../skills/work/SKILL.md`. Use the upstream workflow for Phoenix judgment,
but use Codex tools and the local repo instructions for execution.

## Codex Execution Rules

- Read the plan first. If no plan exists and the task is non-trivial, suggest
  `phx plan` before implementation unless the user clearly wants direct work.
- Use `update_plan` for visible task tracking.
- Use `rg` and focused reads before editing.
- Use `apply_patch` for manual edits.
- Do not revert user changes.
- Keep changes surgical and Phoenix-idiomatic.
- Run verification before claiming completion:
  - `mix compile`
  - `mix format --check-formatted` or the repo's established formatter check
  - focused `mix test`

## Phoenix Execution Posture

- Prefer contexts for data access and business logic.
- Keep LiveView state explicit and assign names clear.
- Use changesets and database constraints for persistence guarantees.
- Add tests next to the behavior changed.
- If JavaScript is needed, explain why LiveView alone is insufficient.

## Completion

Finish with changed files, verification results, and a risk level with one
line describing possible blast radius.

