# Slicing Rules and Roadmap Template

A slice is the smallest piece of the rewrite that proves a capability
works end to end in Elixir, inside the compatibility bar. It is the unit
`/phx:plan` plans and `/rewrite:verify` scores.

## Rules

1. **Cut by capability** — a slice names `F-` IDs. It touches every layer
   those capabilities need (schema, context, web or worker edge, jobs,
   realtime, auth), not one layer for every capability
2. **Foundation is thin** — slice 00 builds only what slice 02 needs:
   project skeleton, Repo topology, legacy schema mapping for the tables
   slice 02 touches, the auth edge read-only, and the legacy baseline
   measurement the performance goal requires. It passes the size check in
   roadmap step 2, or splits into `00a` skeleton + Repo and `00b` edge adapters
3. **Fixtures before behavior** — slice 01 captures legacy-produced data
   and vectors: database rows with real-world quirks (nulls, enums,
   microsecond timestamps), signed cookies and tokens minted by the legacy
   code, webhook payloads, file layouts. Synthetic users only; never copy
   production secrets or customer data. The plugin never runs the legacy
   app, so vectors come from the legacy repo's own fixtures and recorded
   cassettes, published spec vectors, or a capture the user makes on a
   non-production instance they run. `test/fixtures/legacy/PROVENANCE.md`
   records each one's source, revision, capturer and test secret. A vector
   the new Elixir code computed is not a legacy vector
4. **Riskiest core first** — slice 02 is the capability with the most
   guarantees and contracts (money, permissions, durable work, realtime).
   It proves the architecture; easy CRUD proves nothing
5. **One owner per invariant per phase** — under staged cutover or
   coexistence, every slice states which runtime owns each write it touches
6. **Replacements are their own slices** — retiring Redis roles, draining a
   legacy queue or swapping a cache gets separate correctness and
   performance gates; never bundle it with feature work
7. **UI modernization is optional and last** — only when ADR-000 allows a
   UI change; old-client transition is part of that slice
8. **Rehearsal closes the roadmap** — conversion, backup and restore,
   rollback or forward recovery, and the operator commands, all on a copy
9. **Blocked is explicit** — a slice that depends on an UNDECIDED ledger
   row or an unresolved consequential decision (ASSUMED, proposed or
   pending, in the charter, ADR-000, linked ADRs or divergences) lists them
   under `Blocked by`. UNDECIDED blocks the seed; an unresolved decision
   blocks only the `/phx:plan` handoff
10. **Size** — 3–8 phx plan tasks and at most ~12 ledger rows per slice;
    the size check in roadmap step 2 splits a larger one into `NNa`/`NNb`
11. **Oracles set slice 01, each slice's suite files and the perf script** — read the grade in the
    `## Oracles` section of `.claude/rewrite/inventory/inventory.md`, lowered by the `## Oracle Grade`
    verdict in `contracts.md` when the surveyor downgraded it. An inventory without that section
    predates oracle detection: treat the grade as `none` until `/rewrite:analyze` re-runs
    - **`weak` or `none`** — slice 01 also writes characterization tests: ExUnit
      tests that assert the legacy captures from rule 3 for every capability in
      slice 02. No behaviour slice is seeded until slice 01 is `done`
    - **Black-box or E2E suite** (Hurl, Postman, Bruno, REST Client, Tavern,
      Dredd, Playwright, Cypress, Gherkin; in SOURCE or an `--oracle` dir) —
      assign each file to the first slice after which every request in it can
      pass, its setup and cleanup requests included: a file that registers a
      user and deletes its article belongs to the slice that adds DELETE, not
      the one it is named after. Earlier slices may run it as a diagnostic that
      does not gate, except for a leading run of entries an earlier slice can
      pass in full (register and login before the user routes): that range
      gates the earlier slice (Hurl `--to-entry N`, one command per file), and
      the whole file still gates its own slice. The seed lists the files with
      the exact command under `## Oracle`, run so one failure does not hide the
      rest (Hurl: `--continue-on-error`); roadmap.md lists unassigned files
    - **Benchmark or load harness** — P1 in `.claude/rewrite/kb/performance-gates.md` drives the
      baseline and the candidate with it. Without one, slice 00 writes a
      port-only load script (k6 or wrk) over the P0 routes, labelled
      "no legacy comparison": it catches regressions between port builds and
      supports no claim about the original
    - **Legacy is never executed** — every suite runs against the port only;
      legacy tests are translated into ExUnit, never run, unless an accepted ADR
      or ledger decision grants running the legacy app in isolation
