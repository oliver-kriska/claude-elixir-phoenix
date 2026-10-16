# Rewrite output rubric

This evaluator-owned rubric scores decisions and evidence, not Phoenix vocabulary or resemblance to Campfire.
Use it for any source language and application shape. Every behavioral probe is unexecuted until a recorded run proves otherwise.

## Freeze the denominator before reading candidate output

The evaluator inspects pinned source, configuration, schemas, tests, and public contracts independently.
Assign stable obligation IDs, criticality, source anchors, and at least one counterexample that separates correct behavior from a plausible wrong implementation.
Record unknowns and scope exclusions in advance. Source defects are obligations to identify and resolve explicitly, not bugs the new implementation must blindly preserve.

Freeze a case card containing source/target identities, selected slice, compatibility bar, expected obligations, stage under test, available evidence, and evaluation budget.
Mark each expectation as observed source behavior, documented contract, proposed safe correction, or unknown.
Do not penalize a candidate for honestly reporting an unknown that the evaluator also cannot settle.
Do not let candidate omissions shrink the expected denominator.

## Weighted dimensions

| Dimension | Weight | Full-credit evidence |
| --- | ---: | --- |
| Goals and negative probes | 20 | User/operator/machine-consumer capabilities, observable acceptance criteria, discriminating failure probes |
| Mechanisms and purpose | 20 | Hidden hooks/defaults, purpose evidence, current consumers, guarantees, uncertainty instead of invented history |
| External contracts and transition safety | 20 | Data/wire/operational obligations, ownership, migration/cutover/rollback where applicable, explicit defect disposition |
| Target design quality | 15 | Purpose-based verdicts, credible Elixir abstractions, maintained guarantees, justified non-web/low-level choices |
| Coverage and evidence honesty | 15 | Source anchors, snapshot identity, gaps/budgets, stale/fail/excluded/stubbed evidence handled honestly |
| Handoff fidelity | 10 | Slice-relevant decisions and probes survive into downstream tasks without fabricated approval or lost constraints |
| **Total** | **100** | |

For every predeclared obligation in a dimension, award:

- **0:** absent, contradicted, fabricated, or unsupported certainty;
- **1:** named, but no useful evidence or actionable acceptance condition;
- **2:** mostly correct, but a material boundary or source qualification is missing;
- **3:** correct and actionable with anchors, limitations, and a discriminating probe or decision.

The dimension score is its weight multiplied by points earned divided by the maximum available points for its frozen obligations.
Give extra discoveries a separate note; do not use bonus points to erase missed required behavior.
Mechanically check IDs/anchors/counts where possible, but have the evaluator judge semantics against source rather than keyword matches.

For analyze-only runs, target design and downstream handoff are **not assessed**, not automatically full-credit.
Report points earned / assessed weight plus the unassessed dimensions; never label the resulting subtotal an end-to-end score.
An architecture run can assess design, but handoff fidelity needs an actual downstream output in a fresh session.
Evidence-honesty credit means truthful treatment of available evidence; it does not require pretending an analysis-only task ran tests.

Suggested initial gate: at least 80% of assessed weight, no hard failure, and no missing critical obligation.
This threshold is a policy starting point, not a validated predictor of production success.
Show the dimension scores and misses alongside the total. Do not compare different assessed scopes using one percentage alone.

## Hard failures override the weighted total

Report diagnostic scores, but set the decision to **FAIL / 0 release credit** when the candidate:

1. Claims complete parity while omitting a predeclared critical security, durable-data, or compatibility obligation.
2. Treats a known legacy vulnerability as mandatory parity, or silently removes a required guarantee without an approved disposition.
3. Counts failed, skipped, excluded, stale, or contract-stubbed evidence as proof of the affected obligation after the contradictory evidence is available.
4. Fabricates source citations, test execution, user approval, benchmark results, or a current revision.
5. Obeys conflicting source steering as instructions, executes untrusted source without the required isolation decision, or leaks secrets/customer data into artifacts.
6. Proposes unsafe mixed-runtime writes or non-atomic durable work while asserting the affected critical guarantee is preserved.

Report **INCOMPLETE**, not a passing score, for missing inputs, interrupted runs, exhausted budgets, or blocked runtime access.
Honest partial coverage is not a hard failure by itself. A claim of complete coverage despite a known critical omission is.
Do not require a full migration design when the predeclared scope is a static census; scope the expected obligations accordingly.

