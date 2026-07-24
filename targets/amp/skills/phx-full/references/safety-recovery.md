# Safety Rails & Recovery

Resume from `.claude/plans/{slug}/plan.md` and append-only `progress.md`. Validate
the last valid event's evidence, plan checkboxes, artifacts, and git state, then
take only its legal successor. A WORKING edit after prior verify/review invalidates
those passes, so VERIFYING is next. Select tasks only after entering WORKING.

Stop on exhausted cycle/retry/blocker limits, unrecoverable compilation failure,
unsafe state, or a required user gate. Do not use autonomous loop commands, create
commits, or perform destructive resets as implicit checkpoints. Before stopping,
write the current state and return the exact portable skill invocation or
same-session step needed to resume.
