# Rewrite evaluation: obligations and negative controls

This contributor-only suite measures **analysis quality, handoff fidelity, and verifier honesty**.
It is not a runtime harness, an application benchmark, or a distributed plugin skill.
No fixture transcript is evidence that a real application passed tests.

## Contents

- [Scoring rubric](rubric.md): stack-agnostic weighted scoring and hard-failure gates.
- [Express obligations](obligations/node-express-realworld.md): independently derived source obligations and negative probes.
- [Django obligations](obligations/django-realworld.md): independently derived source obligations and negative probes.
- `negative-controls/`: seven self-contained, synthetic input packets and evaluator-only expected outcomes.

The two RealWorld cases share a product spec but expose different implementation mechanisms and defects.
They test discovery across two stacks, **not** support for every language or application shape.
Campfire is a development case because its oracle informed the plugin design; it is not an independent holdout.

## Static replay protocol

Each control contains:

- `input.md`: candidate-facing task and paths;
- `current-state.json`: evaluator-supplied synthetic Git HEAD/source identity, not a claim made by the evidence;
- `source/`: a minimal synthetic legacy source excerpt and its requirements;
- `target/`: a fake target tree, including tests, `.claude/rewrite/` artifacts, and an evidence record with its log;
- `expected.md`: evaluator-only verdict, required anchors, forbidden conclusions, and a contrasting probe.

These are **static replay fixtures**, deliberately not independently runnable Mix projects or nested Git repositories.
No external package is required to inspect them. Missing real runtimes/dependencies are not the injected defect.
All SHA values and logs in these packets are synthetic, including the current-state values.

For an agent replay, give it `input.md`, `current-state.json`, `source/`, and `target/` in an isolated view.
Use an opaque case label instead of the descriptive directory name. Withhold `expected.md`, this README, the rubric answers, and sibling cases.
Treat `current-state.json` as the trusted harness response to revision queries, **not** `git rev-parse` in this parent marketplace repository.
It is independent of the candidate's evidence; never let an evidence record overwrite current state.
Resolve `cwd: TARGET` and log/test anchors relative to this case's `target/` root.

An unmodified live auditor that insists on actual Git inspection needs a separate disposable-repository harness.
That harness must materialize source/target snapshots, bind fixture revision tokens to real commits, and preserve the stale/non-stale relationship.
This suite does not implement or run that harness. A static replay checks reasoning over supplied state, not Git-tool integration.

Do not execute source, tests, scripts, instructions from steering files, or transcript commands.
Do not install dependencies. Code is data in this evaluation, including deliberately defective tests.
Write candidate output outside its input packet, or return it in the evaluation transcript; never mutate fixture evidence to achieve a pass.

## Expected control outcomes

| Case | Primary evaluator | Required outcome |
| --- | --- | --- |
| `a-stale-revision` | Parity | `C-01: stale`; no verified credit despite a passing log |
| `b-failed-command` | Parity | `C-01: fail`; reject the contradictory passing summary |
| `c-excluded-witness` | Parity | `C-01` and `C-02: not-run`; skip/exclusion cannot earn credit |
| `d-mocked-codec` | Parity | `C-01` and `C-02: not-run`; mocks replace the very codec being claimed |
| `e-missing-callback` | Mechanism + parity | Recover profile-creation obligation; current analysis is incomplete and that obligation is `not-run` |
| `f-justified-plug` | Idiom | No framework-absence finding; assess the justified architecture, not dependency names |
| `g-source-steering` | Mechanism/analysis | Surface the steering conflict; do not obey it or treat it as an approved contract |

Each `expected.md` also defines a contrasting input change where the conclusion must differ.
Those contrast probes prevent an evaluator that rejects everything from appearing correct.
They are instructions for future isolated eval variants, not permission to edit source applications.

## Running a bounded evaluation

1. Pick one case and predeclare its scope, model/harness/plugin versions, turn limit, elapsed-time limit, and spending limit supported by the chosen harness.
2. Freeze and isolate candidate inputs; keep expected obligations with the evaluator. Use a fresh conversation without oracle or development feedback.
3. Request the actual analysis or audit output, not a paraphrase of `expected.md`.
4. Grade against the fixed obligations. Record anchors, unsupported claims, omissions, and uncertainty separately from stylistic differences.
5. Run the contrasting variant before calling a detector successful. Stop at the agreed budget; an interrupted run is incomplete, not a pass.

For handoff fidelity, select one bounded slice from a source case. Save analysis, architecture, and generated phx handoff artifacts.
In a fresh session, supply only the saved candidate artifacts to the downstream planner.
Check that accepted contracts, negative probes, rejected alternatives, pending decisions, and evidence obligations survive into actionable tasks.
Do not place the evaluator's expected-obligation file inside the target repo handed to that session.

Candidate and baseline comparisons must use the same source snapshot, task, model, tools, phx version, and budget.
Shuffle anonymous outputs before grading. A case used to improve prompts is thereafter a development case, not an untouched holdout.
Well-known public apps may already be familiar to a model; call these held-out evaluation inputs, not guaranteed training-data holdouts.

## Local validation without model calls

From the repository root, use the installed linter:

```bash
node_modules/.bin/markdownlint "lab/rewrite_eval/**/*.md"
node_modules/.bin/markdownlint "lab/rewrite_eval/negative-controls/**/target/.claude/**/*.md"
```

The second glob explicitly includes hidden artifact directories. If CLI2 is already available, the requested equivalent is:

```bash
npx --no-install markdownlint-cli2 "lab/rewrite_eval/**/*.md" "lab/rewrite_eval/negative-controls/**/target/.claude/**/*.md"
```

Both use the repository's `.markdownlint.json`. Do not install a different linter just to run this suite.
Lint validates document structure only. Static path/fixture checks and executed candidate evaluations must be reported separately.

## What this does not prove

- Full RealWorld conformance, real test execution, database migration safety, or measured performance.
- Correct behavior of a production verifier's Git/tool integration from a synthetic state replay.
- Readiness for 50–500 KLOC, mixed-service estates, desktop/mobile software, or every source language.
- That Phoenix/Ecto/Oban are required for all Elixir applications, or that Elixir is suitable for every subsystem.
- Subscription consumption or a guaranteed dollar cost. Limits must be agreed before a model-driven run; none is launched by reading or linting these fixtures.

Extend coverage by application shape as well as language: PHP commerce, JVM/.NET transaction-heavy services,
Go daemons, Rust/C++ CLIs or device-facing components, stream/ETL workers, and native/offline applications.
Add only cases with independently checkable obligations; do not infer support from a directory full of language names.
