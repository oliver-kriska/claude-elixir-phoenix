---
name: phx:research
description: Research an Elixir/Phoenix topic on the web. Searches ElixirForum, HexDocs, blogs, and GitHub. Uses efficient markdown conversion.
disable-model-invocation: true
---

# Research Elixir Topic

Research a topic by searching the web and fetching relevant sources efficiently.

## Usage

```
/phx:research Oban unique jobs best practices
/phx:research LiveView file upload with progress
/phx:research Ecto multi-tenancy patterns
/phx:research Phoenix PubSub vs GenServer for real-time
```

## Arguments

`$ARGUMENTS` = Research topic/question. Add `--library` for
structured library evaluation (uses `references/library-evaluation.md`
template).

## Library Evaluation Mode

If `$ARGUMENTS` contains `--library` or the topic is clearly
about evaluating a Hex dependency (e.g., "should we use permit",
"evaluate sagents", "compare oban vs exq"):

1. Read `references/library-evaluation.md` for the template
2. Follow the structured evaluation workflow
3. Output ONE document to `.claude/research/{lib}-evaluation.md`
4. Skip the general research workflow below

## Workflow

### 1. Search for Sources

Search multiple places for: **$ARGUMENTS**

```
Priority sources:
1. ElixirForum - community discussions, real-world experience
2. HexDocs - official documentation
3. GitHub - issues, discussions, code examples
4. Blogs - fly.io/phoenix-files, dashbit.co, thoughtbot
```

Use `WebSearch` tool to find relevant URLs:

```
WebSearch(query: "$ARGUMENTS site:elixirforum.com OR site:hexdocs.pm OR site:github.com")
```

For domain-specific searches:

```
# ElixirForum only
WebSearch(query: "$ARGUMENTS", allowed_domains: ["elixirforum.com"])

# HexDocs only
WebSearch(query: "$ARGUMENTS", allowed_domains: ["hexdocs.pm"])
```

### 2. Spawn web-researcher

Use Task tool to spawn `web-researcher` agent:

```
Task({
  subagent_type: "web-researcher",
  prompt: "Research: $ARGUMENTS\n\nFetch and analyze these sources: {urls from search}\n\nFocus on:\n- Code examples\n- Common patterns\n- Gotchas and warnings\n- Version compatibility",
  run_in_background: false
})
```

### 3. Output (File-First — NEVER Dump Inline)

**ALWAYS write output to a file** — never dump research inline.
One document per research question. No redundant summary/index files.
Target size: ~5KB for library evaluations, ~8KB for topic research.

Create `.claude/research/{topic-slug}.md` with:

```markdown
# Research: {topic}

## Summary
{2-3 sentence answer to the research question}

## Sources

### ElixirForum Discussions
- [{thread title}]({url}) - {key insight}

### Documentation
- [{doc page}]({url}) - {relevant section}

### Code Examples

```elixir
# From {source}
{example code}
```

## Recommendations

Based on research:

1. {recommendation with evidence}
2. {recommendation with evidence}

## Watch Out For

- {gotcha from forum/issues}
- {version compatibility note}

```

## Token Budget

| Source Type | Max Tokens |
|-------------|------------|
| Forum thread | 40,000 |
| HexDocs | 30,000 |
| Blog | 25,000 |
| GitHub issue | 20,000 |

Total research output should be under 100k tokens.

## After Research — STOP

**STOP and present the research summary.** Do NOT auto-transition to planning, implementation, or any other workflow phase.

Use `AskUserQuestion` to let the user choose their next action:

- "Plan a feature based on this research" → `/phx:plan`
- "Investigate a specific finding" → `/phx:investigate`
- "Research more on a subtopic" → continue research
- "Done" → end

**NEVER auto-invoke `/phx:plan` or any other skill after research.**
