# Performance Gates

A speed claim comes out of gates P0–P5, never out of one benchmark run (Iron Law 9). Correctness acceptance
(parity) and performance acceptance are separate gates: "passing parity proves the checked behavior, not that
the implementation is efficient".

The Campfire lesson is that **removing work beat redistributing it by orders of magnitude**. Two days of
pool and dispatch work ended near +19% room throughput at c16 over upstream, with p99 +54% at c64. PR #5
profiled whole requests, removed per-request work, and reports 17,237 room req/s. Its own notes put reader
checkout below 1% of the profile.

## P0 Workload Contract

Write this into ADR-000 before any architecture.

- **A primary goal with a number.** For example: "≥2× room req/s and ≤ +10% p99 at c64 vs the original on
  hardware X". Or: "idiom first; no route regresses more than N%". Re-confirm it when the user's framing shifts.
- **Workload.** Populated read routes, writes, realtime fan-out (100/500/1,000 clients), uploads and job drain,
  at concurrency 1, 16 and 64.
- **Metrics per route.** req/s, **CPU per successful response** (the primary efficiency metric), p50 and p99 per
  concurrency, peak memory, wire bytes, errors, job drain time.
- **Contracts the user may relax, each answered yes or no:**
  - per-form CSRF tokens vs Fetch Metadata
  - job durability
  - the proxy or TLS front
  - cookie write policy
  - byte-identical HTML or gzip vs decoded equivalence
  - the legacy socket protocol vs Channels or LiveView
- **Prior art.** Other ports, open PRs, upstream benchmark tooling. Campfire's Rust port had already been
  accepted diverging on every item in that list.

Exit: the contract is in the plan.

## P1 Baseline on Target Hardware

- **The original first.** Build the original production image and label it exactly: "untouched upstream
  `<sha>`". Never compare against your own intermediate build.
- **The host.** A dedicated native Linux host with **≥4 server CPUs** and disjoint CPU sets for the load
  generator (no shared SMT siblings).
- **Equal limits.** The same `nofile` for server and load generator. A Docker soft limit of 1,024 aborted the
  1,000-client case.
- **A quiet gate.** Load below 1.5 before each start. Record steal and throttling.
- **Pinned inputs.** Immutable image IDs and the same seed (checksum the archive and the DB). Pin the runtime,
  read `OTP_VERSION`, and rebuild the load generator unconditionally.
- **Proof the new path ran.** Log `System.schedulers_online()` and each runtime-gated feature at boot, and
  assert the new path is active (the pool process exists, the flag is on).

Exit: a baseline table plus a hardware block.

## P2 Whole-Request Profile

Profile **both** the original and the candidate before you name a bottleneck:

- queries and prepares per request
- bytes compressed per request
- call counts (eprof, tprof)
- scheduler and dirty-IO utilization (`:scheduler.utilization/1`)
- owner queue lengths
- CPU saturation per route

Use profiles for call counts, not time shares. Instrumentation changes timing (one sampler measured 981 vs
283 ms between arms), so keep profiled runs apart from clean timing runs.

Exit: hot paths ranked by measured share.

## P3 One-Variable Screens

- **Shape.** AB/BA pairs, fresh containers, short cells (about 12 s), a decoded-equivalence check, focused
  tests only.
- **Stop rule.** Drop a track after one screen that regresses any primary route, or after N hours without
  a ≥X% gain. Fix N and X in P0.
- **Promotion.** Only rebuilt release images get promoted. A hot-loaded prototype with 6 s cells did not
  predict the release over four rounds.

Exit: accept or reject each idea, and record both outcomes.

## P4 Full Matched Run

- Run it only for the candidate you intend to ship, after full parity has passed on that exact SHA.
- Run **≥4 balanced rounds** with warmups, for example `B1,C1,C2,B2,B3,C3,C4,B4`.
- Keep every attempt, including failed ones (`INCOMPLETE.md`). No reruns or exclusions after seeing results.
  Report min–max ranges.
- Count only populated 200 responses. Fan-out must be complete. Jobs must drain: three or more quiet
  observations spanning at least one second.
- Save raw counters (cgroup CPU before and after). Campfire's final run kept none, so its CPU deltas cannot be
  reconstructed.

Exit: a report with ranges and regressions.

## P5 Publication Hygiene

