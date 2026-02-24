# Plan Annotation Guide

Complete reference for the `--annotate` mode of `/phx:plan`.

## What Are Annotations?

Annotations are HTML comments added to plan.md that signal
specific changes or questions. They enable lightweight iterative
plan refinement without spawning research agents.

## Syntax

```markdown
<!-- ANNOTATION: {PRIORITY} | {TYPE} | {note} -->
```

**Priority** (processing order):
- `CRITICAL` — Must address before work begins
- `HIGH` — Important change or concern
- `MEDIUM` — Nice-to-have improvement
- `LOW` — Minor suggestion

**Type**:
- `TASK` — Add, remove, or modify a task
- `SCOPE` — Change what's in/out of scope
- `DECISION` — Override or question a technical decision
- `RISK` — Flag a new risk or concern
- `SPIKE` — Request investigation before committing
- `PATTERN` — Suggest a different implementation pattern
- `GENERAL` — Anything else

## Examples

### Adding a Missing Task

```markdown
## Phase 2: Context Module [PENDING]

<!-- ANNOTATION: HIGH | TASK | Add rate limiting for password reset -->

- [ ] [P2-T1][direct] Implement register_user/1
```

### Questioning a Decision

```markdown
## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Cache | ETS | Fast reads |

<!-- ANNOTATION: CRITICAL | DECISION | Prefer Redis for cache — we already use it for sessions -->
```

### Flagging Scope Change

```markdown
## Scope

**In Scope:**
- User registration

<!-- ANNOTATION: MEDIUM | SCOPE | Should we also handle email verification in this plan? -->
```

### Requesting a Spike

```markdown
- [ ] [P3-T1][liveview] Real-time notification component

<!-- ANNOTATION: HIGH | SPIKE | Need to investigate if Phoenix.PubSub handles 1000+ subscribers -->
```

## Processing Rules

1. **Priority order**: CRITICAL → HIGH → MEDIUM → LOW
2. **Remove after addressing**: Each annotation is deleted once resolved
3. **Task IDs are IMMUTABLE**: `[Pn-Tm]` identifiers NEVER change
4. **New tasks get new IDs**: If annotation adds a task, use next available ID
5. **Track cycles**: `**Annotation Cycles**: n` in plan metadata
6. **Log to scratchpad**: Each cycle logged as `ANNOTATION CYCLE {n}` entry

## Workflow

```
User adds annotations → /phx:plan plan.md --annotate
  → Agent reads annotations
  → Processes in priority order
  → Addresses each (modify plan, add task, update decision)
  → Removes processed annotations
  → Increments Annotation Cycles counter
  → Presents changes for review
```

## vs. --existing Mode

| Aspect | --annotate | --existing |
|--------|-----------|-----------|
| Agents spawned | None | 2-4 specialists |
| Time | 1-3 minutes | 10-30 minutes |
| Depth | Surface-level refinement | Deep research |
| Use when | You know what to change | You need more information |
| Combines with | --existing (run after) | --annotate (run before) |

## Iron Laws for Annotations

1. **Task IDs `[Pn-Tm]` are NEVER deleted** — even if annotation
   says "remove this task", mark it as OUT OF SCOPE instead
2. **CRITICAL annotations block work** — must be resolved before
   `/phx:work` starts
3. **Annotations are ephemeral** — they exist only during the
   annotation cycle, never in the final plan
