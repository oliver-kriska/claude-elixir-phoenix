# Agent Selection Guidelines

## When to Spawn Which Agents

| Feature Type | Agents to Spawn |
|--------------|-----------------|
| CRUD feature | patterns-analyst, ecto |
| Interactive UI | patterns-analyst, liveview |
| External integration | patterns-analyst, otp (+ hex-researcher ONLY if new lib) |
| Background processing | patterns-analyst, oban, otp |
| Data-heavy | patterns-analyst, ecto (+ hex-researcher ONLY if new lib) |
| Real-time | patterns-analyst, liveview |
| Auth/permissions | patterns-analyst, security-analyzer |
| Refactoring | patterns-analyst, call-tracer |
| Review fix (simple) | patterns-analyst only |
| Review fix (complex) | patterns-analyst + relevant specialists |
| Full new feature | ALL relevant agents |

## When to Spawn hex-library-researcher

**Spawn ONLY when:**

- Feature requires a NEW library not yet in mix.exs
- Evaluating ALTERNATIVE libraries to replace an existing dep

**Do NOT spawn when:**

- Library is already in mix.exs (use Read/Grep on `deps/` instead)
- Fixing review blockers (libraries already chosen)
- Refactoring existing code
- Understanding API of an existing dependency
- Simple bug fixes or improvements

**To understand an existing library's API:**

- Use `Read` on `deps/{library}/lib/` source code
- Use `Grep` to find function signatures and docs
- Use Tidewave's `mcp__tidewave__get_docs` if available
- Do NOT spawn hex-library-researcher for this

## When to Spawn web-researcher

**Model**: haiku (cheap fetch worker — extraction, not reasoning)

**Spawn when:**

- Feature involves unfamiliar library/pattern
- Need community input (ElixirForum discussions)
- Looking for real-world examples
- Checking for known issues/gotchas
- CI/CD or infrastructure questions

**Do NOT spawn when:**

- Standard CRUD feature
- Well-known patterns (auth, pagination)
- Codebase already has similar implementation

**Spawn rules:**

- Pass a focused 5-15 word query OR pre-searched URLs, NEVER raw text
- If multiple web topics: spawn multiple agents in parallel (1 per topic)
- Max 5 URLs per agent (diminishing returns beyond that)
- Agent returns 500-800 word summary — synthesis happens in orchestrator

## When to Spawn call-tracer

Spawn when planning involves:

- **Changing function signatures** — Need all callers and argument patterns
- **Moving/renaming functions** — Need all call paths
- **Refactoring contexts** — Need data flow understanding

## When to Ask Clarifying Questions

**Ask if:**

- Multiple valid approaches exist
- Scope is ambiguous
- Performance requirements unclear
- Integration points undefined

**Don't ask if:**

- Best practice is clear
- Codebase shows clear patterns
- Feature is well-specified

Max 3 questions. Make them count.
