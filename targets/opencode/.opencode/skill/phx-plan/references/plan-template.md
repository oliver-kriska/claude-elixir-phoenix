# Plan Template Format

## Full Plan Template

```markdown
# Plan: {Feature Name}

**Status**: PENDING
**Created**: {date}
**Detail Level**: {minimal|more|comprehensive}
**Input**: {review path, or "from description"}

## Summary

{What we're building in 2-3 sentences}

## Scope

**In Scope:**

- Item 1
- Item 2

**Out of Scope:**

- Item 1

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Library | {name} | {why} |
| Storage | {type} | {why} |

## Data Model

{If database changes needed}

## Module Structure

{If new modules needed}

## System Map (LiveView features with 2+ pages/components only)

{Omit this entire section for non-LiveView or simple features.
Include when the liveview-architect produced a breadboard.}

### Places

| ID | Place | Entry Point | Notes |
|----|-------|-------------|-------|
| P1 | {LiveViewName} | {route} | {notes} |

### UI Affordances

| ID | Place | Component | Affordance | Type | Wires Out | Returns To |
|----|-------|-----------|------------|------|-----------|------------|
| U1 | P1 | {comp} | {element} | {phx-*} | {N-id} | {S-id} |

### Code Affordances

| ID | Place | Module | Affordance | Wires Out | Returns To |
|----|-------|--------|------------|-----------|------------|
| N1 | P1 | {Module} | {function} | {targets} | {S-id} |

### Data Stores

| ID | Store | Type | Read By | Written By |
|----|-------|------|---------|------------|
| S1 | {name} | {type} | {U/N ids} | {N ids} |

### Spikes

{List any ⚠️ unknowns from the tables above.}

## Phase 0: Spikes [PENDING] (only if ⚠️ unknowns exist)

- [ ] [P0-T1][direct] Spike: {investigate unknown}
  **Unknown**: {what we don't know}
  **Success criteria**: {what resolves it}
  **Time-box**: 30 minutes max

## Phase 1: {Phase Name} [PENDING]

- [ ] [P1-T1][ecto] Create user schema and migration
  **Implementation**: Generate with `mix phx.gen.context`.
  Add fields: email (string, unique), password_hash (string).
  Add unique index on email.

- [ ] [P1-T2][direct] Configure deps and environment
  **Locations**: mix.exs, config/runtime.exs
  **Pattern**: Add Argon2 to deps, configure hash rounds.

## Phase 2: {Phase Name} [PENDING]

- [ ] [P2-T1][liveview] Build registration LiveView
  **Implementation**: Create `RegisterLive` with form component.
  Handle `validate` and `save` events. Use `to_form/1` for
  changeset. Redirect to login on success.
  **Locations**: lib/app_web/live/register_live.ex,
  lib/app_web/live/register_live.html.heex

### Parallel: {Group Name}

- [ ] [P2-T2][direct] Task that can run in parallel
- [ ] [P2-T3][direct] Another parallel task

### Sequential

- [ ] [P2-T4][liveview] Task that depends on above

## Phase N: Verification [PENDING]

- [ ] [PN-T1][test] Unit tests for {context}
- [ ] [PN-T2][test] LiveView tests for {component}
- [ ] [PN-T3][test] Run full verification suite

## Task Agent Annotations

| Annotation | Agent | Use For |
|------------|-------|---------|
| `[ecto]` | ecto-schema-designer | Schemas, migrations, queries |
| `[liveview]` | liveview-architect | LiveView, real-time UI, PubSub |
| `[oban]` | oban-specialist | Background jobs, workers |
| `[otp]` | otp-advisor | GenServers, processes |
| `[security]` | security-analyzer | Auth, tokens, permissions |
| `[test]` | testing-reviewer | Tests, mocks, factories |
| `[direct]` | (none) | Simple tasks, config |

**Rules:** Primary focus wins. Security always wins for auth tasks.

## Files to Follow as Patterns

Existing files to read first when implementing (reduces cold-start):

- `{path/to/similar_module.ex}` — follow this pattern for {reason}
- `{path/to/existing_test.exs}` — follow this test structure
- `{path/to/component.ex}` — follow this component pattern

## Patterns to Follow

From codebase analysis:

- {Pattern 1}
- {Pattern 2}

## Session Handoff

Key context from planning session for `/phx:work` to use:

- **Discovery**: {key findings, bugs found, gotchas learned}
- **Decisions**: {choices made and why}
- **Warnings**: {things to watch out for during implementation}

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| {potential issue} | {how to handle} |

## Verification Checklist

- [ ] `mix compile --warnings-as-errors` passes
- [ ] `mix format --check-formatted` passes
- [ ] `mix credo --strict` passes
- [ ] `mix test` passes

```

## Task Granularity

Tasks are logical work units, NOT individual file edits.

**BAD** (too atomic -- one task per file):

```markdown
- [ ] [P3-T3][direct] Replace wait_for_timeout in file_a.exs
- [ ] [P3-T4][direct] Replace wait_for_timeout in file_b.exs
- [ ] [P3-T5][direct] Replace wait_for_timeout in file_c.exs
```

**GOOD** (grouped by pattern with locations and implementation):

```markdown
- [ ] [P3-T2][direct] Replace all hardcoded waits with
  condition-based waits
  **Locations** (71 calls across 14 files):
  - proposal_form_test.exs (15 calls)
  - space_inputs_test.exs (7 calls)
  - (12 more files)
  **Pattern**: Replace `wait_for_timeout(conn, 1000)` with:
  - DOM element: `Frame.wait_for_selector(id, selector: "css")`
  - Assertion: `assert_has(conn, "selector", text: "expected")`
  - PubSub: `assert_patiently(fn -> assert_has(...) end)`
```

**Guidelines:**

- 3-8 tasks per phase (not 15+)
- Group by PATTERN, list LOCATIONS within
- Include implementation detail: code examples, before/after
- Sub-locations are indented lists, not separate tasks
- Each task completable in one sitting

**IMPORTANT**: Plan template does NOT auto-start `/phx:work`. The
skill presents the plan and asks the user how to proceed.
