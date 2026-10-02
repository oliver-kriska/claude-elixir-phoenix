# S5: Verified Research Mode (`--verified` flag)

Future enhancement for `/phx:autoresearch` — iterative verification of research output.

## Design (from verification-initiative research)

Add `--verified` flag to `/phx:research`:

```
/phx:research --verified "LiveView streams vs assigns for large lists"
```

This triggers the autoresearch loop applied to research quality:

1. Initial research → draft brief
2. Verify → identify unverified claims (using output-verifier agent)
3. Re-search unverified claims with targeted queries
4. Verify again → remove remaining unverified claims
5. Produce verified brief + provenance sidecar

## Implementation Notes

- Cap at 3 iterations (Self-Refine paper: first iteration catches ~80%)
- Display progress: "Verifying... 14/18 claims confirmed, 2 re-searching, 2 removed"
- Depends on: output-verifier agent (S1b) and source quality tiers (S1a)
- Interactive latency concern: 5-10 min per iteration — users may not wait
- Best for: long-running research on critical topics, library evaluation, architecture research

## When It Makes Sense

- Library evaluation before adding a dependency
- Architecture research before a major rewrite
- Any research that feeds directly into implementation decisions
- NOT for quick "how do I do X" questions

## Provenance Sidecar Format

```markdown
# Provenance: {filename}

**Verified:** {n}/{total} claims | **Sources:** {count} (T1:{n} T2:{n} T3:{n})
**Removed:** {list of claims removed and why}
**Conflicts:** {list of unresolved contradictions, or "none"}
```

## Research Sources

- Self-Refine paper: first iteration catches ~80% of issues
- CoVe (Chain of Verification): verifier independence principle
- FIRE: iterative fact-checking with 7.6x cost reduction
- Feynman deep research: 8-phase with verification review (Phase 7)
- FActScore: 42%+ hallucination rate in niche domains
