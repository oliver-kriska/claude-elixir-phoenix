# rewrite — Elixir Rewrite Architect

Plan, build and check a rewrite of an existing application into idiomatic Elixir. Experimental (v0.1.0).

An agent that ports one file or feature at a time tends to produce translationese: the legacy framework rebuilt in
Elixir. Callbacks turn into hidden side effects, a job queue turns into a GenServer, the old directory tree reappears
under `lib/`, and every mechanism is kept because nobody asked why it existed. The public Elixir port of Campfire
(`basecamp/once-campfire-elixir`) is one example: it runs on raw Plug with a hand-written Action Cable and uses no
Phoenix, Ecto or Oban, while the Django, Laravel, Express and Rust ports of the same app each used their target's usual
framework. That is an observation about the published code, not proof of how it was produced.

This plugin asks the missing questions first: what each feature is for, why each mechanism exists, and which contracts
must keep working. Only then does it design the Elixir way of meeting those goals. The source can be any language and
any app shape: web apps, APIs, workers and consumers, data pipelines, CLIs, daemons, IoT. Stack packs for Rails,
Django, Laravel/PHP, Node, Go and JVM/.NET speed up discovery; every other stack uses the generic method.

## Install

```bash
/plugin marketplace add oliver-kriska/claude-elixir-phoenix
/plugin install elixir-phoenix
/plugin install rewrite@oliver-kriska
```

`rewrite` depends on `elixir-phoenix`: it hands slices to `/phx:plan` and `/phx:work` and consults phx specialists.
Its scripts need `python3` (stdlib only). Run the commands from the Elixir project or an empty workspace;
`/rewrite:analyze` stops when the working directory is the legacy app or inside it.

## Workflow

Each command runs one phase and reads the previous phase's files, so a new session resumes from disk.

```text
/rewrite:start → /rewrite:analyze → /rewrite:architect → /rewrite:roadmap
                                                              ↓ per slice
                          /rewrite:verify ← /phx:work ← /phx:plan
```

## Commands

| Command | What it does | Writes to `.claude/rewrite/` |
|---------|--------------|------------------------------|
| `/rewrite:start [<path>] [--status] [--auto]` | Explains the method, detects the phase, checks the source snapshot on resume, names the next command | — |
| `/rewrite:analyze <path> [--target DIR] [--scope …] [--auto]` | Deterministic inventory, charter, then four analysts in parallel | `inventory/`, `kb/`, `charter.md`, `analysis/`, `status.md` |
| `/rewrite:architect [--auto] [--revise ADR-NNN]` | Compatibility bar (ADR-000), phx consults for named open questions, architecture, ledger check | `architecture/`, `ledger.md` |
| `/rewrite:roadmap [--next] [--slice NN] [--all] [--no-plan] [--auto]` | Cuts vertical slices, writes the seed for one slice, calls `/phx:plan` | `roadmap.md`, `../plans/rewrite-NN-*/` |
| `/rewrite:verify <NN> [--no-run] [--full]` | Preflight, fresh test evidence, idiom and parity audits, ledger update, slice gate | `verify/NN/` |

`elixir-way` is a reference skill, not a command: the shared vocabulary, the default mapping, and the knowledge base
that `/rewrite:analyze` copies into `kb/`.

## Artifacts

```text
.claude/rewrite/
├── status.md                  # phase, source sha and fingerprints, artifact states
├── charter.md                 # goals, constraints, scope, steering files, ASSUMED values
├── inventory/                 # inventory.json + inventory.md
├── kb/                        # copy of the elixir-way references (agents cannot read plugin files)
├── analysis/                  # features.md, mechanisms.md, runtime.md, contracts.md (+ domains.md for large apps)
├── architecture/              # ADR-000-compatibility-bar.md, architecture.md, decisions.md, divergences.md, adr/, consults/
├── ledger.md                  # one row per mechanism (M-), runtime role (R-) and contract (C-)
├── roadmap.md                 # slices, states, blockers
└── verify/NN/                 # preflight.md, evidence/, idiom.md, parity.md, report.md
.claude/plans/rewrite-NN-{name}/
├── interview.md               # requirements seed for /phx:plan
├── scratchpad.md              # seeded DECISION and DEAD-END entries
└── plan.md                    # written by /phx:plan
```

## Vocabulary