- **The PR body.** A compact summary, the hardware block and the deliberate-divergence list. Archive raw
  evidence outside the PR. Campfire's first PR added 96,645 lines, and 93,483 of them were evidence.
- **Regressions next to gains, in the same table.** The merged Campfire PR #4 reported room c64 p99 +54%,
  messages c64 p99 +87% and memory +7.9% beside its throughput gains.
- **Context tables.** Cross-language and cross-hardware tables appear only as context, labeled with their own
  hardware.

## "Faster Than the Original" Checklist

- [ ] The original and the candidate ran on the same host in the same block, from immutable images, with the
      same seed and the same proxy and compression path. Process-model differences are documented.
- [ ] The server had ≥4 schedulers, and the new concurrency path was verifiably active.
- [ ] ≥2 balanced AB/BA pairs for screens, ≥4 rounds for the claim, every attempt kept, ranges reported.
- [ ] Throughput, p99 at the highest concurrency, CPU per success, peak memory and wire bytes, per route.
      No route-agnostic "faster".
- [ ] Zero errors, all responses populated, decoded bodies equivalent, fan-out complete, jobs drained.
- [ ] Full parity green on the exact measured source digest.
- [ ] Every deliberate divergence listed: CSRF model, job durability, cookie policy, compression.
- [ ] The baseline labeled "untouched upstream `<sha>`". Gains over an intermediate build are never reported
      as gains over the original.
- [ ] Cross-language and cross-hardware numbers shown only as context, next to this run's hardware spec.

## Methodology Traps That Actually Happened

| Trap | What happened in Campfire | Rule |
|------|---------------------------|------|
| One-CPU server | The accepted overnight benchmark ran with `nproc 1`, so the scheduler-gated read pool never started. A PASS review plus a single-core run hid a multi-core regression | ≥4 schedulers; assert the new path is active; log gates at boot |
| Cross-hardware comparison | Ryzen 722 vs a Linux Xeon host's 314 room req/s were put in one table | Re-run the original on the target hardware; published tables are context only |
| Regressed intermediate as baseline | "Current" meant the agent's own regressed build, which produced a +112–125% "gain" | Label baselines "untouched upstream `<sha>`" |
| Baseline drift | One untouched image gave room c16 305.4, 314 and 287.55 req/s on one host across sessions | Only paired, same-block comparisons count |
| Throughput hides the tail | The final candidate: room c16 +19.4%, but room c64 p99 260 → 401 ms (+54.4%) and messages p99 210 → 393 ms (+87%) | Gate on p99 at the highest concurrency too; a "median p99" must say it is a median of cell p99s |
| Native vs emulated platform flip | Build `7c1ed67`: room c16 −16.3% on native Linux and +66.9% on an M4 under OrbStack. Rosetta amd64 needed `+JMsingle true`, and the host load was 29.06 | Native Linux timing host; no emulated images in timing; report other platforms separately |
| Build env leaking into the release | The toolchain image's `ERL_FLAGS` (`+JMsingle true`, `+S` pins) reached the release and could disable the gated pool | Reset `ERL_FLAGS` in the final image stage; log scheduler counts at boot |
| Accepted is not finished | Runs ended with 1,125 jobs queued, and DHH's baseline left 8,412 | A job-drain audit is part of the run |
| Equivalence by bytes | Search bodies 2.6% smaller (CSRF masks), gzip OS byte per platform, a 9.65× wire blow-up from naive compressed-part reuse | Compare decoded, normalized bodies **and** report wire bytes |
| Nondeterministic reference | Action Cable cross-channel order is not guaranteed | Assert per-channel order and payload sets |
| Harness assumptions | `PRAGMA busy_timeout` reads 0 under Exqlite's handler; a stale load generator; AppleDouble `._` files in a tarball | Smoke-test every driver path on a disposable fixture before timing |
| Unreproducible claims | PR #2 gitignored its raw JSON and measured warm, sequential, single-user Mac reads | Adopt no number whose raw data and harness you cannot re-run |
| Process cost | A 16-minute, 65-gate parity run plus a four-round benchmark for each micro-change | Focused checks plus a short screen for ideas; full parity and P4 only for the ship candidate |

## BEAM Performance Defaults

Each default carries its reason. Measure before you commit to it.

