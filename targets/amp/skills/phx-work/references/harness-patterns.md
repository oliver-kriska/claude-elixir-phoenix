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

Portable targets assume no lifecycle hooks. Verify actions explicitly after
each edit and use command output as feedback:

```bash
mix format --check-formatted <changed_files>
mix compile --warnings-as-errors
mix test <affected_test_files>
mix credo --strict
```

For auth/security changes, also search the changed files for unsafe atom
creation and untrusted raw HTML, then run negative-path authorization tests.
For repeated failures, capture the exact command and first error in the
scratchpad before trying a different approach.

The loop is: edit, run the explicit command, read its concrete failure, fix the
root cause, and rerun the same command. Do not rely on implicit automation.

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