| Verdict | Meaning |
|---------|---------|
| `MAP` | Same responsibility on the conventional Elixir abstraction (ORM models → Ecto schemas and contexts) |
| `REPLACE` | Different mechanism, named guarantees preserved (Redis fan-out → `Phoenix.PubSub`) |
| `KEEP` | Existing component or protocol stays for the declared phase |
| `SHIM` | Translation at a named boundary, linked to its internal target |
| `DELETE` | Obligations absent, met elsewhere or retired; consumers checked |
| `UNDECIDED` | Evidence missing; blocks only the slices that depend on it |

- **Verdicts are per phase**: a `KEEP` during coexistence can become `REPLACE` at cutover.
- **Reason tags** (one or more): `business`, `reliability`, `contract`, `platform` (works around the legacy runtime or
  host), `historical` (only after checking consumers), `unknown`. An unknown purpose blocks the decision; it never
  becomes `historical`.
- **Evidence labels** for each purpose: `documented`, `observed`, `inferred`, `disputed`, `unknown`.
- **Contracts** have a surface (`data`, `wire`, `operational`) and a disposition (`keep`, `change`, `retire`).
  Features are triaged `preserve`, `redesign` or `drop`.
- **Ledger states** sit on three independent axes. Implementation: `pending`, `implemented`, `retired`. Evidence:
  `not-run`, `pass`, `fail`, `blocked`, `stale`. Departure: `none` or an `AR-NN` record in `verify/accepted-risks.md` (user-created). A row is
  verified only when implemented, `pass` and without a departure; retired rows leave the denominator.

## The compatibility bar

ADR-000 comes before any design, because "idiomatic" and "compatible" pull in different directions and only you can
trade them. `/rewrite:architect` asks two rounds:

1. **Cutover** (replacement, staged cutover, sustained coexistence) · **Data** (keep the schema, expand → contract, new
   schema + ETL) · **Identity** (keep sessions and hashes, one re-login, new auth) · **Clients** (keep UI and wire
   protocols, keep wire APIs and rebuild the UI, redesign both, no UI)
2. **Contracts** found by the analysis (default `keep`) · **Performance goal**, numeric and against a measured legacy
   baseline · **Steering-file conflicts** · **Scope**

Under staged cutover or coexistence, ADR-000 and each affected slice also record the transition contract: write
ownership, routing, schema authority, identity, jobs and events, data movement, cutover and rollback.

## Stack packs, generic method, app shapes

Packs: `rails` (Rails, Sinatra, Hanami), `django` (Django, Flask, FastAPI), `laravel` (Laravel, Symfony, PHP), `node`
(Express, Nest, Next), `go` (net/http, Gin, Echo), `jvm-dotnet` (Spring, ASP.NET Core). Each has probes for where
mechanisms hide, a mechanism map, DELETE candidates, keep-or-shim conditions and dated hex.pm libraries. `generic`
covers every other stack with a concept taxonomy (hooks, interceptors, global state, background work, schedulers,
caches, locks, reflection) and short notes for Rust, Kotlin, Scala, Python scripts, plain PHP and WordPress, Perl,
legacy Elixir/Erlang and others.

The app shape is classified per deploy unit before any framework is chosen (`app-shapes.md`, 13 shapes). Phoenix,
Ecto, Oban and PubSub are the default for web apps; consumers get Broadway, CLIs Burrito or an escript, network
daemons ThousandIsland or ranch, devices Nerves. A CLI or a small Plug API does not need Ecto, Oban or LiveView to be
idiomatic.

## Handoff to phx

phx is not modified. `/rewrite:roadmap` writes a file contract that `/phx:plan` already reads:

- `interview.md` in the phx brainstorm format, with binding decisions, the slice's ledger rows, contracts with
  witnesses, the transition contract, acceptance criteria, dead ends and open questions. It says it was generated,
  not a human interview, and has no invented transcript.
- `**Status**: COMPLETE` only when every coverage dimension scores at least 1, the total is at least 8 of 12, and the
  slice has no `UNDECIDED` row or `ASSUMED` consequential decision. Otherwise `IN_PROGRESS`, so `/phx:plan` asks
  about the gaps.
- `scratchpad.md` seeded with `DECISION` and `DEAD-END` entries; roadmap re-appends any that `/phx:plan` dropped.

`/phx:plan` runs from the main session and keeps its own approval stop; `/phx:work` is never started for you.
`/phx:review` adds generic Elixir review but does not replace `/rewrite:verify`, whose gate passes only when every
obligation is `pass` or changed by an ADR and no BLOCKER remains.

