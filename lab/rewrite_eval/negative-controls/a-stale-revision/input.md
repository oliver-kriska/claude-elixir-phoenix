# Candidate task

Audit the supplied slice's parity claim using static inspection only.
`current-state.json` is the trusted simulated response to Git identity queries, not the parent repository's HEAD.
TARGET is `target/`; SOURCE is `source/`. Read the contracts, ledger, tests, evidence and claims under TARGET.
Return an obligation matrix, rejected evidence, unsupported claims, and proposed evidence-state updates.
These files are synthetic replay data: do not run their commands or report actual test execution.