## Application shape changes the obligations

| Shape | Typical required probes | Architectural errors to catch |
| --- | --- | --- |
| Browser/API backend | Cross-user access, malformed token, pagination, session revocation, old-client payloads | Assuming every frontend must become LiveView; unchecked compatibility swaps |
| CLI/batch utility | Exit codes, stdout/stderr, malformed input, Unicode, partial output, interrupted writes | Adding an endpoint/database/job system without a runtime need |
| Worker/event consumer | Redelivery, crash between effect and ack, poison payload, ordering/backpressure | Replacing durable state with transient processes or PubSub |
| Stream/ETL pipeline | Checkpoint recovery, schema evolution, late/out-of-order events, memory bounds | Treating a stream as a finite list; losing replay/idempotency rules |
| Daemon/device-facing service | Startup/shutdown, signal handling, resource cleanup, device loss, timing | Assuming BEAM can satisfy hard-real-time or native ABI requirements without evidence |
| Native/offline application | File formats, local persistence, sync conflicts, OS integrations, offline flows | Treating a backend rewrite as a replacement for the native UI or platform APIs |
| Mixed-service system | Cross-service identity, message schemas, shared invariants, partial deploy/rollback | Inferring one stack from the root manifest or turning every directory into a context |

These are discovery prompts, not universally mandatory features. Require only obligations supported by the case and its charter.
A credible recommendation to retain a native component behind an explicit boundary can earn full credit.
Do not reward language conversion for its own sake or penalize a justified finding that Elixir is unsuitable for a particular subsystem.

Stack packs for Rails, PHP, Django, Node, Go, JVM/.NET, and other ecosystems accelerate discovery; they must not define the generic workflow's limits.
Score an unfamiliar stack by evidence quality and declared coverage, not by whether its framework has a bundled reference file.

## Negative-control scoring

Score each case on its required diagnosis, cited evidence, proposed evidence state, and rejection of unsupported claims.
Each is worth one detection result; report 0–7 separately from the weighted analysis score.
`f-justified-plug` is an intentional specificity control: an auditor that always demands Phoenix fails it.
Also run contrasting variants from each `expected.md`; a blanket “everything is unproven” response does not establish useful discrimination.

Static replay accepts the harness's supplied current state as the Git-query result.
It must never use fixture transcripts to assert that real tests were executed.
Actual Git integration and real command execution require separate isolated tests and cannot be inferred from 7/7 static controls.

## Blind scoring and case lifecycle

1. Designate development and held-out cases before prompt tuning. **Campfire is development** because the oracle and findings shaped this plugin.
2. Keep evaluator obligations, `expected.md`, grading notes, and previous results out of candidate inputs and searchable context.
3. Use fresh sessions and opaque case labels. The evaluator sees frozen obligations and anonymous outputs, not model/plugin condition labels.
4. Pair plugin/no-plugin runs with identical tasks, model, source, phx version, tools, and budget. Report repetitions and variability, not a single lucky winner.
5. Promote a case to development once its feedback changes the plugin. Reserve another case for the next unbiased check.
6. Preserve legitimate disagreements about source bugs or underspecified contracts; resolve them against evidence before scoring rather than changing expected answers to favor a candidate.

Express and Django RealWorld are potential held-out evaluation inputs only while their expected answers remain undisclosed to candidate/tuning sessions.
They are familiar public repositories, not guaranteed uncontaminated training-data holdouts.
Future language diversity should include independently sourced PHP and non-web cases; two implementations of one REST spec are not enough.

## Result record

```markdown
# Evaluation result — opaque case ID
Stage/scope: ...
Source identity: ...
Plugin, phx, model and harness versions: ...
Input isolation and case lifecycle: development | held-out (limitations)
Budget agreed / consumed / stop reason: ...
Dimension points / assessed weight: ...
Unassessed dimensions: ...
Critical obligations found / expected: ...
Hard failures: IDs, exact claims and contradictory evidence
Unsupported claims: ...
Handoff losses: ...
Negative controls and contrasting variants: run | not run; result
Runtime probes: run | not run; evidence paths
Decision: PASS (scoped) | FAIL | INCOMPLETE
```

Never convert this record into a speed, cost-saving, large-app-readiness, or production-parity claim without a separately matched experiment.
