# Cycle Patterns

A cycle is one WORKING → VERIFYING → REVIEWING pass. Increment `task_attempt`
immediately before each attempt and increment `cycle` immediately before
VERIFYING. Count a cumulative blocker once, when its task first becomes blocked.
Reject a transition before its bound would be exceeded: `--max-retries N` permits
the initial attempt plus N retries. Review is read-only; findings return WORKING.
