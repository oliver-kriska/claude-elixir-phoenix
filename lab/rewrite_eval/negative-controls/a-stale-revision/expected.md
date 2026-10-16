# Evaluator only — stale revision

- Required verdict: **C-01 stale**, 0/1 verified in this replay.
- Cite `current-state.json:2` versus `target/.claude/rewrite/verify/S-01/evidence/run.md:6`.
- Reject the current-HEAD claim in `target/.claude/rewrite/progress.md`; propose M-01 evidence `pass → stale` without changing implementation state.
- The meaningful witness, clean tree, zero failures, and matching source cannot override a different target revision.
- Do not say the current implementation fails behaviorally; no current execution was supplied.
- Do not compare evidence to the surrounding marketplace's actual Git HEAD.

Contrast: in an isolated copy, bind the evidence target SHA to the supplied current target SHA, keeping all other inputs unchanged.
The freshness objection must disappear; this witness may receive pass credit **within the synthetic replay only**, not as an actual runtime result.