12. **A row goes where its Target is built** — assign each ledger row to the
    slice that builds every part of its Target column. A Target that spans
    slices goes to the last of them: a DELETE of a test-only hasher whose
    replacement hasher the auth slice writes belongs to the auth slice, not
    the foundation. A row with nothing to build in the port, such as an
    untouched external consumer, goes to the slice whose gate exercises it,
    usually the rehearsal's full suite run. Otherwise verify can only score
    the row `not-run` and the slice gate fails on work that slice never owned

## Ordering Heuristics

- Dependencies first (identity before anything that checks permissions)
- Then by risk: auth, money, tenancy, destructive operations, data export,
  durable work, public integrations
- Shared mechanisms land with the first slice that needs them, then get
  reused; later slices reference the ledger row, never re-specify it

## Slice by App Shape

| Shape | Slice 02 usually proves |
|-------|-------------------------|
| Web app / SaaS | an authenticated write path with its side effects and a negative permission probe |
| API service | the busiest endpoint with its exact wire contract, errors and pagination |
| Realtime | join → authorized broadcast → revocation while connected → reconnect |
| Worker / consumer | consume → idempotent effect → ack; crash mid-message; duplicate delivery |
| Pipeline / ETL | one full run on a fixture, byte-identical or approved-diff output, re-run idempotency |
| CLI / tool | the most used command's flags, exit codes, output format and config file |
| Daemon / network service | protocol handshake, one request type, overload and slow-client behavior |

## `roadmap.md` Template

```markdown
# Rewrite Roadmap — {app}

Bar: ADR-000 ({accepted | ASSUMED}) · Mode: {cutover mode} · Source @ {sha}

| # | Slice | Capabilities | Ledger | Contracts | State | Blocked by |
|---|-------|--------------|--------|-----------|-------|------------|
| 00 | Foundation | — | M-03, R-01 | C-11 | ready | — |
| 02 | Checkout | F-03, F-04 | M-07, M-12, R-04 | C-04, C-09 | ready | — |
| 05 | Nightly export | F-09 | M-21 | C-15 | blocked | M-21 UNDECIDED (purpose of SQL job) |

## 02 Checkout
**Goal**: {capability sentences from features.md}
**Ledger rows**: M-07 (REPLACE → Ecto.Multi + Oban), M-12 (REPLACE → Oban), R-04 (DELETE)
**Contracts**: C-04 (keep legacy cookie), C-09 (keep webhook payload v2)
**Transition**: {only for staged/coexistence: owner, schema authority, identity, jobs, data movement, cutover, rollback}
**Acceptance criteria**: {probes from features.md, witnesses from contracts.md}
**Oracle**: legacy tests to translate {paths} · black-box files {files or requests, `--oracle` root} · perf {harness or port-only script, or none}
**Exit gate**: `/rewrite:verify 02` — every obligation passes, or is changed or retired by an *accepted* ADR or an AR record whose `Approved` field the user filled; no BLOCKER
**Plan**: .claude/plans/rewrite-02-checkout/ · State: ready | seeded | planned | in-progress | done
```

States: `ready` → `seeded` (seed written, no retained plan yet) →
`planned` (`plan.md` exists and the handoff map covers every `D-` ID) → `in-progress` →
`done` (verify gate passed) · `blocked`.

## Exit Gate

An obligation clears the gate only when it passes on fresh evidence, or is
changed or retired by an ADR with Status `accepted` or an AR record in
`.claude/rewrite/verify/accepted-risks.md` with Owner, Scope, Rationale,
Review and an `Approved` field filled by the user. ASSUMED or proposed
decisions, a drafted ADR and a bare AR heading never count.
