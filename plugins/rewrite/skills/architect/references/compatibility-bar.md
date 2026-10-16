# Compatibility Bar — Questions, Defaults, ADR-000

The bar decides what the port must keep working for people and systems that
already depend on the legacy app. Ask it before any design. Every answer
narrows the architecture; none of them is a technical preference.

## Round 1 (one `AskUserQuestion` call, 4 questions)

| Header | Question | Options (≤4) |
|--------|----------|--------------|
| Cutover | How will traffic move from the legacy app to Elixir? | **Replacement** — one maintenance window, rehearsed conversion, rollback by restore · **Staged cutover** — domain or route at a time, both runtimes live for weeks · **Sustained coexistence** — both run long-term with one owner per invariant |
| Data | What happens to the existing database and files? | **Keep schema as-is** — Ecto maps legacy tables · **Evolve via expand → contract** — keep data, change schema in steps · **New schema + ETL** — migrate once, legacy schema retired |
| Identity | What may happen to logged-in users and passwords? | **Keep sessions and hashes** — no forced logout · **Keep hashes, one re-login** · **New auth** — credentials reset |
| Clients | Which clients must keep working unchanged? | **Keep UI and wire protocols** · **Keep wire APIs, rebuild UI** (LiveView allowed) · **Redesign both** (approved behavior change) · **No UI** (API, worker, CLI, pipeline) |

Put the concrete numbers in each option description: user count, install
count, table count, public endpoints, socket clients (from the analyses).

## Round 2 (one call, up to 4 questions)

| Header | Question | Options |
|--------|----------|---------|
| Contracts | The analysis found N contracts, M incidental behaviours and K defects (list the top 4 by break cost; security defects first). | **By class** (default: keep `contract`, relax `incidental`, decide each `defect`) · **Review individually** (then one question per item) · **Keep data + wire, relax operational and incidental** |
| Perf goal | What does "fast enough" mean? | **No regression vs measured legacy baseline** (p95 latency, throughput, memory on a named workload) · **Specific target** (user types numbers) · **Measure only, no gate yet** |
| Steering | `charter.md` lists steering files that define "correct" differently. Which wins? | **Charter wins** · **Steering file wins for {topic}** · **Decide per conflict** |
| Scope | Which capabilities are in this rewrite? | **All preserved features** · **Domains from charter only** · **Preserve + redesign, drop flagged** |

Skip a question when the analysis makes it moot (no steering conflicts, no UI).

## Contract Classes

`contract-surveyor` tags every item; the class sets its default.

| Class | Meaning | Examples |
|-------|---------|----------|
| `contract` | a consumer is evidenced (test, client code, published spec, integration config, operator script) | legacy session cookie, webhook payload, password hash format |
| `incidental` | a framework default with no identified consumer; listed under "Incidental behaviour", not the register | `X-Powered-By`, weak ETag, case-insensitive paths, the default 404 page, URL-matcher quirks |
| `defect` | a legacy bug or security hole | credential or hash leak in a response, forgeable secret fallback, crash (5xx) on input |

A security defect is a `defect` that exposes credentials or secrets, allows
token forgery or an authorization bypass, or permits injection.

## `--auto` Defaults (conservative, all marked ASSUMED)

| Decision | Default | Rule |
|----------|---------|------|
| Cutover | Replacement | when `runtime.md` shows one deployable and one database; otherwise **Staged cutover** |
| Data | Keep schema as-is | always |
| Identity | Keep sessions and hashes | always |
| Clients | Keep UI and wire protocols | `No UI` when the shape has none |
| `contract` items | Keep | a consumer is evidenced |
| `incidental` items | Relax, with a `pending` divergence | no identified consumer; no SHIM is built for it |
| `defect` items | `UNDECIDED` | blocks only its slice |
| Security defects | Change toward safe behaviour, ASSUMED, with a `pending` divergence | blocks the handoff of its slice; never kept by default |
| Rollback window | Bounded: until the first approved destructive DDL, at most one release cycle | listed as an open decision; never "no end date" |
| Perf goal | No regression vs measured baseline | the baseline is a roadmap slice-0 task |
| Steering | Charter wins, conflicts listed | always |

