# Research Integration Reference

Detailed methodology for the research phase of `/phx:brainstorm`.

## When Research Triggers

User selects "Research" at the Decision Point. This means they want deeper
analysis before committing to an approach. Common triggers:

- Multiple valid approaches exist and user wants comparison
- Niche topic where codebase scan found little existing code
- User wants to know "how do other projects do this?"
- Interview revealed technical unknowns (library choice, pattern selection)

## Diverge → Evaluate → Converge Pattern

Research follows a three-step pattern from creativity research (Guilford's
framework, adapted via LLM Discussion paper 2405.06373):

### Step 1: Diverge (Generate Diverse Approaches)

Spawn 2 agents in ONE Tool Use block with `run_in_background: true`.
Each agent explores from a different perspective:

**Agent 1: Codebase Patterns** (phoenix-patterns-analyst)

```text
Analyze how this codebase handles patterns related to: {topics from interview}

Focus areas:
- Existing modules: {file paths from interview Where dimension}
- Similar features: {patterns found during interview scans}
- Current architecture: {contexts, routers, schemas relevant to topic}

Write analysis to: .claude/plans/{slug}/research/codebase-scan.md

Structure your output as:
1. Existing patterns that could be extended
2. Gaps where new code is needed
3. Architectural constraints (schema dependencies, context boundaries)

Return ONLY a 500-word summary.
```

**Agent 2: External Research** (web-researcher)

```text
Research Elixir/Phoenix approaches to: {topic from interview What dimension}

Context: {2-3 sentence summary from interview}

Search for:
- Community patterns (ElixirForum, GitHub)
- Library options (Hex packages)
- Known gotchas or anti-patterns

Focus on approaches that would work with: {constraints from interview How dimension}

Return 500-800 word summary with source URLs.
```

### Step 2: Evaluate (Thesis + Antithesis per Approach)

After agents complete, read their output files. For each distinct approach found:

**Thesis** — Why this approach works for THIS codebase:

- Aligns with existing patterns found by codebase agent
- Satisfies constraints from interview (How dimension)
- Handles edge cases identified (Edge dimension)

**Antithesis** — Why this approach might NOT work:

- Conflicts with existing architecture
- Scale concerns given the project's size/traffic
- Complexity vs. the scope boundaries (Scope dimension)
- Missing library support or version incompatibility

This step happens in main context (not a subagent) because it requires
synthesizing both agents' findings with interview context.

### Step 3: Converge (Present 2-3 Options)

Present approaches to the user. Format each approach as:

```markdown
### Approach 1: {Descriptive Name}

{2-3 sentence description of the approach}

**Fits your codebase because:**
- {specific reason referencing existing code}
- {alignment with stated constraints}

**Might not fit because:**
- {honest concern}
- {trade-off}

**Would touch:** {list of files/modules}
**Complexity:** Low / Medium / High
**Libraries needed:** {new deps if any}
```

**Rules for convergence:**

- Always present at least 2 approaches (even if one is "do nothing differently")
- Never recommend one as "the best" — present trade-offs, let user choose
- If research found only 1 viable approach, present it alongside "simpler alternative"
  or "more robust alternative"
- Include a "Would touch" list so user understands blast radius

## After Presenting Research

Return to Decision Point. The user now has richer context and may:

1. **Continue interview** — research revealed new questions
2. **More research** — want deeper dive on a specific approach
3. **Make a plan** — ready to commit to an approach
4. **Store & exit** — need to think about it
5. **Discuss** — want to talk through the trade-offs

Update `.claude/plans/{slug}/interview.md` with research findings
(populate the "Research Findings" and "Approaches Found" sections)
BEFORE presenting the Decision Point.

## Iterative Research

**Cycle 1** (from Decision Point): MAX 2 agents — phoenix-patterns-analyst +
web-researcher. Keep it fast (~2-3 min). This covers most brainstorms.

**Cycle 2+** (user picks "More research"): Focused deep dives.

1. Ask what specific aspect needs deeper investigation
2. Spawn 1-2 targeted agents (e.g., specialist reviewer, focused web search)
3. Present focused findings
4. Return to Decision Point

**Track iterations** in interview.md:

```markdown
## Research Log
- Cycle 1: phoenix-patterns-analyst + web-researcher (3 approaches found)
- Cycle 2: deep-dive on beam scanning approach (prior art search)
```

**Soft limit**: After 3 research cycles, suggest: "We have substantial
research now. Ready to move to a plan, or is there a specific gap remaining?"

## Research Output Files

### `.claude/plans/{slug}/research/codebase-scan.md`

Written by phoenix-patterns-analyst:

```markdown
# Codebase Analysis: {topic}

## Existing Patterns
- {pattern 1}: found in {file_path}, used for {purpose}
- {pattern 2}: found in {file_path}, used for {purpose}

## Architecture
- Contexts involved: {list}
- Schema dependencies: {list}
- Router structure: {relevant scopes/pipelines}

## Gaps
- No existing code for: {what's missing}
- Would need new: {module/schema/migration/route}

## Constraints
- {constraint 1 from codebase analysis}
- {constraint 2}
```

### `.claude/plans/{slug}/research/external.md`

Written by web-researcher:

```markdown
# External Research: {topic}

## Community Patterns
- {pattern}: {description} (source: {url})
- {pattern}: {description} (source: {url})

## Library Options
| Library | Stars | Last Updated | Fits Because | Risk |
|---------|-------|-------------|-------------|------|
| {name} | {n} | {date} | {reason} | {concern} |

## Gotchas & Anti-Patterns
- {gotcha 1}: {description} (source: {url})
- {gotcha 2}: {description}

## Recommended Approaches (raw, pre-evaluation)
1. {approach}: {brief description}
2. {approach}: {brief description}
3. {approach}: {brief description}
```

## Integration with /phx:plan

When `/phx:plan` detects `.claude/plans/{slug}/interview.md` with research:

1. **Skips clarification** — interview IS the clarification
2. **Skips patterns-analyst spawn** — codebase-scan.md already exists
3. **May skip web-researcher** — external.md already exists (unless plan needs
   deeper research on a different aspect)
4. **Uses approach selection** — if user chose an approach at Decision Point,
   plan focuses on that approach. If not, plan may ask user to pick.

The interview.md "Summary" section becomes the plan's input. The "Coverage
Details" sections provide the depth that plan normally gets from clarification.
The "Approaches Found" section informs the plan's architectural decisions.
