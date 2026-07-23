# Full Cycle Execution Steps

Use portable plan/work/verify/review instructions sequentially. Never transitively
invoke compound. Append one event per transition or outcome to `progress.md`; it
is the sole append-only state authority. Every event records monotonic `seq`,
`phase_visit`, `phase`, `cycle`, `task`, `task_attempt`, cumulative `blockers`,
`outcome`, and an `evidence` or `artifact` path. Task selection is legal only in
WORKING.

Discovery proposes depth and waits for the user gate. Planning writes and presents
the plan. Work updates checkboxes and append-only progress evidence. Verification
records exact commands and outcomes. Review is read-only; approved findings return
to WORKING as plan tasks. After accepted review, COMPOUNDING writes a solution
artifact only for a non-obvious reusable learning; otherwise it records SKIPPED.
The only successful order is REVIEWING → COMPOUNDING → COMPLETED.

Never silently continue through a blocker or limit. Report COMPLETE, BLOCKED, or
INCOMPLETE with cycle/retry counts, changed files, verification, review disposition,
artifacts, and the runtime-native resume action.