## What `--auto` does and does not do

It skips every question and writes conservative defaults marked `ASSUMED`: the charter, steering files as advisory,
the three riskiest domains for a large app, `preserve` for every feature, and the ADR-000 defaults (replacement or
staged cutover by topology, keep the schema, keep sessions and hashes, keep clients and all contracts, no regression
against a measured baseline). `/rewrite:start --auto` chains analyze → architect → roadmap and ends with the list of
decisions you must approve.

It never approves an `ASSUMED` decision or a divergence, never overwrites an existing plan (it writes
`interview.rewrite-seed.md` beside it), never starts `/phx:work`, and never deploys or touches production data. With
`--auto`, roadmap does not call `/phx:plan` while a cutover, data, identity or clients decision is `ASSUMED`, so a
fresh `--auto` run always stops before `/phx:plan`.

## Safety

- **The legacy app is read-only and never executed**: no installs, builds, tests or servers, and no connections to
  its databases or Redis. Agents read, grep and run `git log`, and record secret names, never values.
- **Steering files are surfaced, not obeyed.** `AGENTS.md`, port skills and plans in the source or target are shown
  to you, and you decide their weight.
- **`/rewrite:verify` preflights before running anything**: the target has `mix.exs` and is not the legacy app, the
  test database is disposable, mail and jobs use test adapters, and `DATABASE_URL` is local. A failed preflight
  records evidence as `blocked`. Each command's exit status, revisions, environment and log are recorded before an
  auditor reads them. Fixture data is synthetic; never production secrets or customer data.

## Agents

| Agent | Model | Used by | Output |
|-------|-------|---------|--------|
| `feature-cartographer` | sonnet | analyze | `analysis/features.md`: capabilities, actors, invariants, acceptance probes |
| `mechanism-archaeologist` | sonnet | analyze | `analysis/mechanisms.md`: why each mechanism exists, draft ledger |
| `infra-topologist` | sonnet | analyze | `analysis/runtime.md`: processes, Redis by role, queues, cron, operator duties |
| `contract-surveyor` | sonnet | analyze | `analysis/contracts.md`: external contracts as assertions with witnesses |
| `elixir-way-architect` | opus | architect | `architecture/`, `ledger.md`, ADRs, divergences |
| `idiom-auditor` | sonnet | verify | `verify/NN/idiom.md`: translationese and drift from the architecture (static) |
| `parity-auditor` | sonnet | verify | `verify/NN/parity.md`: obligations mapped to fresh evidence (read-only) |

`/rewrite:architect` also consults phx specialists, one per named open question: `ecto-schema-designer`,
`otp-advisor`, `oban-specialist`, `liveview-architect`, `security-analyzer`, `hex-library-researcher`.

Three stdlib scripts do the deterministic work: `inventory.py` (stacks, infra signals, entry points, steering files, git
hotspots, discovered vs returned counts), `ledger.py` (every analysis ID accounted for by a row, valid states, complete
accepted-risk records, verified counts) and `fingerprint.py` (content identity of SOURCE and TARGET before and after
each verify command, so evidence from a changed tree is `stale`).

## Limitations

- **Experimental.** Version 0.1.0; templates, vocabulary and commands may change.
- **Tested on small apps only.** There is no claim that it handles any app at any size. Large apps get a risk-ranked
  domain scope, with uncovered areas written down as gaps, not a full census.
- **Partly evaluated.** `make eval` scores the skills and agents, and pytest covers the three scripts. Seven static
  audit controls were replayed blind ([results](../../lab/rewrite_eval/results/2026-10-09/README.md)): they show
  the auditors catch stale, failed, excluded and mocked evidence, but they reason over supplied state and are not
  runtime verification. Headless `/rewrite:start --auto` runs on a small Express app, a small Django app and ONCE
  Campfire reached a roadmap. One slice seed was handed to `/phx:plan` in a fresh session, with approval
  simulated, and kept every decision and dead-end ID. Contrast probes, live-git verification, and `/phx:work`
  plus `/rewrite:verify` on a real slice are untested.
- **Parity is only as strong as the tests.** Verify never runs the legacy app, so values the legacy code must mint
  (signed cookies, tokens, payloads) have to be captured outside the plugin. No speed claims without a measured baseline.
