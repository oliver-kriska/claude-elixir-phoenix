# Candidate task

Statically audit TARGET (`target/`) against its accepted architecture and mechanism ledger.
SOURCE is `source/`; `current-state.json` supplies simulated Git identity. Scope: `target/lib/health_router.ex`.
Read ADR-001, architecture, contracts and tests; report architectural violations with anchors or explain why none were found in this scope.
Do not execute source, Mix, or the synthetic evidence commands. Do not turn a static design assessment into production parity certification.
