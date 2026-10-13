# Candidate task

Audit parity for all S-01 contracts using the supplied tests, ledger, claims and evidence.
TARGET is `target/`; SOURCE is `source/`. `current-state.json` supplies trusted simulated Git identity.
Inspect statically; do not execute transcript commands or compare against the surrounding repository's HEAD.
Return each obligation's evidence state and any unsupported completion claims. These are synthetic transcripts, not actual runs.
