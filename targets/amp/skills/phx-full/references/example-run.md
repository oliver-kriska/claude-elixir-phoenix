# Example Full Cycle

The runtime discovers relevant context, proposes planning depth, and waits at the
user gate. After approval it creates the plan, presents it, executes approved
tasks in order, and records focused checks. It then runs the final verification
gate and a read-only review. Approved findings become plan tasks and consume a
bounded cycle. The ledger records PHASE_ENTER/PASS/FAIL and all counters. Only a
passing verification and accepted review advance REVIEWING → COMPOUNDING →
COMPLETED; limits or unresolved blockers return INCOMPLETE/BLOCKED.
