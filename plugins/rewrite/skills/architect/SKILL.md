---
name: architect
description: "Design the idiomatic Elixir architecture for a rewrite: set the compatibility bar (ADR-000), consult phx specialists on open questions, then build contexts, ledger and ADRs. Use after /rewrite:analyze."
effort: high
argument-hint: "[--auto] [--revise ADR-NNN]"
---

# Rewrite Architect — Compatibility Bar, Then Design

Phase 2. First decide **what must stay compatible** (ADR-000), then design
the Elixir system that meets the goals inside that bar. The bar comes first
because "idiomatic" and "compatible" pull in different directions, and only
the user can trade them.

```text
/rewrite:analyze → /rewrite:architect  <-- YOU ARE HERE
                         ↓
                   /rewrite:roadmap → /phx:plan → /phx:work → /rewrite:verify
```

## Iron Laws

1. **ADR-000 BEFORE ANY DESIGN** — never spawn the architect without an accepted or ASSUMED bar
2. **THE USER OWNS TRADE-OFFS** — cutover mode, forced logouts, schema changes and UI changes are asked, never inferred
3. **CONSULT BY QUESTION** — spawn a phx specialist only for a named open question, with an evidence packet
4. **LEDGER MUST CHECK CLEAN** — run `ledger.py check` and fix or report every error before presenting
5. **ASSUMED IS NOT APPROVED** — `--auto` decisions stay `ASSUMED` until the user accepts them
6. **SPAWN FROM THIS SESSION** — agents never spawn phx orchestrators (nesting depth)

## Workflow

### 1. Preconditions

Require `.claude/rewrite/analysis/{features,mechanisms,runtime,contracts}.md`;
if any is missing, stop and suggest `/rewrite:analyze`. Read the paths from
`status.md`, stop if the cwd is not `Target path`, and check that the source
is unchanged:

```bash
SOURCE=$(sed -n 's/^Source path: //p' .claude/rewrite/status.md)
TARGET=$(sed -n 's/^Target path: //p' .claude/rewrite/status.md); [ "$(pwd -P)" = "$TARGET" ]
python3 "${CLAUDE_SKILL_DIR}/../analyze/scripts/inventory.py" "$SOURCE" \
  --compare .claude/rewrite/inventory/inventory.json
```

Exit 1 from `--compare` means stale analysis: tell the user and offer to
re-run `/rewrite:analyze` first. Resume: when ADR-000 exists but phase is
`architecting` or `architecture.md`, `decisions.md` or `divergences.md` is
missing, keep ADR-000 and `consults/` and continue at step 4 (step 5 when
all four exist and only `ledger.py check` failed).

### 2. Compatibility bar → ADR-000

Read `${CLAUDE_SKILL_DIR}/references/compatibility-bar.md` for the question
set, the defaults and the ADR-000 template. Ask with `AskUserQuestion` in
two rounds, at most 4 questions each:

1. **Cutover mode** · **Data** · **Identity** · **Clients/UI**
2. **Contracts** (the `Decisions Needed for ADR-000` list from `contracts.md`;
   default by class: keep `contract`, relax `incidental`, decide each
   `defect`) · **Performance goal** (numeric, against a measured legacy
   baseline) · **Steering conflicts** from `charter.md`

With `--auto`, apply the per-class defaults from the reference, set Status
`ASSUMED`, and list every assumption at the top of the ADR. A security
defect is never kept by default.

Write `.claude/rewrite/architecture/ADR-000-compatibility-bar.md`. When the
mode is staged cutover or coexistence, ADR-000 also names the transition
concerns the roadmap must cover per slice (write ownership, schema
authority, identity, jobs, data movement, cutover, rollback).

### 3. Consults (only for open questions)

Read the `Questions` sections of the four analyses. Map each design-relevant
question to at most one specialist, in parallel and at most 4 at a time:

| Open question about | Spawn |
|---------------------|-------|
| Legacy schema mapping, transactions, constraints | `phx:ecto-schema-designer` |
| Runtime topology, processes, supervision | `phx:otp-advisor` |
| Durable work, legacy queue transition | `phx:oban-specialist` |
| UI redesign in LiveView (only if the bar allows it) | `phx:liveview-architect` |
| Legacy auth, crypto, session handoff | `phx:security-analyzer` |
| A library not in `kb/` | `phx:hex-library-researcher` |

Each prompt states the question, the evidence paths to read (analysis
sections, `kb/` files, SOURCE anchors) and the output file
`.claude/rewrite/architecture/consults/{agent}.md`. It says: "You are a
consult: answer the question, do not plan or implement. Write the output
file with your current answer before further research, and update it as
you go." No open questions means no consults.

Stay in this turn until every consult reports (see analyze step 6). Then
check each file exists; for a missing one, resume the agent once with
`SendMessage` (or re-spawn it once), and record a still-missing consult as
a gap in `status.md`.

### 4. Synthesize

Set `status.md` phase `architecting` first, so a cut-off run is detectable.
Spawn `rewrite:elixir-way-architect` (opus) in the FOREGROUND
(`run_in_background: false`): it is one long agent with nothing to run in
parallel, and headless `claude -p` stops background agents 10 minutes after
the last turn. Pass `CHARTER`, `BAR`, `ANALYSIS`, `CONSULTS`,
`KB=.claude/rewrite/kb/`, `PACKS` (each `pack` in `inventory.json`
`stacks`), `TARGET`, `OUT=.claude/rewrite/architecture/`, and `RESUME` (the
architecture files already present, or `none`). It writes `architecture.md`
and `ledger.md` first, then the ADRs, then `divergences.md` and
`decisions.md`. If it returns `BLOCKED`, fix the precondition it names.

### 5. Check the ledger

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/ledger.py" check --rewrite-dir .claude/rewrite
python3 "${CLAUDE_SKILL_DIR}/scripts/ledger.py" stats --rewrite-dir .claude/rewrite
```

`check` counts an analysis ID only from a row's ID cell (one row per
alias), so fix an unaccounted ID with a row, e.g. a DELETE row whose purpose
reads "absent in legacy", never with prose. Rows need every header cell and
Departure `none`; an `AR-NN` departure needs the user's approved record in
`verify/accepted-risks.md`, which neither you nor the architect writes.
On errors (unaccounted or duplicate IDs, short rows, invalid verdicts,
missing ADR files), send the error list back to the architect once via
`SendMessage` (or re-spawn it with the list); if errors remain, show them to
the user instead of hiding them and keep phase `architecting`. Only after `check` passes and
`decisions.md` and `divergences.md` exist, set `status.md` phase
`architected` (`architected (ASSUMED)` under `--auto`).

### 6. Present for approval

Show, from the architect's return and `architecture.md`: the context map,
the process table, verdict counts (UNDECIDED and what they block), the
three decisions that most need review, and pending divergences. Ask:

- **Accept** — set ADR Status `accepted` and divergences `approved`
- **Revise** — name an ADR or area; re-run step 4 with the feedback
- **Stop** — keep everything as `proposed`

`--auto`: leave Status `ASSUMED`, do not mark divergences approved.

`--revise ADR-NNN`: re-open one decision, re-run steps 3–5 for it only, and
mark ledger rows that cite it with evidence `stale`.

Next step: `/rewrite:roadmap`.

## Arguments

- `--auto` — conservative per-class defaults for every bar question, marked `ASSUMED`
- `--revise ADR-NNN` — re-open one decision

## References

- `${CLAUDE_SKILL_DIR}/references/compatibility-bar.md` — questions, defaults, ADR-000 and transition template
- `${CLAUDE_SKILL_DIR}/scripts/ledger.py` — `check` and `stats`
