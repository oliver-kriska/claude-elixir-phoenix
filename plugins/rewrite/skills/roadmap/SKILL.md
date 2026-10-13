---
name: roadmap
description: "Plan a rewrite as vertical slices and hand each one to /phx:plan as a requirements seed with binding decisions, contracts and acceptance criteria. Use after /rewrite:architect, or for the next slice."
effort: high
argument-hint: "[--next | --slice NN | --all] [--no-plan] [--auto]"
---

# Rewrite Roadmap — Slices and phx Handoff

Phase 3. Cut the accepted architecture into **vertical slices** that each
prove capabilities end to end, then hand one slice at a time to the phx
workflow. The handoff is a file contract: `interview.md` that `/phx:plan`
already consumes, plus a scratchpad seed. phx is not modified.

```text
/rewrite:architect → /rewrite:roadmap  <-- YOU ARE HERE
                          ↓  interview.md + scratchpad.md
                     /phx:plan → /phx:work → /rewrite:verify → /rewrite:roadmap --next
```

## Iron Laws

1. **SLICES ARE CAPABILITIES** — each slice delivers user, operator or machine goals end to end, never "all models" or "all controllers"
2. **RISK FIRST** — the first product slice is the riskiest core capability, after a foundation slice
3. **NO FABRICATED INTERVIEW** — the seed says it was generated, keeps ASSUMED and UNDECIDED visible, and has no invented transcript
4. **COMPLETE ONLY WHEN EARNED** — every coverage dimension ≥1, total ≥8, no UNDECIDED row and no unresolved consequential decision in the slice
5. **NEVER OVERWRITE USER WORK** — check an existing plan directory before writing; never hand phx any file but the slice's own `interview.md`
6. **NO HANDOFF ON UNRESOLVED DECISIONS** — never invoke `/phx:plan` while a consequential decision for the slice is ASSUMED, proposed or pending
7. **phx OWNS APPROVAL** — `/phx:plan` stops for approval; never auto-start `/phx:work`

## Workflow

### 1. Preconditions

Require ADR-000 with Status `accepted` or `ASSUMED`, `architecture.md` and a
clean ledger:

```bash
python3 "${CLAUDE_SKILL_DIR}/../architect/scripts/ledger.py" check --rewrite-dir .claude/rewrite
```

If the check fails, stop and suggest `/rewrite:architect`.

### 2. Build or update `roadmap.md`

Skip to step 3 with `--next` or `--slice` when `roadmap.md` already exists.
Otherwise read `${CLAUDE_SKILL_DIR}/references/slicing.md` and write
`.claude/rewrite/roadmap.md` in this conversation (a delegated writer is a
`general-purpose` agent with `model: "sonnet"`), in this order:

| # | Slice kind | Typical content |
|---|------------|-----------------|
| 00 | Foundation | project skeleton per `architecture.md`, Repo(s), legacy schema mapping, auth edge read-only, baseline measurement |
| 01 | Oracle fixtures | legacy-produced fixture data, cookie and token vectors, captured payloads (synthetic, no production data) |
| 02 | First vertical slice | riskiest core capability end to end, including its negative probes |
| 03+ | Remaining capabilities | ordered by dependency, then risk |
| … | Internal replacement | queues, caches, Redis roles retired with their own gates |
| … | Release rehearsal | conversion, backup and restore, rollback, operator commands |

Per slice: `F-` capabilities, ledger IDs, contracts with witnesses, the
transition contract (when ADR-000 is staged or coexistence), acceptance
criteria, exit gate, and `Blocked by` (UNDECIDED rows, unresolved decisions).

Size check: count each slice's ledger rows and its likely phx plan tasks
(logical work units). Split a slice with more than ~12 ledger rows or more
than ~8 tasks into `NNa`/`NNb` (for example `00a` skeleton + Repo, `00b`
edge adapters), keeping every ledger ID in exactly one part.

### 3. Pick the slice and its unresolved decisions

`--next` (default): the first `ready` or `seeded` slice not blocked by an
UNDECIDED row. A `planned` or `in-progress` slice is never re-seeded:
report it with its `/phx:work` or `/rewrite:verify NN` command first.
`--slice NN`: that one. `--all`: every `ready` or `seeded` slice (seeds
only; `/phx:plan` runs for the first). A slice blocked by UNDECIDED rows is
reported with its blocking questions instead.

