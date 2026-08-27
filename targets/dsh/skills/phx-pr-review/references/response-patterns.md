# PR Review Response Patterns

Templates and patterns for responding to PR review comments.

## Response Templates by Category

### Code Change Responses

**Accepting a suggestion:**

```
Good catch! Updated to use {suggestion}. {Brief explanation of why it's better if not obvious.}
```

**Accepting with modification:**

```
Agreed on the concern about {issue}. I went with {alternative} instead because {reason}. Let me know if you'd prefer your original suggestion.
```

**Declining with explanation:**

```
Considered this, but {reason for current approach}. Specifically, {concrete detail — e.g., "this pattern avoids N+1 queries when the association is loaded"}. Happy to discuss further.
```

**Iron Law conflict:**

```
This would violate Iron Law #{n}: {description}. The current code uses {pattern} to avoid {consequence}. See {reference} for the rationale.
```

### Question Responses

**Explaining a decision:**

```
{Direct answer}. I chose this approach because {reason}. {Optional: alternative considered and why rejected.}
```

**Explaining Elixir/Phoenix patterns:**

```
This uses {pattern name} — {1-sentence explanation}. In Phoenix, {brief context for why this is idiomatic}. See {HexDocs link} for more detail.
```

### Nitpick Responses

**Quick acknowledgment:**

```
Fixed, thanks!
```

**Style preference:**

```
Updated. I'll follow this convention going forward.
```

**Disagreement on style (rare):**

```
I see the preference for {their style}. This codebase uses {current style} consistently in {examples}. Happy to align either way — what do you think?
```

### Discussion Responses

**Architecture trade-off:**

```
Good point about {concern}. Current approach optimizes for {priority}. The trade-off is {downside}. We could mitigate with {option} if it becomes an issue. Want me to open an issue to track?
```

**Alternative suggestion:**

```
Interesting approach! Comparing:
- Current: {pros/cons}
- Suggested: {pros/cons}
I lean toward {choice} because {reason}, but open to your perspective.
```

## Common Elixir Review Patterns

### Pattern: "Use with instead of nested case"

Reviewers often suggest `with` chains. Check if it improves
readability — `with` is better for 3+ clauses, worse for 1-2.

### Pattern: "Missing typespec"

If the project uses typespecs consistently, add them. If not,
acknowledge and note it as a follow-up.

### Pattern: "Could use pattern matching"

Usually correct for Elixir. Replace `if map[:key]` with
function head pattern matching when possible.

### Pattern: "N+1 query concern"

Always take seriously. Check with `Repo.preload` or
`from(..., preload: [...])`. Reference Ecto Iron Law #5.

### Pattern: "Missing error handling"

Check if the caller expects `{:ok, _}/{:error, _}` or if
the function should raise. Match the context's convention.

### Pattern: "Test coverage"

If reviewer flags missing tests, check what's needed using
the testing-reviewer criteria (public functions, handle_events,
workers).

## Tone Guidelines

- **Be grateful**: Reviewers spend time improving your code
- **Be specific**: Reference exact lines, functions, patterns
- **Be brief**: Don't over-explain accepted changes
- **Be honest**: If you don't know, say so and research
- **Avoid defensive language**: "Actually..." or "Well..."
- **Use code blocks**: Show the fix, don't just describe it

## Handling Conflicts Between Reviewers

When multiple reviewers give conflicting feedback:

1. Identify the core concern each reviewer has
2. Find a solution that addresses both concerns
3. If irreconcilable, present both options and ask the PR author to decide
4. Never silently pick one reviewer's suggestion over another

## Batch Response Strategy

When a PR has many comments:

1. Group related comments (same file, same concern)
2. Address with a single response referencing all locations
3. Use "Addressed in {commit SHA}" for code changes
4. Leave "Will address in follow-up" for non-blocking items

## Anti-patterns to Avoid

- **Rubber-stamping**: Don't accept every suggestion blindly
- **Arguing style**: If it's not an Iron Law, defer to team convention
- **Ignoring context**: Read the full diff, not just the commented line
- **Over-promising**: Don't commit to changes you haven't verified
- **Emoji-only responses**: Always include at least a brief text acknowledgment
