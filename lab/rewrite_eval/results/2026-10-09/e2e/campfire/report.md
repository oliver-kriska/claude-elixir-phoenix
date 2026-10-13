# E2E: `/rewrite:start --auto` on ONCE Campfire, scored against the oracle

Date: 2026-10-09 · Case: **development** (judged strictly) · Oracle: `.claude/research/2026-10-09-amp-campfire-elixir-way-oracle.md` §5 · Critique: `.claude/research/2026-10-09-amp-rewrite-design-critique.md`

SOURCE: `~/Projects/campfire-bench/once-campfire-elixir/reference` @ `90b330024dec` (read-only; nothing under `campfire-bench` was written, installed, built or run).
WORKSPACE: `$S/e2e/campfire` (empty `git init`, no commits). Artifacts copied to `$S/e2e/campfire-artifacts/` (`run1/` = snapshot after the truncated first run, `final/` = after the resume run, plus `ledger-check-final.txt`).

`$S` = the session scratchpad (normalized when this file was saved to the repo).

**Verdict: 86/100, 0 hard failures — for the artifacts as they stand after a manual resume. The first, unattended run died in the architect phase and left no ledger, so a single headless `--auto` run of the shipped plugin does not reach a scoreable handoff (defects 1 and 2).**

## 1. Run facts

| Fact | Run 1: `/rewrite:start $SOURCE --auto` | Run 2 (resume): `/rewrite:start --auto`, `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` |
|---|---|---|
| Stream | `$S/e2e/campfire-run.jsonl` (4.2 MB) | `$S/e2e/campfire-run2.jsonl` (1.0 MB) |
| Wall clock | 09:34:47Z → 10:18:21Z (43.5 min) | 10:20:09Z → 10:49:54Z (29.7 min; `duration_ms` 1,779,628) |
| Cost | redacted (all `claude-opus-5-5`, 375,776 output tokens) | redacted (all `claude-opus-5-5`, 177,699 output tokens) |
| `num_turns` | 11 | 14 |
| Assistant messages / tool calls | 467 / Bash 153, Read 65, Grep 19, Write 11, Agent 9, Glob 8, Skill 2, Edit 2 | 84 / Bash 47, Read 9, Write 4, Agent 2, Skill 2 |
| Skills fired | `rewrite:analyze --auto`, `rewrite:architect --auto` | `rewrite:architect --auto` (resume), `rewrite:roadmap --auto` |
| Subagents | 9, **all `model: opus`, `run_in_background: true`**: feature-cartographer, mechanism-archaeologist, infra-topologist, contract-surveyor, phx:security-analyzer, phx:oban-specialist, phx:otp-advisor, phx:ecto-schema-designer, elixir-way-architect | 2, foreground: `rewrite:elixir-way-architect` (opus), `general-purpose` (opus) "Write rewrite roadmap and slice-00 seeds" |
| `permission_denials` | `[]` | `[]` |
| Termination | `subtype: success`, but `subagent_stats.killed.system = 1`. `campfire-run.err`: "Background tasks still running 10m after the last turn (subagent "Synthesize Elixir architecture"); stopping them." The architect died after 26 tool calls: ADR-001..010 + consults written, **no `architecture.md`, `ledger.md`, `decisions.md`, `divergences.md`**. `ledger.py check` on `run1/`: `error: missing ledger.md` (exit 1); `stats`: `verified 0 of 0` | `subtype: success`, `killed: 0`. Resume detected correctly ("Preconditions hold… skipping steps 2–3 and resuming at synthesis"); analysis and consults not redone |

