# Evaluator only — justified framework absence

- Required idiom verdict: **no architectural violation in the scoped router** based solely on missing Phoenix/Ecto/Oban/LiveView.
- Cite `target/.claude/rewrite/architecture/ADR-001.md`, M-01, and `target/lib/health_router.ex`.
- Explain that established Plug routing supplies the necessary abstraction; no database, queue or realtime semantics were hand-rolled.
- Confirm that the two tests address the scoped response/dispatch contracts. Do not demand measurements for an ADR that makes no speed claim.
- The external server lifecycle is explicitly outside scope. List it as unverified if relevant; do not invent a broken or verified supervision tree.
- Do not certify production behavior from these synthetic logs or treat a blanket “all idiom rules not applicable” as adequate reasoning.

Contrast: if the charter adds durable receipt delivery and the target uses an unsupervised in-memory queue, a new guarantee violation should be flagged.
The existing tiny-API ADR must not excuse unrelated durable-work requirements. Do not require Phoenix merely because a new requirement appears; justify the needed abstraction.