`/rewrite:roadmap --auto` will not hand a slice to `/phx:plan` while any
consequential decision that slice depends on (charter, ADR-000, linked
ADRs, divergences) is still ASSUMED, proposed or pending.

## ADR-000 Template

```markdown
# ADR-000: Compatibility Bar

**Status**: accepted | ASSUMED (auto, needs approval)
**Date**: YYYY-MM-DD · **Source**: {path} @ {sha} · **Decided by**: {user | --auto}

## Assumptions (only when ASSUMED)
- {each default applied, with its rule}

## Cutover Mode
{Replacement | Staged cutover | Sustained coexistence} — {why, in one paragraph}

## Kept Contracts
| Contract | Surface | Class | Disposition | Consumers | Witness |
| C-04 legacy session cookie | wire | contract | keep | logged-in browsers | analysis/contracts.md C-04 |

## Changed or Retired Contracts
| Contract | Change | Consumers affected | Approval |

## Incidental Behaviour
| Item | Legacy default | Disposition (relax / keep with consumer) | Divergence |

## Defects
| Contract | Defect | Security? | Disposition (UNDECIDED / change → safe) | Divergence | Blocks slice |

## Data
{schema decision, DDL authority, file storage}

## Identity
{session issuer and reader, password hashes, revocation}

## Clients and UI
{what must keep working; whether LiveView may replace UI}

## Performance Goal
{metric, workload, environment, baseline source or "slice 0 measures it"}

## Steering Files
| File | Weight | Conflict | Resolution |

## Transition Concerns (staged cutover or coexistence)
{the rows from "Transition Contract" below that apply}
```

## Transition Contract (per aggregate or slice)

Required whenever both runtimes write or read live data.

| Concern | Decide and record |
|---------|-------------------|
| Write ownership | One owner per business invariant (not per table): HTTP, workers, admin scripts, imports, backfills |
| Routing | Which routes or cohorts go to which runtime; how non-owner writes are delegated |
| Schema authority | One DDL owner; supported old/new runtime × schema combinations; expand → backfill → validate → contract gates |
| Identity | Session issuer and reader, key access and rotation, revocation across both runtimes and open sockets |
| Jobs and events | Atomic intent, producer schema, consumer owner, idempotency, ordering |
| Data movement | Backfill checkpoint, conflict policy (versioned writes, tombstones, write pause), reconciliation |
| Cutover | Writer fencing and drain, switch, observation window, stop criteria |
| Rollback | Last reversible point; old readers tested against new writes; forward-recovery plan when reversal is impossible |

## Coexistence Rules

- **Shared database** — share storage, never split one invariant across two
  writers. Two runtimes updating different columns can still break it
- **Defaults and types** — check null semantics, defaults, enum values,
  timestamp precision and zones, triggers and ORM callbacks against both runtimes
- **Backfill is a writer** — a snapshot copy can overwrite newer values or
  resurrect deletes; it needs a checkpoint and a conflict policy
- **Sessions** — accepting legacy cookies does not require minting them
  forever; decide one-way or two-way issuance, and test revocation on both sides
- **Legacy producers into Oban** — on Postgres, the legacy app may insert
  `oban_jobs` rows in its own transaction (Oban documents this). Pin a
  producer contract: Oban version and engine, queue and worker names,
  versioned args, uniqueness, scheduling, and the measured pickup latency
  (raw inserts skip Oban's insert notification). Not proven for `Oban.Engines.Lite`
- **Two job systems** never consume the same logical work without an
  ownership and dedup protocol
- **SQLite** — test the real file topology, busy handling, transaction length
  and backup/restore; pooling does not make SQLite multi-writer
- **Permanent adapters are legitimate** — "sunset" means an owner, a support
  policy and exit conditions, not an arbitrary date
