---
name: phx-plan
description: "Plan Elixir/Phoenix features in Codex. Use when the user asks for phx plan, /phx:plan, Phoenix planning, LiveView planning, Ecto schema planning, Oban job planning, or a multi-step Elixir/Phoenix implementation plan."
argument-hint: "<feature description OR path to review/plan file>"
---

# Plan Elixir/Phoenix Feature In Codex

This is the Codex-native adapter for the upstream Claude skill at
`../../skills/plan/SKILL.md`. Use the upstream skill as domain guidance, but
follow the Codex adaptations in this file whenever tool names or workflow
mechanics conflict.

## Codex Tool Mapping

- Claude `Read` -> shell reads with `sed`, `cat`, or `rg`
- Claude `Edit` / `MultiEdit` -> `apply_patch`
- Claude `Bash` -> `exec_command`
- Claude `TodoWrite`, `TaskCreate`, `TaskUpdate` -> `update_plan`
- Claude `AskUserQuestion` -> ask one direct plain-text question unless a
  blocking Codex question tool is explicitly available in the current mode
- Claude subagents -> use Codex subagents only when the user explicitly asks
  for delegation or parallel agent work
- Claude slash commands like `/phx:work` -> tell the user to ask Codex with
  `phx work <plan path>`

## Workflow

1. Identify the Phoenix app root. If the current directory is a monorepo
   parent, search for nearby `mix.exs` files and choose the app named by the
   user. If ambiguous, ask which app to target.
2. Gather context with `rg`, `mix phx.routes` when useful, and focused file
   reads. Prefer existing Phoenix contexts, LiveView modules, Ecto schemas,
   tests, and route structure over new abstractions.
3. Clarify only blocking ambiguity. State assumptions before planning when
   reasonable assumptions are enough.
4. Create a durable plan under `docs/plans/{slug}.md` in the target Phoenix
   app unless the repo already uses a different plan location.
5. Include:
   - Problem frame and scope
   - Existing patterns to follow with repo-relative paths
   - Implementation units with `[ecto]`, `[liveview]`, `[oban]`, `[web]`,
     `[test]`, or `[infra]` tags where useful
   - Test scenarios and exact test file paths
   - Verification commands, normally `mix compile`, `mix format --check-formatted`,
     and focused `mix test`
   - Risks and decisions
6. Stop after presenting the plan. Do not start implementation unless the user
   explicitly asks.

## Phoenix Rules

- Prefer LiveView capabilities over JavaScript unless JavaScript is clearly
  necessary.
- Keep Repo and SQL calls out of web modules; use contexts.
- Prefer HEEx `{}` expressions over `<%= %>` where appropriate.
- Do not add silent fallbacks. Prefer explicit failure or ask before
  introducing fallback behavior.
- Treat compile warnings as errors.