**Plugin loading.** As shipped, `plugins/rewrite/.claude-plugin/plugin.json` declares `"dependencies": ["elixir-phoenix"]`. With `claude -p --plugin-dir plugins/rewrite --plugin-dir plugins/elixir-phoenix …` the stream-json `init` message lists `rewrite cmds: []` (`$S/e2e/smoke-init.jsonl`); the model's own answer (`$S/e2e/smoke.json`) is "None of these are loaded in this session… depends on `elixir-phoenix`". Inline `--plugin-dir plugins/elixir-phoenix` registers under the manifest name `phx`, so the dependency is unsatisfiable and CC **silently drops the plugin**. A dependency-free copy (`$S/e2e/plugin-copy-campfire/rewrite`, only `dependencies` removed) loads 5 commands + 7 agents (`smoke-init-copy.jsonl`) and was used for both runs. The copy was taken at 11:33 local; `$S/e2e/plugin-copy-campfire/diff-vs-repo.txt` records 42 files that changed in the live tree during the run; `elixir-way/references/app-shapes.md` (added 11:35) was absent from the copy (defect 8).

**Environment contamination.** Oliver's global `~/.claude/CLAUDE.md` ("Default every Agent call to `model: "opus"`") is read by the headless session, so the orchestrator passed `model: "opus"` on every `Agent` call, overriding the `model: sonnet` frontmatter of the four analysts and the phx consultants. The run cost is therefore not the plugin's own model policy. The same file's "fork" rule had no effect.

## 2. Rubric score

