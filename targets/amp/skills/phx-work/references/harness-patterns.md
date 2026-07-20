# Harness Patterns for Error Recovery

Adapted from AutoHarness (Lou et al., 2026): programmatic verification
outperforms unstructured retry. A smaller model with good harnesses
beats a larger model without them.

## Critic-Refiner Pattern

When a task fails verification, use structured analysis instead of
immediate retry:

```
Attempt → Verify → FAIL
                    ↓
              Critic Phase (consolidate):
              - What EXACTLY failed? (first error only)
              - Is this the SAME error as before?
              - What has been tried already?
                    ↓
              Refiner Phase (targeted fix):
              - Address root cause from critic analysis
              - Don't repeat previous approaches
              - Check compound docs for known solutions
```

### When to Apply

- **Attempt 1**: Normal retry with error context
- **Attempt 2**: Pause. Compare errors. Same root cause = wrong mental model
- **Attempt 3**: Full critic analysis before BLOCKER decision

### Critic Analysis Template

Before the 3rd retry, consolidate:

```markdown
## Error Consolidation

**Command**: mix compile / mix test path:line
**Attempts**: 2 failed

**Error #1**: [exact error message]
**Error #2**: [exact error message]

**Same error?** Yes/No
- If YES → Root cause not addressed. Re-read source file.
- If NO → Progress made. New error is the real issue.

**Compound docs match?** grep -rl "KEYWORD" .claude/solutions/
**Dead-ends from scratchpad?** [any relevant entries]

**Next approach**: [specific, different from previous attempts]
```

## Action Verification Pattern

The plugin uses programmatic verification hooks (harness-as-action-verifier)
to catch invalid actions BEFORE they propagate:

| Hook | What It Verifies | Feedback On Failure |
|------|-----------------|---------------------|
| `format-elixir.sh` | Code formatting | "NEEDS FORMAT" warning |
| `iron-law-verifier.sh` | Iron Law violations in code content | Specific violation + line number |
| `security-reminder.sh` | Auth file patterns | Security Iron Laws checklist |
| `error-critic.sh` | Repeated mix failures | Consolidated error analysis |

Each hook follows the pattern:

1. **Propose** (Claude writes code)
2. **Verify** (hook checks programmatically)
3. **Reject with feedback** (specific violation message via stderr)
4. **Retry** (Claude fixes the specific issue)

This is more reliable than asking Claude to self-check because:

- grep-based checks never miss patterns
- Line numbers pinpoint exact locations
- Feedback is specific, not generic
- Verification runs every time (no skipping)

## Anti-Pattern: Unstructured Retry Loop

```
# BAD: Same approach, hope for different result
Attempt 1: mix test → FAIL
Attempt 2: tweak code → mix test → FAIL (same error)
Attempt 3: tweak more → mix test → FAIL (same error)
→ BLOCKER (wasted 3 attempts)
```

```
# GOOD: Critic-refiner with structured analysis
Attempt 1: mix test → FAIL
Attempt 2: compare errors → same root cause → re-read source
           → different fix approach → mix test → PASS
```