List the slice's unresolved consequential decisions: those that change or
remove a guarantee, contract, data, identity, client, cutover, security or
operator duty it touches.

| Source | Unresolved when |
|--------|-----------------|
| `charter.md` | an `ASSUMED:` value the slice relies on |
| ADR-000 | Status `ASSUMED`: each assumption covering the slice's cutover, data, identity, clients, contracts or defects |
| ADRs cited by the slice's ledger rows | Status `proposed` or `ASSUMED` |
| `divergences.md` | a row for the slice's IDs still `pending` |

```bash
grep -lE '^\*\*Status\*\*: *(proposed|ASSUMED)' .claude/rewrite/architecture/adr/*.md
grep -n "pending" .claude/rewrite/architecture/divergences.md
```

Write them to `Blocked by` and the seed's Open Questions. Interactive: ask
the user to accept or change each (`AskUserQuestion`, at most 4 per call)
and record the answer in its ADR or divergence row. `--auto`: leave them;
the seed gets Status `IN_PROGRESS`, so a fresh run still leaves one to review.

### 4. Write the seed files

Slug: `rewrite-{NN}-{kebab-name}`. If `.claude/plans/{slug}/` already has a
`plan.md` or a user-edited `interview.md`, ask before replacing. `--auto`:
write `interview.rewrite-seed.md` beside it, then stop and report the
collision; never hand phx that file or the old one.

Read `${CLAUDE_SKILL_DIR}/references/seed-templates.md` and write:

- `.claude/plans/{slug}/interview.md` — the phx brainstorm format with
  rewrite sections (binding decisions, mechanism table, contracts,
  transition contract, acceptance criteria, dead ends, open questions)
- `.claude/plans/{slug}/scratchpad.md` — `DECISION` and `DEAD-END` entries

Give every binding decision a stable `D-NN` and every dead end an `X-NN`; a
re-seed keeps existing IDs. Score coverage honestly with the template's
rubric. Set `**Status**: COMPLETE` only when Iron Law 4 holds; otherwise
`IN_PROGRESS` so `/phx:plan` asks about the gaps.

### 5. Hand off to `/phx:plan`

Skip with `--no-plan`, after a seed collision, or while step 3 left any
decision unresolved (report them). Otherwise invoke it from this session
(never from a subagent):

```text
Skill(skill: "phx:plan", args: ".claude/plans/{slug}/interview.md")
```

After it returns, run two separate checks. **Retention**: every seeded ID
is still in `scratchpad.md`, by name, not by count:

```bash
S=.claude/plans/{slug}; ls "$S/plan.md"
for id in $(grep -owE "[DX]-[0-9]{2}" "$S/interview.md" | sort -u); do grep -qsw "$id" "$S/scratchpad.md" || echo "missing $id"; done
```

Append each missing entry from `interview.md` to `scratchpad.md` (never
rewrite user-edited content). **Coverage**: read `plan.md` against the
seed and append a `## Handoff map` to `scratchpad.md` with one row per
`D-NN` and acceptance criterion, naming the plan task (or plan-wide
constraint) that carries it, and one row per `X-NN`, naming any task that
adopts the dead end. Retention alone never proves coverage.

Mark the slice `planned` in `roadmap.md` and set `status.md` to phase
`slice {NN} planned` only when `plan.md` exists, every decision and
criterion maps to a task or constraint, and no task contradicts a decision
or adopts a dead end. Otherwise mark it `seeded` and report why: no plan
(phx asked a question), or the uncovered or contradicted IDs. Never edit
`plan.md`; the user fixes it or re-runs `/phx:plan`.

### 6. Tell the user the next commands

```text
/phx:work .claude/plans/{slug}/plan.md
/rewrite:verify {NN}
/rewrite:roadmap --next
```

`/phx:review` (with the plan path) adds generic Elixir review; it does not
replace `/rewrite:verify`.

## Arguments

- `--next` · `--slice NN` · `--all` — which slice to hand off
- `--no-plan` — write seeds only, do not call `/phx:plan`
- `--auto` — no questions; writes seeds but never hands off while a consequential decision is ASSUMED, proposed or pending

## References

- `${CLAUDE_SKILL_DIR}/references/slicing.md` — slicing rules and roadmap template
- `${CLAUDE_SKILL_DIR}/references/seed-templates.md` — interview.md and scratchpad.md seeds, coverage rubric