| Dimension | Max | Score | Evidence (path → quote) | Deductions |
|---|---|---|---|---|
| Goals and purposes | 20 | **17** | `analysis/features.md`: 28 `F-` capabilities, each with Goal / Invariants (source anchors) / Acceptance probes incl. negatives, e.g. F-08 "D cannot subscribe to R's message stream even with a signed stream name harvested earlier (`room_messages_channel_test.rb:28`)"; 10 actors; 20 triage questions. `analysis/mechanisms.md`: 69 mechanisms with purpose tagged observed/inferred/documented, "High-Risk Mechanisms", "Implicit Framework Behavior (the port must re-provide)" (15 items). Hidden reasons explained: refresh endpoint "compensate non-durable delivery" (M-32), presence counters "no unread/push while looking + shared store across Puma" (M-28), Redis split into roles R-20..R-25 | −2 all 20 triage items default `preserve` including stored-XSS T-03 (flagged, not decided); −1 coverage gaps admitted: "~60 Stimulus controllers and most of the 89 views/helpers were not fully audited" |
| Compatibility and migration | 25 | **21** | ADR-000: "Cutover = Replacement" (oracle Mode A), 57 contracts in a kept table with surface/consumers/witness, Data/Identity/Clients sections; rollback "the pinned Rails image must also still boot on a database the port has written… no destructive schema change… FTS stays maintained by app code"; `divergences.md`: 19 `DV-` rows with legacy/new/reason/consumers/ADR/ledger/approval `pending`; ADR-004 two ledgers (`ecto_schema_migrations` vs Rails' `schema_migrations`); ADR-010 "Rails reads port-minted `session_token` after rollback"; ADR-011 "Never decode Marshal" | −1 rollback window "has no end date while ADR-000 is ASSUMED" (oracle: rollback needs a time boundary; left open rather than defaulted); −1 ADR-000 Kept table lists C-21 "keep" while ADR-010/DV-06 change it and ADR-000 is not amended; −1 queue transition reduced to "nothing to drain" on an ASSUMED premise (bundled non-persistent Redis; "external `REDIS_URL` users unknown"); −1 presence columns stop being written during the open rollback window (DV-05, mitigated by `puma.rb:51` reset but still a Rails-visible change) |
| Elixir design | 20 | **18** | `architecture.md` §2 context map "drawn from invariants, not Rails models" with owns/invariants/public functions/emits/enqueues per context; §8 process table with runtime reason, supervisor, restart, overload policy — "There is no GenServer in front of the database, no hand-rolled queue, and no process per room or user"; §3 "`Campfire.Repo` is the **only writer**: `pool_size: 1`, `default_transaction_mode: :immediate`" + read-only pool; ADR-005 one transaction per write intent, broadcasts after `{:ok, _}`; ADR-006 `Oban.Engines.Lite` on the writer, PG notifier "Erlang process groups, **not** PostgreSQL", crash-window analysis in DV-01/02/03; ADR-008 shim in one namespace with owner and deletion trigger | −1 encode-once dispatcher relies on phoenix_pubsub subscription `metadata:` marked `verify` (design hinges on an unconfirmed API); −1 ADR-016 picks Hammer's clock-aligned window (DV-10, up to 2× the limit) over a 40-line exact limiter for "framework default" reasons |
| Evidence and tradeoffs | 15 | **13** | Pinned SHA on every artifact; `status.md` tree fingerprint `455ff1ef81a4f46d`; ADR Alternatives sections (e.g. ADR-014 "New VAPID keys. Rejected: every user must re-enable notifications"); `architecture.md` "Claims: none… nothing has run"; `ledger.py stats`: `verified 0 of 151`, `evidence: not-run 151`; crypto "needs-vector"; `kb/data-compat.md` WORKSPACE CORRECTION with library-source citation `codec.ex:117` | −1 `architecture.md` §10 "verified on hex.pm on 2026-10-09" restates the KB heading as the run's own verification (no WebFetch in `--allowedTools`); −1 ADR validation sections cite "vectors 1, 4, 5…" by number from `consults/security-analyzer.md` without listing them, so the gate is not self-contained |
| Verification / handoff | 20 | **17** | `roadmap.md`: 19 slices, "28 of 28 `F-` capabilities and 151 of 151 ledger IDs appear exactly once"; slice 02 acceptance has negative (non-member D, foreign Origin, unauthenticated `/cable`), crash ("an injected FTS failure leaves no message, no body, no unread change, no job row and no broadcast"), privacy, and complete-request performance screens ("p95 post→broadcast at c16 and writer checkout queue time… This is a screen, not a claim"); slice 18 Rollback A/B incl. "the pinned image boots directly on the port-written DB"; slice 00 baseline "untouched upstream `90b330024dec`", concurrency 1/16/64; `plans/rewrite-00-foundation/`: `interview.md` IN_PROGRESS with 16 DECISION / 9 DEAD-END in `scratchpad.md`; "`/phx:plan` was **not** invoked: `--auto` never hands off while ADR-000 has an ASSUMED… decision" | −2 the handoff only exists because of the manual resume; the shipped flow leaves no ledger and `start`'s state table cannot route it (defect 2); −1 slice 01 fixtures depend on running the pinned Rails image "in an isolated sandbox" — necessary, but the roadmap gives no recipe (image build, seed script), so the first executable gate is under-specified |
| **Total** | **100** | **86** | | |

## 3. Hard-failure checklist (oracle §5)

| Hard failure | Hit? | Evidence |
|---|---|---|
| Silent data loss | No | Every loss is a named, pending divergence: DV-03 (jobs >10 min cancelled, "This includes jobs restored from a backup"), DV-05 (presence columns no longer written), DV-06 (one 422 for forms rendered by Rails before cutover). `architecture.md` §11: "After a rollback, `oban_jobs` is ignored by Rails, so pending jobs are lost (equal to legacy semantics)" |
| Implicit forced logout / storage breakage | No | ADR-000 Identity "No user is forced to log out"; ADR-010 mints `session_token` in Rails format "so a rollback to Rails keeps users logged in"; ADR-013 keeps Active Storage tables, key layout, signed blob URLs; ADR-014 keeps VAPID keys |
| Unauthorized room access | No | ADR-008: RoomMessages "verify the signed stream name, parse the room, check membership"; Turbo channel rejects `*:messages`; `{:sockets_revoked, _}` closes sockets; "Reconnect re-runs authentication and every subscription check" |
| Claiming Channels/LiveView understand Cable | No | ADR-008 Alternatives: "Phoenix Channels or LiveView on `/cable`. Impossible: different protocol." `architecture.md` §4: "Phoenix Channels and LiveView are not on `/cable` and do not understand this protocol" |
| Claiming SQLite supports multiple simultaneous writers | No | `architecture.md` §3 "only writer… `pool_size: 1`"; ADR-018 admin scripts via `bin/campfire rpc` so "no second writer can exist"; ADR-006 "Never two containers on one volume" |
| Claiming durable / exactly-once PubSub | No | `architecture.md` §4 "ephemeral and at-most-once; the catch-up is `GET /rooms/:id/refresh`"; ADR-008 "at-most-once, ephemeral" |
| Interpreting Oban PG as PostgreSQL | No | ADR-006 and `architecture.md` §5: "`Oban.Notifiers.PG`, which uses Erlang process groups, **not** PostgreSQL" |
| Claiming unexecuted tests / speculative findings verified | No (wording nit) | `ledger.py stats`: `verified 0 of 151`; "Claims: none"; "needs-vector". Nit: "verified on hex.pm on 2026-10-09" inherited from `kb/stacks/rails.md` (see score table) |
| Treating old evidence as proof for a new snapshot | No | SHA pinned everywhere; fingerprint in `status.md`; vectors "generated in the pinned image"; resume re-ran the inventory compare before skipping steps |

**Hard failures hit: 0.**

## 4. Review/verify matrix coverage (oracle §5)

| Contract | Covered? | Where | Gap |
|---|---|---|---|
| Scope and privacy | Yes | F-08 probes; ADR-008 per-subscription authorization; slice 02 "D's RoomMessages subscribe with a harvested signed name for R gets `reject_subscription`"; ADR-009 revocation after commit; slice 05 membership revoke | Reconnect-after-revoke test is stated (ADR-009) but not as a slice acceptance line |
| Mutations and permissions | Yes | ADR-021 "changeset rejects any type change of a direct room"; M-13 permission matrix; M-48 "generated permission matrix across all routes" (slice 16); slices 07/10 | Deactivated/banned actor attempts not enumerated per action |
| Auth / crypto | Yes | ADR-010 validation "valid, tampered, expired, wrong purpose, rotated key, short secret; HTTP and `/cable` agree"; ADR-011 wrong-purpose tests for every pair, disjoint-salt test, both directions; slice 01 reverse-direction harness | Vectors referenced by number only |
| Database mapping | Yes | ADR-003 (`RailsTime`, `Ecto.Enum` legacy values, NULL involvement); slice 01 corpus "usec = 0 and usec > 0… NULL involvement… boosts longer than 16"; C-02 byte round-trip; `architecture.md` open #14 probes | — |
| Transaction ownership | Yes | ADR-005 no HTTP/IO/render inside the writer txn; slice 02 injected FTS failure; slice 00 "the reader rejects writes"; `Repo.reader/0` returns the writer inside a transaction (scratchpad) | Caller-exception / invalid-binding probe not written |
| Message identity / history | Yes | M-04 `client_message_id` kept, "retried POST duplicates (kept)"; M-32 refresh 40+40 "no tombstones (kept)"; ADR-021 keyset `(created_at, id)` with DV-14 and "41 messages with identical `created_at`" test | — |
| Job durability | Yes | ADR-006 crash-window rows, Lifeline test "an `executing` webhook job ends `discarded`, with no POST", "Rollback test: a failed message transaction leaves no job"; DV-13 ban removal idempotent, batched | — |
| Queue transition | Partial | C-59 "queued legacy jobs not drained (Redis non-persistent)"; `architecture.md` §11; slice 08 witnesses | No "stop old enqueueing / overlap deployment" probe; premise ASSUMED |
| Cache isolation | Yes | ADR-017 DELETE; "Port the fragment keys into Cachex. Rejected: ports the cross-user leak"; only body-HTML cache keyed `{message_id, updated_at, filter_version}`, "never `{:error, _}`" | — |
| Rich-text safety | Yes | ADR-012 three-layer sanitizer parity, fail-soft kept; ADR-011 "a forged unsigned mention cannot notify a non-member"; "sanitizer fuzz corpus" | Expansion-heavy parser bounds (oracle's OOM finding) not addressed |
| Media / storage | Yes | ADR-013 MD5 before txn, variant digest reuse, "No direct-upload or disk `PUT` routes… negative route test", loader allow-list; slice 09 | Traversal-key / partial-upload probes not listed |
| Push / SSRF | Yes | ADR-014 pinned-IP delivery, 404/410 cleanup, "A legacy-created subscription receives a port-sent test notification in Chrome, Firefox and Safari"; ADR-015 surfguard vectors, "redirect to 127.0.0.1 rejected" | — |
| Bots / integrations | Yes | ADR-020 golden JSON fixtures, raw UTF-8 body, T-06/T-07 quirks kept; ADR-015 webhook "no Net.Guard" by documented design, 7 s timeouts | — |
| Presence / lifecycle | Yes | ADR-007 Registry, 60 s window, "entries die with their owner"; F-12 probes (two tabs, restart); DV-05 | Stale-TTL probe under process restart only via F-12 negative |
| Operations / rollback | Yes | ADR-018 `VACUUM INTO`, hooks, exit codes; slice 18 "`pre-backup` during a write burst → `PRAGMA integrity_check`", Rollback A/B, `find / -newer` C-52 | Stale WAL/SHM handling after restore not mentioned |
| Performance | Yes | `architecture.md` §12 P0–P4, "No speed claim exists until P4 evidence names both SHAs, the command, the result and the denominator"; slice 00 baseline hardware block | Numeric goal open (honest) |

15 of 15 rows covered, 2 partial (queue transition; parser resource bounds).

## 5. Steering-file handling

Not exercised by this scenario. TARGET was an empty workspace, and `inventory.py` scans steering globs (`AGENTS.md`, `.agents/skills/*/SKILL.md`, `migration.toml`, `plans/*.md` …) only in SOURCE and `--target`. The official port's steering files live one level above SOURCE (`campfire-bench/once-campfire-elixir/{AGENTS.md,.agents/skills/rails-port/SKILL.md,migration.toml}`) and were never in scope: `inventory.md` "Agent-steering files: none found", `charter.md` "Steering files: None found in SOURCE or TARGET", ADR-000 "Steering = Charter wins. No steering files were found". Iron Law 5 could not be tested positively; nothing was obeyed and the absence was reported, not fabricated. To test it, run with `--target ~/Projects/campfire-bench/once-campfire-elixir` (read-only) or add `--steering <dir>` (defect 7).

## 6. Comparison with the official port (oracle §4)

| Area | Official port (B/P) | This plan | Prevented? |
|---|---|---|---|
| Web stack | Plug.Router + Bandit, 2,235-line generated route table, no Phoenix | Phoenix 1.8 router/controllers/HEEx; route-parity table "generated from `config/routes.rb`" as test data (`kb/stacks/rails.md`: "Route parity is a test table, not a runtime emulator") | Yes |
| Persistence | Raw SQL through one owner process (B serialized all reads) | Ecto on `ecto_sqlite3`, writer `pool_size: 1` + read-only pool; "There is no GenServer in front of the database"; a DB-owning process is a recorded DEAD-END | Yes — single-reader bottleneck designed out, single-writer kept |
| Realtime | Hand-written Cable + mandatory Redis bridge inside one VM | Cable shim in one namespace over local PubSub; "Shim backed by Redis (once-campfire-elixir). Rejected: Redis is retired (C-59) and was on the hot path" (ADR-008); owner + deletion trigger | Yes |
| Jobs | Native consumer emitting Resque envelopes over Redis; post-commit enqueue gap | Oban Lite on the writer, job intents inside the domain transaction (ADR-005/006); DV-01/DV-02 crash windows | Yes |
| Marshal | Encoder for variant digests (justified) | Same: `ActiveStorage.VariationDigest` "Marshal **encoder** of the transformation hash only"; "Never decode Marshal" | Matches |
| Fragment cache | Protected ETS with Rails-derived keys; cross-user CSRF/host leak history | DELETE (ADR-017); body-HTML cache only after measurement, keyed without per-request data | Yes |
| Auth | Rails cookie/capability codecs in `auth.ex`/`rails.ex` | Same necessity, per-purpose modules, no "verify anything" function, CI greps against codecs outside `compat/` | Yes, better isolated |
| Rate limit | Failed open on Redis error | Hammer ETS, no external dependency (DV-10 records the window change) | Yes |

The plan states the oracle's headline: `architecture.md` §1 "Core contexts never see Turbo, Cable or Rails formats" — Phoenix is the internal architecture, Rails formats are an edge protocol with retirement conditions. Redis is split by role (R-20 cable pub/sub → PubSub, R-21 remote-connection control → `user:<id>` revocation, R-22 fragment cache → DELETE, R-23 rate-limit → Hammer, R-24 Resque → `oban_jobs`, R-25 Kredis → DELETE "zero call sites"). SQLite stays one writer. LiveView/Channels are never claimed to speak Cable.

## 7. Defects in the plugin (ranked by impact)

| # | Plugin file · section | Observed | Fix |
|---|---|---|---|
| 1 | `plugins/rewrite/.claude-plugin/plugin.json` · `dependencies` | `"dependencies": ["elixir-phoenix"]` is unsatisfiable when phx is loaded by `--plugin-dir` (manifest name `phx`); CC drops the plugin silently (`init` lists `rewrite cmds: []`). Same class as the `lab/plugin_eval` note about `claude plugin eval` | Declare the dependency by the name CC resolves (`phx`, matching `plugins/ecto` and `plugins/lv` as installed), or drop it and preflight `phx:*` presence inside `start`; add a smoke test that asserts `rewrite` commands appear in the `init` message of `claude -p --plugin-dir …` |
| 2 | `skills/architect/SKILL.md` · §4 Synthesize; `agents/elixir-way-architect.md` · outputs 1–4; `skills/start/SKILL.md` · state table | The single synthesis agent was spawned `run_in_background: true` (CC default), and headless `claude -p` kills background work 10 min after the last turn: run 1 ended with ADRs but no `ledger.md`/`architecture.md`, so `ledger.py check` fails and `start`'s row "ADR-000, no `architecture.md`" is the only route. The agent also wrote ADRs **before** `ledger.md` although the SKILL says it "writes `architecture.md` and `ledger.md` first" | In §4 spawn with `run_in_background: false` (nothing runs in parallel with it) and say why (headless ceiling); in the agent, make the write order binding (ledger.md → architecture.md → ADRs → divergences → decisions) so a kill leaves a checkable state; have `start --auto` detect `killed.system` / missing ledger and resume automatically |
| 3 | `skills/elixir-way/references/data-compat.md:37`, `sqlite-on-beam.md:102` | KB recommends `datetime_type: :text_datetime`; ecto_sqlite3 writes `%Y-%m-%d %H:%M:%S` without microseconds (`codec.ex:117`), so port rows would sort wrongly against Rails rows. The orchestrator caught it by reading library source and patched the workspace copy; a less careful run ships a data bug | Replace the advice with "custom Ecto type that dumps Rails' `.ffffff` text; never `:text_datetime` or `:iso8601` on legacy columns" (the run's ADR-003 wording) |
| 4 | `skills/architect/references/compatibility-bar.md` · `--auto` defaults; `skills/analyze/SKILL.md` · §Triage | `--auto` leaves the rollback window "no end date" and defaults every triage item to `preserve`, including security-tagged T-03 (raw custom CSS = stored XSS), T-04, T-06, T-07 — parity worship by default, only flagged in prose | Rollback: default to a bounded window ("until the first approved destructive DDL; one release cycle") and list it as an open decision; Triage: items tagged `security` default to UNDECIDED (blocking the slice) instead of `preserve` |
| 5 | `agents/elixir-way-architect.md` · self-check; `skills/architect/scripts/ledger.py` · `check` | ADR-000 Kept table says C-21 "keep" while ADR-010/DV-06 change it; ADR-000 was never amended, so the bar and the divergence ledger disagree | Add a check: every `DV-NN` whose "Kept / changed" is **changed** must cite a contract that appears in ADR-000 "Changed or Retired Contracts"; the agent self-check must amend ADR-000 or reclassify the DV |
| 6 | `skills/analyze/SKILL.md` · charter `--auto` defaults | The charter invented goals before analysis ("drop Redis/Resque/ActionCable", "must-keep integrations" guessed); ADR-000 then rightly kept the Cable wire via a shim, i.e. the charter default contradicted the bar it is meant to constrain | `--auto` charter goals must be limited to what the inventory shows (stack, deployable, datastores) and phrase mechanism retirements as questions for ADR-000, not goals |
| 7 | `skills/analyze/scripts/inventory.py` · `scan_steering`; `skills/start/SKILL.md` · arguments | Steering scan covers SOURCE and `--target` only; a fresh-target rewrite with steering files elsewhere (this scenario) silently reports "none found" | Add `--steering <dir>` (repeatable) to `start`/`analyze` and scan SOURCE's parent when SOURCE is a subdirectory named `reference`/`legacy` |
| 8 | `skills/analyze/SKILL.md` · KB copy step | References `kb/app-shapes.md`; absent from the plugin snapshot → `status.md` "kb incomplete"; architect classified the shape from the inventory. Timing artifact of concurrent editing, but it shows the KB file list is hardcoded | Derive the KB copy list from the `references/` directory and fail loudly (BLOCKED) if a file the SKILL names is missing |
| 9 | `agents/elixir-way-architect.md` · evidence rules; `skills/elixir-way/references/stacks/rails.md:154` | "Libraries (hex.pm, verified 2026-10-09)" in the KB was restated by the architect as the run's own verification | KB headings should say "verified by the plugin author on <date>"; add an agent rule "cite `kb/` for versions; never write 'verified' for a check this run did not perform" |
| 10 | Environment / observations (not plugin bugs) | (a) global CLAUDE.md forced `model: opus` on all 9 agents (cost redacted); (b) roadmap steps 2–4 were delegated to a `general-purpose` agent (skill allows it; CLAUDE.md pin rule says sonnet for such spawns); (c) 5 wasted Bash calls across runs from zsh `echo =====` ("===== not found"); (d) the orchestrator believes "the ledger check script only finds them under `architecture/`" — ledger.py does not look at those files at all, though the chosen paths match the plugin's contract | (b) `roadmap` SKILL: if delegation is allowed, say `model: "sonnet"`; (c) `echo ---` in any skill examples |

## 8. What worked

- **Resume path.** Run 2 re-ran the inventory compare, saw the same fingerprint, "skipped steps 2–3 and resumed at synthesis"; it reused ADR-001..010 and consults, added ADR-011..021, and finished `ledger.md` (151 rows, `ledger OK`), `architecture.md`, `decisions.md`, `divergences.md`, `roadmap.md` and the slice-00 seeds.
- **The orchestrator checked its workers.** Run 1's result text: fixed ADR-000's 403→429 slip (`block_banned_requests.rb:10`), caught the KB `:text_datetime` defect from ecto_sqlite3 source, replaced "Ecto writes Rails' `schema_migrations`" with the two-ledger design, and confirmed from `config/puma.rb:51` that Rails resets presence columns on boot before accepting the Registry.
- **`--auto` stopped at the right place.** `/phx:plan` not invoked; every slice `blocked`; seed Status IN_PROGRESS with the ASSUMED decisions named; `decisions.md` lists the three decisions most needing review.
- **Oracle alignment on every specific check**: Replacement mode, 57 contracts with witnesses, Redis split by role, one SQLite writer, Cable shim ≠ Channels/LiveView, Oban PG explained, PubSub ephemeral, no Marshal decode, no fragment cache, Thruster kept with a reason, process table with runtime reasons, no claims of verification.
- **Ledger discipline**: 151/151 IDs placed in exactly one slice, one UNDECIDED (M-69) with what it blocks, 19 divergences with consumers, `verified 0 of 151` reported rather than hidden.

## 9. Ledger tool output (final artifacts, `$S/e2e/ledger-check-final.txt`)

```
## check
ledger OK
exit=0
## stats
verified 0 of 151 ledger rows (retired 0, accepted risk 0, UNDECIDED 1)
verdicts: DELETE 12, KEEP 60, MAP 42, REPLACE 28, SHIM 8, UNDECIDED 1
implementation: pending 151
evidence: not-run 151
exit=0
```
