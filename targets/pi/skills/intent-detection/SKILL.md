---
name: intent-detection
description: Route ambiguous Phoenix/LiveView/Ecto work requests to the correct /skill:phx-*
  workflow. Use when intent is unclear, mixed (bug fix vs. refactor), or scope is
  ambiguous.
---

# Intent Detection — Workflow Routing

When user describes work WITHOUT specifying a `/skill:phx-*` command, analyze their intent and suggest the appropriate workflow BEFORE starting work.

**Hard guard — check FIRST**: if the message starts with any slash command
(`/skill:phx-*`, `/skill:ecto-*`, `/skill:lv-*`, or any other `/command`), this skill does not apply.
Follow the invoked command directly — no routing analysis, no suggestion, zero
output from this skill.

## Routing Table

| Signal | Detected Intent | Suggest |
|--------|----------------|---------|
| "bug", "error", "crash", "failing", "broken", stack trace | Bug investigation | `/skill:phx-investigate` |
| "brainstorm", "explore idea", "not sure what I need", "vague idea", "let's discuss", "how to approach" | Ideation/requirements | `/skill:phx-brainstorm` |
| "add", "implement", "build", "create" + multi-step | New feature | `/skill:phx-plan` |
| "review", "check", "audit" code | Code review | `/skill:phx-review` |
| "fix" + small/specific scope | Quick fix | handle directly or `/skill:phx-quick` |
| "refactor", "clean up", "improve" | Refactoring | `/skill:phx-plan` (needs scope) |
| "research", "how to", "what's the best" | Research | `/skill:phx-research` |
| "evaluate", "compare", "adopt", "library", "should we use" | Library evaluation | `/skill:phx-research --library` |
| "test", "spec", "coverage" | Testing | handle directly or `/skill:phx-plan` |
| Describes 1-2 file changes, < 50 lines | Small task | handle directly |
| "deploy", "release", "production" | Deployment | `/skill:phx-verify` then deploy |
| "performance", "slow", "N+1", "memory" | Performance | `/skill:phx-perf` |
| "PR review", "review comments", "address feedback", "respond to PR" | PR response | `/skill:phx-pr-review` |
| "that worked", "fixed it", "problem solved" | Knowledge capture | `/skill:phx-compound` |
| "enhance plan", "more detail", "deepen" | Plan enhancement | `/skill:phx-plan --existing` |
| "triage", "which findings", "prioritize fixes" | Finding triage | `/skill:phx-triage` |

## Behavior

1. Read user's first message
2. Match against routing table (use keyword + context signals, not exact match)
3. If match found with multi-step workflow: "This looks like [intent]. I'd suggest `[command]` — want me to run it, or should I just dive in?"
4. If trivial task (typo, single-line fix, config change): skip suggestion, just do it
5. If user already specified a `/skill:phx-*` command: follow it, don't re-suggest
6. **NEVER block the user** — suggestion only, not mandatory

## Confidence Signals

High confidence (suggest immediately):

- Stack trace or error message pasted → `/skill:phx-investigate`
- "Add [feature] with [multiple components]" → `/skill:phx-plan`
- "Review my changes" or "check this PR" → `/skill:phx-review`

Medium confidence (suggest with caveat):

- "Fix [thing]" — could be quick or complex, suggest based on scope description
- "Update [thing]" — could be small edit or refactor

Low confidence (just do it):

- Single file mentioned, clear change
- "Change X to Y"
- Configuration or dependency updates

## Complexity Signals

When a task matches a workflow command, check complexity before suggesting:

**Trivial signals** (suggest `/skill:phx-quick` or handle directly):

- Single file mentioned explicitly
- "exclude X from Y", "add X to config", "rename", "change X to Y"
- Problem + solution both stated ("X is wrong, change to Y")
- One-line fix described

**Complex signals** (suggest `/skill:phx-plan` or `/skill:phx-investigate`):

- 3+ modules or files mentioned
- "intermittent", "race condition", "sometimes", "random"
- Stack trace with 5+ frames
- "across", "all", "every" (scope indicators)

**Override rule**: If user invokes `/skill:phx-full` but task matches trivial signals:
"This looks like a quick fix. Want `/skill:phx-quick` instead, or stick with the full cycle?"

## Iron Laws

1. **NEVER block on suggestion** — If user starts explaining, just do the work
2. **One suggestion max** — Don't re-suggest if user ignores first suggestion
3. **Commands are shortcuts, not gates** — All work can be done without commands

## Routing Logic Example

```
if has_slash_command($ARGUMENTS) -> follow command directly
elif has_stack_trace(message) -> suggest /skill:phx-investigate
elif matches("add|build|implement", message) and multi_step -> suggest /skill:phx-plan
elif matches("fix", message) and small_scope -> handle directly or /skill:phx-quick
elif matches("review|audit", message) -> suggest /skill:phx-review
else -> handle directly (no suggestion)
```

## Integration

This skill is consulted at session start. It works alongside:

- SessionStart hook (shows plugin loaded message)
- CLAUDE.md routing instructions (passive reference)
- Individual workflow skills (activated by commands)