1. **Remove per-request work before adding concurrency.**
   - Memoize auth and session in `conn.assigns`. Batch N+1 queries: the sidebar went from 13 to 6 SELECTs
     for +33% throughput and −24% CPU.
   - Precompute headers, write cookies only on change, read the clock once per request.
   - Why: room was CPU-bound at about 3.5 of 4 CPUs in both arms, so more concurrency could buy about 0.4 CPU.
     Work you remove is saved on every core.
2. **Encode each broadcast once.**
   - Phoenix Channels already serialize once per serializer for all subscribers (the PubSub fastlane).
     Hand-rolled sockets must do the same.
   - Why: Campfire's Cable spent 33.7% of its time decoding JSON and 33.9% escaping it, because every
     subscriber re-encoded the same broadcast. Frame reuse gave 3.42× at 1,000 clients.
3. **Serve precompressed, correctly cached assets.**
   - Use `mix phx.digest`, `Plug.Static` with `gzip: true` and long-lived cache headers for digested paths, and
     conditional and range support.
   - Why: fixing asset cache headers alone gave 8.07× on static CSS.
4. **Compress once.**
   - Cache compressed bytes for stable content, or lower the zlib level. Never gzip a whole large body on every
     request.
   - Why: the room page spent 25% of CPU gzipping a ~464 KB body, and naive compressed-piece reuse cost −40%
     with 9.65× the wire size.
5. **Profile before naming the bottleneck.**
   - Why: an "idiomatic" pool caused the biggest regression. Exqlite's DBConnection path prepared every SELECT
     twice and doubled CPU per sidebar response (6.665 → 12.523 ms). A review flagged the double prepare at
     5.92% of the profile before the benchmark, and nobody acted on it.
   - Profiles also surface runtime gotchas: on OTP 28+ a literal `~r` was rebuilt on every evaluation
     (~17 µs vs 0.9 µs compiled).
6. **No fixed sleeps in job or delivery loops.**
   - Why: a 50 ms poll capped Campfire's jobs at 20/s. Oban's producers are notified on insert.
7. **Add owner processes only on evidence.**
   - The evidence is a long owner queue **while schedulers have headroom**.
   - Why: on a CPU-bound box more owners add dirty-scheduler hops and signals. The dirty signal handler went
     from 44 to 848 calls per sidebar response.
8. **Caches name their writer set.**
   - Key on every input, never cache errors, and bound eviction (translationese-checks.md T34–T38).
   - Why: every Campfire response-cache PR was blocked on invalidation for foreign writers.
9. **NIFs only for a whole measured hot loop.**
   - Run them on dirty schedulers, isolate crash-prone C (a port, not an in-VM NIF, for untrusted input), and
     install them atomically.
   - Why: a read NIF on normal schedulers was rejected, and in-VM parser crashes take down the node.

## When a Hand-Rolled Component Is Justified

Only when **all** of the following hold. Record them in an ADR (Iron Law 5).

1. A P2 profile on the target OS ranks the library path among the hot paths. Assumed overhead does not count.
2. A P3 screen shows the replacement winning on throughput **and** p99 **and** CPU per success, on every primary
   route.
3. The ADR lists every library semantic the replacement must re-provide: caller-side errors, rollback on raise,
   throw and exit, timeouts, overload queueing, supervision and restart. There is one test per semantic.
4. A flag switches back to the library path as a reversible A/B control. Turning Campfire's pool off restored
   sidebar c16 to 508 req/s, which proved the cause.
5. The decision is re-measured whenever the library is upgraded, because an upstream fix can retire it.

| Campfire component | Verdict |
|--------------------|---------|
| Cable frame-reuse cache | Justified: measured 3.42×, needed because the Turbo/Cable contract was kept |
| Owned SQLite readers + statement cache vs Exqlite 0.42's pool | Justified with a stated tail regression; re-measure against Ecto and each Exqlite release |
| Gumbo parser in isolated, bounded helpers | Justified for safety (crash isolation), not speed |
| In-process job queues replacing Resque | Not justified: speed bought by silently dropping durability (Oban Lite keeps it) |
| Whole-response caches keyed on a BEAM-local generation | Not justified: stale authorization after external writes |
| SQLite read NIF on normal schedulers | Rejected: one slow query blocks a scheduler |

Report every claim in one table shape so reviewers can diff runs:

```markdown
| Route | c | Baseline req/s (min–max) | Candidate req/s (min–max) | Δ | p99 base → cand | CPU/success | Wire bytes |
|-------|---|--------------------------|---------------------------|---|-----------------|-------------|------------|
```
