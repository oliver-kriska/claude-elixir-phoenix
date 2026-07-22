# Changelog

All notable changes to the Elixir/Phoenix Claude Code plugin.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Amp target drift pre-commit guard** — canonical changes under
  `plugins/elixir-phoenix/skills/` now trigger `make amp-skills-validate` and
  require regenerated `targets/amp/skills/` changes to be staged. CI retains
  the same drift check as the authoritative fallback. Contributors can run
  `make amp-skills-sync` to regenerate and verify the complete target in one
  command.

### Changed

- **Portable PR-review/full workflow overlays** — generated Codex, Pi, and
  OpenCode `phx-pr-review` now use available GitHub connectors or authenticated
  `gh`, preserve read-only triage and explicit mutation approval, and never infer
  replies or resolution. Generated `phx-full` now preserves user phase gates,
  bounded retries/cycles, explicit verification, read-only review, and compound
  completion through portable skill invocation or sequential same-session
  execution. Canonical Claude and frozen Amp output remain unchanged; other
  workflows are not claimed portable.

- **Portable plan/work workflow overlays** — generated Codex, Pi, and OpenCode
  `phx-plan` and `phx-work` skills now use scratchpad research checklists, plan
  checkboxes, and `progress.md` instead of Claude-only named agents, task APIs,
  question tools, hooks, or MCP identifiers. Optional native subagents and
  Tidewave retain complete same-session sequential fallbacks. Canonical Claude
  skills and the frozen Amp target are unchanged; this does not claim parity for
  other generated workflows.

- **Amp installation no longer requires cloning this repository** — the primary
  project-local and global instructions now install all 51 generated skills
  directly from the GitHub `targets/amp/skills` tree. Update instructions also
  clarify that Amp copies skills and requires an explicit `--overwrite` install.

### Fixed

- **Portable command rewriting now requires complete invocation tokens** — Amp,
  Codex, Pi, and OpenCode projections leave filesystem paths, URLs, uppercase
  names, underscored suffixes, and malformed namespace wildcards unchanged. Pi
  now emits native `/skill:*` syntax directly instead of passing through a
  path-like intermediate form.

## [2.14.3] - 2026-07-20

Patch release: document the `Repo.transaction/1` changeset error-handling
footgun in the `ecto-patterns` skill (issue #76, proposed by @ndrean).

### Added

- **`ecto-patterns`: `Repo.transaction/1` changeset error handling** — new
  reference section (and an anti-pattern row in the auto-loaded SKILL.md) on the
  bare-match footgun inside `Repo.transaction(fn -> ... end)`: `{:ok, _} =
  Repo.update(cs)` raises `MatchError` on an invalid changeset, which rolls back
  and **re-raises** (crashing the caller, e.g. a `500`) — it does *not* return
  `{:error, %MatchError{}}`. Documents the explicit `case` + `Repo.rollback/1`
  fix (single step) and the `with ... else` fix (multi-step), and points to
  `Repo.transact/1` / `Ecto.Multi` as the footgun-free forms. Verified
  empirically on Ecto 3.14. Thanks to @ndrean for the proposal (#76).

### Changed

### Fixed

## [2.14.2] - 2026-07-13

Patch release: extend the optional Codex reviewer to the autonomous full
loop (`/phx:full --codex`) and fix a false-skip in the `/phx:watch-pr --codex`
trigger gate surfaced in live use.

### Added

- **`/phx:full --codex`** — the Codex CLI joins the review panel on every
  review cycle of the autonomous full loop, parity with `/phx:review --codex`.
  The flag propagates through both review paths (inline `/phx:review` and the
  delegated `parallel-reviewer`, which now spawns `codex-reviewer` as a
  conditional cross-model track). Consensus findings (a Claude agent **and**
  codex) are marked HIGH CONFIDENCE. Requires the `codex` CLI; degrades to a
  SKIPPED note when absent — never fails the cycle. Users without codex are
  unaffected (flag-gated, no codex code paths without `--codex`).

### Changed

### Fixed

- **`/phx:watch-pr --codex` no longer skips the `@codex review` trigger based
  on the wrong signal** — the "already reviewed → don't post" gate is now
  strictly scoped to the connector bot (`chatgpt-codex-connector[bot]`)
  reacting to / reviewing the current head SHA. The repo's CI "Codex" check
  and local `codex exec` / `/phx:review --codex` / `/phx:codex-loop` runs are
  explicitly named as separate mechanisms that never satisfy the skip. With
  `--codex`, the default is now unambiguously to POST the trigger (the flag is
  that consent); skipping is the narrow exception.

## [2.14.1] - 2026-07-11

Patch release: stop the Tidewave detection hook from probing apps that never
opted into Tidewave (#72), and quote `argument-hint` frontmatter so skills
load on GitHub Copilot CLI 1.0.65+ (#71).

### Fixed

- **Tidewave detection no longer probes apps that don't use Tidewave** —
  `detect-tidewave.sh` fired a blind `POST http://localhost:4000/tidewave/mcp`
  on every session start, showing up as `[info] POST /tidewave/mcp` noise in
  any Phoenix app listening on :4000. The probe is now gated on `tidewave`
  appearing in `mix.exs`/`mix.lock` (umbrella `apps/*/mix.exs` included);
  non-Elixir and non-Tidewave projects exit silently (#72)
- **`argument-hint` frontmatter quoted in 9 skills** — unquoted values starting
  with `[` parse as a YAML flow sequence (array), not a string; GitHub Copilot
  CLI 1.0.65+ rejects the array shape so those skills silently failed to load
  there. Wrapped in double quotes — the safe form for both runtimes
  (#71, PR #70 by @thejesh23)

## [2.14.0] - 2026-07-10

Optional Codex external-reviewer integration (`/phx:review --codex`,
`/phx:codex-loop`, `/phx:watch-pr --codex`), plus a CC 2.1.206 compatibility
pass: make the `Stop` hook actually reach the user, clean up `StopFailure`,
refresh model docs for Sonnet 5, and document the subagent nesting-depth budget.

### Added

- **Codex integration (optional)** — use OpenAI Codex as an external reviewer
  when the codex CLI / Codex GitHub connector is available. Zero impact
  without it: every touchpoint is flag-gated and degrades gracefully.
  - `/phx:review --codex` — new `codex-reviewer` bridge agent (haiku) joins
    the review panel; issues flagged by both a Claude agent and codex are
    marked HIGH CONFIDENCE (cross-model consensus)
  - `/phx:codex-loop` — new skill: bounded review→fix→verify loop with the
    Codex CLI as external critic (default 3 rounds, `--auto`, Iron Law
    scrutiny on every finding)
  - `/phx:watch-pr --codex` — posts the `@codex review` trigger, watches
    reactions and reviews via new watcher events (`codex_ack`,
    `codex_review`, `codex_clean`, `codex_timeout`), and loops
    fix→re-request until codex + CI are clean (≤3 rounds). Skips the
    trigger when codex already auto-registered the PR on ready (bot 👀/👍
    on the PR body since the head commit — verified live); PR-level
    reactions are time-filtered so stale 👀/👍 from earlier rounds can't
    fire spurious events. Clean-pass bot COMMENTS ("Didn't find any major
    issues" + `Reviewed commit: <sha>`) classify as `codex_clean` instead
    of a generic `comment` event, and `Reviewed commit` sha comparison is
    the preferred freshness check (committer timestamps are client-set
    and can skew) — all from live-session analysis of 9 codex sessions
  - `/phx:init` Step 4b — managed `## Review guidelines` block for
    AGENTS.md: one Elixir rubric honored by BOTH the local CLI review and
    the Codex cloud reviewer (verified live; the CLI rejects prompt +
    diff-flag combinations, so AGENTS.md is the only injection point)
  - `pr-review` bot-triage reference: codex thread anatomy (P1/P2/P3
    badges, per-commit reviews, clean-pass semantics)
  - Design note: a `--codex-panel` mode (3 dimension-focused codex passes
    alongside the holistic review) was A/B-tested on 4 real branches and
    rejected — real misses did not outnumber false positives on fresh
    diffs, at 4× quota cost. The single holistic review + AGENTS.md
    rubric is the shipped path; the A/B harness lives on as contributor
    tooling (`.claude/skills/codex-ab/`)

### Changed

- **`Stop` hook (`check-pending-plans.sh`) now reaches the user.** A Stop hook's
  plain stdout goes to the debug log only (CC hooks ref), so the previous `echo`
  warnings were invisible in normal use. It now emits a JSON `systemMessage`
  (user-visible; Claude still stops), gated on the rare, session-created signals
  — running `background_tasks[]` / `session_crons[]` (a forgotten `mix phx.server`
  / scheduled job) — with pending plans + dirty tree folded in only as supporting
  context. Clean stops stay silent (no per-turn noise); pending plans and an
  uncommitted tree are already surfaced at `SessionStart`. Deliberately NOT
  `additionalContext`/`exit 2`, which would force Claude to continue every stop.
- **CC changelog audit advanced v2.1.145 → v2.1.206** (48 versions). CLAUDE.md +
  README agent-model note updated: the `sonnet` alias now resolves to Sonnet 5 (CC's
  default model since 2.1.197, 1M context). Hook-output contributor notes updated
  for Stop (`systemMessage` vs `additionalContext`) and StopFailure (output
  ignored). Verified the `Edit(*.ex)` / `Bash(*mix deps.*)` hook `if`-conditions
  remain correct after the 2.1.176/2.1.163 matching changes (`deps-audit-gate.sh`
  self-guards; `Edit(*.ts)` is the canonical documented form).

### Fixed

- **`StopFailure` hook cleanup** — CC ignores a StopFailure hook's exit code and
  output entirely, so `stop-failure-log.sh`'s trailing `exit 2` + stderr was a
  no-op that misled contributors into thinking it blocked/messaged. Removed; the
  scratchpad write (read by the next session's `check-resume.sh`) is the actual
  mechanism and is unchanged.
- **`/phx:brief` showed no briefing content** — with extended thinking
  enabled, the model composed each ★ Briefing section inside its (invisible)
  reasoning and went straight to the `AskUserQuestion` "Continue?" dialog, so
  the user saw only the continue prompts and never the brief itself. The
  skill and `briefing-guide.md` now require each section to be emitted as
  visible response text BEFORE the question (new Iron Law #7), and the
  question phrasing no longer implies the section was already shown. Same
  guard added to `/phx:intro`'s section presentation loop and
  `/phx:codex-loop`'s findings-triage step.

## [2.13.0] - 2026-07-03

Security-posture + deep-audit release: SkillSpector scanning with `SECURITY.md`,
a repo-wide audit (5 parallel audit agents cross-checked against 1,853 sessions)
that fixed the long-standing garbled resume banner, destructive-op blocker
bypasses, an issue-#33 recurrence, and stale docs throughout — plus
`planning-orchestrator` repurposed into a spawnable research sub-orchestrator.

### Added

- **Security posture / `SECURITY.md`** — all 50 skills + 25 agents scanned with
  [NVIDIA SkillSpector](https://github.com/NVIDIA/SkillSpector) (static, zero
  egress): 65/75 SAFE raw; after reviewed baselines 0 DO_NOT_INSTALL (gate
  passes; 6 CAUTION-tier remain documented). The 4 higher-scoring
  components are documented false positives (a static scanner flags
  safety-enforcing / security-auditing skills because they name dangerous
  patterns to forbid or detect them; e.g. a line that reads `NEVER bypass
  security checks for speed`). Ships `SECURITY.md` with line-by-line triage,
  a README "scanned with SkillSpector" badge, `lab/skillspector/scan.sh`
  (reproducible, CI-gated) + reviewed baselines, and a `make security` target
  wired into `make ci` (graceful skip when the binary is absent).

### Changed

- **`planning-orchestrator` repurposed as a research sub-orchestrator**
  (deep-audit 2026-07-03: 0 spawns across 1,853 sessions — nothing ever
  invoked it, and its interactive design — AskUserQuestion, Iron Law #1 STOP —
  cannot run in a subagent). Now a non-interactive agent that owns ONLY the
  research fan-out: Tidewave context, cache reuse, parallel specialists,
  context-supervisor compression, decision-council research; returns a ≤500-word
  digest and never writes plans or asks the user. `/phx:plan` step 5 gains the
  routing rule: 0–2 research agents → spawn directly, 3+ (broad multi-context
  feature) → spawn the orchestrator and read only its digest. Right-sized
  opus→sonnet (secondary orchestrator), 547→232 lines. Stale cross-references
  in `planning-workflow.md` and `tool-catalog.md` corrected.
- **SessionStart banner has a single owner** — removed the duplicate `echo`
  hook entry from hooks.json; `check-resume.sh` owns the no-plan banner and is
  now gated on `mix.exs` OR existing `.claude/plans/` (issue #55 class:
  non-Elixir projects no longer get the Elixir banner).
- **Skill naming consistency** — `freeze` → `phx:freeze` (self-referenced
  `/phx:freeze` 8× but wasn't namespaced), `ecto-constraint-debug` →
  `ecto:constraint-debug` (matches sibling `ecto:n1-check` and the command
  docs advertise).
- **`memory: project` agents allow Edit** (planning-orchestrator,
  phoenix-patterns-analyst) — current CC docs confirm memory auto-enables
  Read/Write/Edit for memory-file management; disallowing Edit conflicted.
- **`context-supervisor` sets `omitClaudeMd: true`** (report-only writer);
  the eval matcher's exemption list no longer misclassifies it as an
  orchestrator.

### Fixed

- **`check-resume.sh` garbled resume banner** — `grep -c ... || echo 0`
  double-prints zero on no-match (grep emits `0` AND exits 1), rendering
  `(0\n0 done)`; session evidence: 15,817 garbled renders across 436 session
  files. Same latent idiom fixed in `check-scratchpad.sh` (there it raised a
  bash arithmetic error).
- **`block-dangerous-ops.sh` bypasses** — `MIX_ENV=test mix ecto.reset`,
  `mix do ecto.drop`, `env MIX_ENV=prod mix release`, and multi-space variants
  slipped past the anchors while bare `mix ecto.reset` blocked. Regexes now
  tolerate env-var/`env` prefixes, `mix do`, comma task lists, and flexible
  whitespace; quoted-mention false positives still allowed. 15 new regression
  cases (56 total, all passing).
- **Issue #33 recurrence in research agents** — `hex-library-researcher`,
  `otp-advisor`, and `deep-bug-investigator` disallowed Write while their own
  bodies (and the planning flow) expect written findings files. Write restored;
  Edit stays blocked (dormant in sessions — the spawn path always asked for
  inline returns — but fixed before the new orchestrator wiring makes it live).
- **Deprecated `--detail` flag purged** — `plan/references/complexity-detail.md`,
  `full/references/execution-steps.md`, `init/references/injectable-template.md`,
  and `plan-template.md` still taught `--detail minimal|more|comprehensive`;
  all now use `--depth quick|standard|deep` (sessions showed users only ever
  passed `--depth`).
- **Stale docs counts and tables** — intro tutorial said 47 skills / 22 Iron
  Laws (actual 50 / 26, four spots); README "Agents (25)" table listed only 20
  (added ash-policy-reviewer, ash-query-optimizer, ash-resource-designer,
  hex-deps-triager, requirements-verifier); web-researcher listed as sonnet
  (actual haiku); banner Iron Law stat 25→26; "40 skills + 20 agents" wording
  purged from Makefile, CLAUDE.md, run_eval.sh, and contributor docs; `make ci`
  descriptions now include the `validate` + `security` stages.
- **SECURITY.md overclaim** — "75/75 SAFE after baselines" corrected to the
  accurate "0 DO_NOT_INSTALL after reviewed baselines (gate passes; 6
  CAUTION-tier documented)"; same phrasing fixed in README and this changelog.
- **Eval trigger-cache drift** — pruned 6 ghost caches for deleted skills
  (autoresearch, xray-*), added the missing `mix-compression` trigger run
  (100% accuracy); behavioral coverage is now a true 50/50 instead of a
  reported 55 with a silent gap.
- **Path-form violations** — bare `references/` → `${CLAUDE_SKILL_DIR}/references/`
  in help, narrow-bare-rescue, mix-compression, deps-audit, deps-vet; compound's
  cross-skill path → `${CLAUDE_PLUGIN_ROOT}/skills/compound-docs/references/`.
- **CLAUDE.md hook docs drift** — documented the four live-but-undocumented
  hooks (`deps-audit-gate.sh`, `freeze-gate.sh`, `detect-ash.sh`,
  `route-intent.sh`/UserPromptSubmit) and added the docs-drift note that
  current Claude Code ignores `permissionMode` on plugin subagents (field kept
  for back-compat). `workflow-orchestrator` now suggests `/phx:learn-from-fix`
  (was nonexistent `/phx:learn`). Missing `effort:` added to help, permissions,
  and the three contributor agents; contributor `phoenix-project-analyzer`
  moved off `permissionMode: plan` and dropped the unrecognized `LS` tool.
- **`permissions` SkillSpector baseline refreshed** — the frontmatter edit
  shifted finding fingerprints; hashes updated with triage reasons preserved.

## [2.12.0] - 2026-06-16

Workflow-completion release driven by 400-session analysis: three new skills
(`/phx:recall`, `/phx:deps-update`, `/phx:watch-pr`), `/phx:pr-review` v2 that
closes the review loop (fetch → fix → reply → resolve), a `route-intent.sh`
UserPromptSubmit hook replacing ~0%-firing CLAUDE.md prose routing, four new
Iron Laws (#23–#26), and an eval-hardening pass that backfilled the
AskUserQuestion 4-option check, cross-file consistency tests, and untracked-file
detection. Law count 22 → 26.

### Added

- **Iron Law #26 — Comments aren't commit messages** (session analysis found
  Oliver asking "remove unnecessary comments" on essentially every PR, 8+
  sessions clustered June 2026). A change's reasoning — the bug, what it
  replaces, the task — belongs in the commit/PR/squash, which git persists; not
  in code comments. No issue-reference tags inline (`# ENA-1234`). Keep only
  durable intrinsic facts a future reader needs regardless of history:
  footguns, invariants, library quirks. Wired into CLAUDE.md, the
  `inject-iron-laws.sh` SubagentStart hook (code-writing subagents inherit it),
  the `iron-law-judge` agent as detection `#19` (so `/phx:review` flags ticket
  tags, change-narration, and what-comments), and the `init` injectable
  template. Stops the comments being added during `/phx:work`/`/phx:quick`
  rather than stripping them at PR time. Law count 25 → 26.
- **UserPromptSubmit routing hook (`route-intent.sh`)** — injects one-line `/phx:`
  suggestions directly into Claude's context for three high-signal intents: GitHub
  PR URLs / review-feedback phrasing → `/phx:pr-review`, Tidewave
  `<context name="current-page">` blocks → `/phx:investigate`, Elixir stack-trace
  pastes → `/phx:investigate`. Replaces CLAUDE.md prose routing rules measured at
  ~0% firing rate across 400 sessions. One suggestion per category per session,
  silent on explicit slash commands, gated on `mix.exs`, always exits 0
  (UserPromptSubmit exit 2 would erase the user's prompt).
- **`/phx:recall` — session and history archaeology** (git-archaeology sessions
  ran manual `git log`/`diff` pipelines with no plugin support). Three evidence
  layers, cheapest first: `.claude/solutions/` compound docs → git archaeology
  (`--grep`, `-S` pickaxe, `--follow`, `-L`) → ccrider MCP session search, gated
  with graceful degradation when the MCP is absent. ONE ccrider fetch = ONE
  subagent (3–15KB responses; writes a ≤30-line summary file). Every answer cites
  its evidence; clean misses are stated, then routed to `/phx:compound` so the
  next recall stops at layer 1. 100% trigger accuracy.
- **`/phx:deps-update` — generic dependency freshness workflow** (dependency
  maintenance was a recurring session pattern with no plugin support). Inventory
  via `mix hex.outdated` (exit 1 = normal "outdated" signal), changelog deltas via
  the built-in `mix hex.package diff <pkg> <v1>..<v2>` (no project-specific mix
  tasks), updates with coupled-group enforcement (Phoenix core, Ecto, Ash, Oban,
  telemetry families move together), breaking-change fixes, and PR splitting
  (patches bundled, minors by area, majors solo). Majors require an explicit
  `mix.exs` edit; `override: true` only when the per-package constraint table
  shows a transitive blocker. Hands off security to `/phx:deps-audit` (Mode B) and
  verification to `/phx:verify`. The only mutating deps skill — audit/vet stay
  read-only. 89% trigger accuracy.
- **`/phx:watch-pr` — token-conscious PR/CI watching** (replaces hand-rolled
  60-min foreground `sleep` loops observed in session analysis). A quiet
  background watcher (`scripts/watch-pr.sh`, Monitor-tool-first with
  `run_in_background` fallback) polls `gh pr view --json` in its own process and
  emits ONE line per genuinely-new event (review, comment, CI conclusion, merged/
  closed, watchdog, gh-failure) — raw JSON never enters Claude's context, and
  Claude takes zero turns while idle (no cache-TTL straddling). `--checks-only`
  delegates to `gh pr checks --watch --fail-fast` (exit code is the signal).
  Routes actionable reviews to `/phx:pr-review` and CI failures to
  `/phx:investigate`. 100% trigger accuracy on the new fixture.
- **`/phx:pr-review` v2 — closes the review loop** (fetch → fix → reply → resolve).
  The old skill drafted replies but used REST endpoints that expose neither thread
  IDs nor resolved status, so it could never resolve a thread or skip handled ones.
  v2 fetches threads via GraphQL `reviewThreads` (thread ID + `isResolved` +
  `isOutdated`, paginated), replies via REST to the thread root, resolves via
  `resolveReviewThread`, and is idempotent across review rounds — GitHub's
  `isResolved` is the state. New flags: `--bots-only` (triage CI bot passes —
  Copilot/Codex/CodeRabbit detected via `__typename == "Bot"`), `--no-resolve`.
  New Iron Laws: never resolve without a reply, never claim a fix without a shown
  diff, bot findings get the same scrutiny as humans. New references:
  `gh-commands.md` (3 comment surfaces, pagination, bot detection),
  `bot-triage.md` (batch flow + Elixir false-positive patterns).
- **Three new Iron Laws (#23–#25)** from the 400-session analysis, wired into
  `elixir-idioms`, `liveview-patterns`, the `/phx:init` template, the SubagentStart
  injection hook, and `iron-law-judge` detection patterns:
  - **#23** Mix tasks start only what they need — `Mix.Task.run("app.config")` +
    `Application.ensure_all_started/1`, never `Mix.Task.run("app.start")` (boots the
    full tree: endpoint binds the port, Oban starts consuming jobs). The
    `mix-tasks.md` reference previously taught the anti-pattern; now fixed.
  - **#24** LiveView handlers match `{:error, %Ecto.Changeset{}}` explicitly — bare
    `{:error, _}` silently swallows form validation errors.
  - **#25** Capture Gettext/CLDR locale before spawning Task/GenServer — locale is
    process-local; spawned processes reset to default.
- **Pre-migration safety section** in `ecto-patterns/references/migrations.md` —
  check duplicates (including soft-deleted rows) before unique indexes, with
  partial-index/data-fix/composite-key resolutions.
- **Tidewave reliability guards** in `tidewave-integration` — worktree/port
  verification (multi-worktree setups debug the wrong server), schema introspection
  before SQL, output-size caps, `browser_eval` server-side fallbacks, and a
  QA-walkthrough pattern for feature smoke tests.
- **Eval: AskUserQuestion 4-option-limit check** (`askuserquestion_option_limit`
  matcher) — the tool silently drops a 5th option; brainstorm shipped that way for
  months. Scans option lists after every AskUserQuestion mention (YAML `- label:`
  blocks and bullet/numbered runs), stops at headings, and skips sibling list items
  when the mention is itself inside a list. Backfilled into all 50 skill evals and
  the generator template; caught a real second instance in `/phx:plan`.
- **Eval: cross-file consistency tests** (`lab/eval/tests/test_consistency.py`) —
  two bug classes per-skill scoring can't see: references teaching anti-patterns
  their own Iron Laws ban (mix-tasks.md shipped the `app.start` pattern Iron Law
  #23 bans), and skill scripts using cwd-relative `.claude/` paths (the
  nested-state-dir bug class). The path lint caught a 4th live instance in
  `scripts/fetch-claude-docs.sh`.
- **`make eval` now sees untracked files** — brand-new skills/agents were invisible
  to the `git diff`-based changed-file detection until first commit;
  `git ls-files --others` is now merged into both detection paths.

### Changed

- **Workflow handoffs between phases** — `/phx:investigate` now ends with a routing
  step (quick fix vs `/phx:plan` vs `/phx:compound`); `/phx:review` passes the review
  file path to `/phx:plan` for follow-up plans; `/phx:work` suggests `/phx:compound`
  after non-obvious fixes and re-verifies stale plans from earlier sessions.
- **`/phx:full` deflects existing plan files** — description and a usage guard route
  `.claude/plans/*/plan.md` arguments to `/phx:work` instead of re-planning.
- **`intent-detection` hard guard** — skips entirely when the message starts with any
  slash command; no more routing suggestions on top of explicit commands.
- **`/phx:work` batches checkbox updates** — one edit pass when several tasks complete
  together, not one Edit call per checkbox.
- **`/phx:compound` write-block fallback** — outputs the solution doc inline and
  points at `/phx:permissions` instead of silently dropping knowledge;
  `/phx:permissions` now always recommends workflow-artifact write grants
  (`.claude/plans/`, `.claude/solutions/`, `.claude/reviews/`).
- **AskUserQuestion discipline in `brainstorm`/`triage`** — decisions only, concrete
  impact per option; fixed brainstorm's Decision Point exceeding the tool's 4-option
  limit (5 options meant one was always silently dropped).

- **`security-analyzer`** — new end-to-end flow checks from the 400-session analysis: IDOR
  via `handle_params` URL params, data-flow through multi-step transforms, failure-path
  consistency in `Ecto.Multi`/`with` chains, soft-delete leakage in authz lookups — all bug
  classes external review bots caught after plugin review passed.
- **`elixir-reviewer`** — failure-path review section (Multi/with error branches,
  short-circuit side effects, multi-step transforms, soft-delete filters), known
  false-positive traps (`nil[:key]` is nil-safe via Access), and diff-scoped reading rule
  to stop turn exhaustion on large PRs.
- **`verification-runner`** — compiles FIRST (turn 1 combines discovery + `mix compile`),
  maxTurns 10 → 15, earlier findings-file write; stops "compiling… let me check again"
  turn exhaustion observed on large PRs.
- **`parallel-reviewer` + `/phx:audit`** — rate-limit circuit breaker: when 2+ subagents
  fail with rate-limit/API errors, synthesize from existing outputs and tell the user to
  re-run after reset instead of dead-waiting on "continue".
- **`ecto-schema-designer`** — pre-UNIQUE-index migration safety check (duplicates +
  soft-deleted rows silently block production migrations).

### Fixed

- **Iron Law verifier is now blame-aware** — `iron-law-verifier.sh` scans only the content
  the current Edit/Write introduced (`new_string`/`content`), not the whole file.
  Pre-existing violations in untouched regions no longer force unrelated refactors.
- **`block-dangerous-ops.sh` fails open on script errors** — a corrupted hook file (e.g.
  merge-conflict markers) once blocked ALL Bash calls with no recovery; hooks.json now
  appends `|| exit 0` and the script documents the JSON-deny/exit-0 contract.
- **Stop hook warns about uncommitted feature-branch changes** — prevents the
  lost-work-after-rebase incident class observed in session analysis.
- **`liveview-architect` + `ecto-schema-designer` missing Write** — both agents still had
  the pre-v2.8.1 `disallowedTools: Write, ...` frontmatter and fell back to inline output
  when spawned as reviewers ("I only have Read, Grep, and Glob"). Write now allowed for
  their own findings file; Edit stays disallowed.
- **`web-researcher` could never write its output file** — research workers were asked to
  save findings but had Write disallowed; agents burned all turns on fetches then lost the
  output. Write allowed + reserve-last-turns-for-output guard.
- **`/phx:plan` post-plan AskUserQuestion exceeded the 4-option limit** — 5 options
  ("Review the plan" / "Adjust the plan" merged into one) meant one was always
  silently dropped. Fixed in the skill, `planning-orchestrator`, and both hook
  scripts that echo the list (`precompact-rules.sh`, `plan-stop-reminder.sh`).
- **`scripts/fetch-claude-docs.sh` wrote its cache relative to cwd** — anchored to
  `${CLAUDE_PROJECT_DIR:-$PWD}` like the other skill scripts.

## [2.11.0] - 2026-06-08

First-class Ash Framework support — an inline `ash-framework` skill (7 Iron
Laws, 100% trigger accuracy), three specialist agents, `mix.exs` auto-detection,
and Ash-aware output compression — plus the `/phx:freeze` scoped edit-lock and
per-skill eval + trigger coverage across all 47 skills.

### Added

- **`ash-framework` skill** — Iron Laws, generator workflow, and tiered research protocol
  (Tidewave → `usage_rules` → WebFetch hexdocs.pm) for Ash Framework projects. Iron Laws:
  domain code interfaces, actor-on-query placement, generators first, codegen after resource
  changes, actions over functions, never edit resource snapshots, no direct `Repo.*`.
- **`ash-resource-designer` agent** (sonnet) — designs Ash resources with actions, policies,
  relationships, and domain code interfaces. Outputs a design doc with generator commands and
  code interface stubs.
- **`ash-policy-reviewer` agent** (sonnet) — audits Ash policy coverage, `authorize?: false`
  bypass patterns, actor placement at call sites, and check module correctness.
- **`ash-query-optimizer` agent** (sonnet) — detects N+1 load patterns and surfaces the
  "Ash way" across 8 Iron Laws and 9 anti-patterns: load+`length`/`count` → aggregates,
  `count > 0` → `exists` aggregate, post-load `Enum.filter` → query-customized loads,
  derived `Map.put` → calculations, multi-read + `Enum.uniq_by` → `Ash.Query.combination_of`,
  direct `Repo.*` → Ash actions/aggregates, wide-resource reads → `Ash.Query.select`.
- **Ash auto-detection** — `detect-ash.sh` SessionStart hook announces the `ash-framework`
  skill (and `usage_rules` setup) when `:ash` appears in `mix.exs` or `use Ash.Resource`/
  `use Ash.Domain` appears in `lib/`. `priv/resource_snapshots/**` added to the CLAUDE.md
  auto-load table with a reminder that snapshots are owned by `mix ash.codegen`.
- **`mix-compression` Ash filters** — added `[filters.mix-ash-codegen]` and
  `[filters.mix-ash-migrate]` to `references/rtk-filters.toml`. Matches the same
  compression model as `mix-ecto-migrate`: happy-path short-circuits to one-liner,
  snapshot/migration file lists preserved verbatim, errors never stripped. Extends
  the documented 5-15% per-session token reduction to Ash workflows.
- **`freeze` skill + `freeze-gate.sh` hook** — scoped edit lock (`/phx:freeze`). Writes a
  `.claude/.freeze` sentinel (allow-list of path prefixes, or empty = freeze everything);
  a `PreToolUse` hook then denies `Edit`/`Write`/`NotebookEdit` outside the allow-list.
  Use for read-only investigation or to keep a refactor inside specific dirs.

### Changed

- **Ash callouts in existing skills** — `ecto-constraint-debug`, `liveview-patterns`,
  `phoenix-contexts`, `security`, and `testing` now route Ash projects to the
  `ash-framework` skill. CLAUDE.md "Ash Framework Detection" rewritten to load the skill
  and research via `usage_rules` rather than deferring to external docs.
- **`mix-compression` install docs** — `rtk test` → `rtk verify` CLI syntax.

### Fixed

## [2.10.6] - 2026-06-04

Patch: Elixir 1.20 type-system awareness across the verify/review path, plus
contributor tooling — a `/release` skill and single-sourced markdownlint ignores.

### Added

- **Elixir 1.20 type-system awareness.** Elixir v1.20 (2026-06-03) completed
  its first type-system milestone: the compiler now infers types and gradually
  type-checks every program **without annotations**, reporting dead code and
  *verified bugs* (guaranteed runtime failures) as `mix compile` warnings —
  built-in, no Dialyzer/PLT. The practical impact for the plugin: on 1.20+
  (OTP 27+), `mix compile --warnings-as-errors` — which `/phx:verify`,
  `/phx:work` checkpoints, and the "fix CI" pattern run everywhere — now
  **fails the build on type violations**. Changes:
  - New reference `skills/elixir-idioms/references/elixir-120-type-system.md`:
    the `dynamic()` mental model (refinable range, disjoint-only flagging),
    guard/clause/map inference, how to read & fix a violation, and a
    compiler-checker-vs-Dialyzer comparison table.
  - `skills/elixir-idioms/SKILL.md`: reference pointer added.
  - `skills/verify/SKILL.md` + `agents/verification-runner.md`: note that
    `--warnings-as-errors` now surfaces type violations at the compile step,
    and to suspect a newly-detected verified bug (not a regression) when a
    previously-green build fails after a 1.20 bump.
  - `agents/elixir-reviewer.md`: new "Type Checking (Compiler vs Dialyzer)"
    note — the built-in checker is the first line of type safety,
    complementary to (not redundant with) Dialyzer.
- **Protected-section invariant** in the autoresearch loop (contributor
  tooling, not distributed). The `## Iron Laws` section of every SKILL.md is
  now **append-only slow state**: the loop may add a law but a delete/reword
  forces REVERT. Enforced as a hard gate via `checks.sh` check #7 (backed by
  `lab/autoresearch/scripts/protected_sections.py`, which diffs the working
  tree against git HEAD, prefix-stripped so renumbering is allowed), plus a
  "Protected Sections" declaration in `lab/autoresearch/program.md`. Borrowed
  from SkillOpt (arXiv 2605.23904), which measured this fast/slow guarantee at
  ~22 points on SpreadsheetBench. A live test confirmed the necessity: the
  8-dimension scorer is *blind* to single-law deletion (composite and `safety`
  both stay 1.0, because the scorer is stateless and the `safety` dimension
  only checks section presence + min count) — so the old soft gate would have
  silently accepted dropping a security Iron Law. New tests:
  `lab/autoresearch/tests/test_protected_sections.py` (10 cases).
- **`/release` contributor skill** for cutting plugin releases — bumps
  `plugin.json`, finalizes the CHANGELOG, gates on `make ci`, tags `vX.Y.Z`,
  and runs `gh release create`. Encodes the Release/Versioning checklist and
  local gotchas as Iron Laws (`claude plugin tag` doesn't work for this
  marketplace layout; `plugin.json` == CHANGELOG heading == tag; confirm before
  the outward-facing publish; never force-push). `.claude/skills/release/` —
  contributor tooling, not distributed.

### Changed

- **markdownlint ignores single-sourced** via `.markdownlintignore` (gitignore
  syntax), de-duplicating the list across `package.json` and the Makefile and
  excluding untracked non-source dirs (`social/`, `.rtk/`) so `make ci` stays
  green on promo/cache content. Contributor tooling, not distributed.

## [2.10.5] - 2026-05-25

Patch: route audit subagents to declared-model specialists instead of
`general-purpose`, cutting Opus subagent volume per `/phx:audit` run.

### Changed

- `skills/audit/SKILL.md`: route 3 of 5 parallel audit subagents to
  declared-model plugin specialists instead of `general-purpose` (which
  inherits the parent session model, usually Opus). Architecture →
  `phoenix-patterns-analyst` (sonnet), Security → `security-analyzer`
  (opus), Test health → `testing-reviewer` (sonnet). Performance and
  Dependency tracks kept on `general-purpose` with TODO notes — no plugin
  specialist exists for project-wide perf or deps audit. Motivation: a
  JSONL analysis of 4,561 local sessions found 61.6% of Task/Agent
  invocations bypass the plugin via CC built-ins, materially explaining
  why Sonnet+Haiku combined are only ~7% of total token spend despite 18
  of 22 plugin agents declaring those models.

## [2.10.4] - 2026-05-21

Patch: fix force-push hook false-positive (issue #61) and the same
scan-past-separator class in the two sibling rules.

### Fixed

- `block-dangerous-ops.sh` (PreToolUse) — the force-push regex
  `git push.*(--force|-f)\b` matched `--force-with-lease` (in ERE,
  `\b` is a word boundary and the hyphen after `--force` is non-word,
  so the boundary triggered on the lease variant) AND scanned past
  shell command separators, so an unrelated `&& gh ... --force-with-lease`
  on the same line tripped the deny. The hook blocked the very command
  its `permissionDecisionReason` recommended as the safer alternative.
  Reported by @inou (issue #61) — hit on a Sprint 8 rebase cycle that
  stranded three rebased branches. New ERE anchors on start-of-line or
  shell separator (`;` `&` `|` `&&` `||`), keeps the scan inside the
  current command (`[^;|&]*`), and requires the flag to end at a word
  terminator (`([[:space:];&|]|$)`), so `--force-with-lease` is allowed
  while real `--force`/`-f` are still blocked. The same anchor fix is
  applied to the `mix ecto.(reset|drop)` and `MIX_ENV=prod mix` rules
  in the same file, which had the identical scan-past-separator
  failure mode (e.g. `echo "do not run mix ecto.reset" && mix test`
  used to be denied).
- New `plugins/elixir-phoenix/hooks/tests/block-dangerous-ops_test.sh`
  regression harness — 41 cases covering real force-push, the lease
  variant, scan-past-separator false positives, Elixir-only Ecto and
  MIX_ENV rules, and the `mix.exs`-gated cross-project bleed (#55).
  Run with `bash plugins/elixir-phoenix/hooks/tests/block-dangerous-ops_test.sh`.

## [2.10.3] - 2026-05-20

Patch release bundling two unreleased changes since v2.10.2: CC hook-API
adoption from PR #56 and the eval-framework multi-model trigger scorer.

### Added

- `check-pending-plans.sh` (Stop hook) now surfaces `background_tasks[]`
  and `session_crons[]` from hook input as terminal warnings — catches
  forgotten `mix phx.server`, `iex -S mix`, `mix watch` processes and
  pending `/schedule` jobs at session stop (CC 2.1.145+ field).
- `block-dangerous-ops.sh` (PreToolUse) now emits structured JSON
  output with `permissionDecision: "deny"`, a user-facing reason, and
  `hookSpecificOutput.additionalContext` containing the safer
  alternative. Thanks to the CC 2.1.110 fix that preserves
  additionalContext on blocked tool calls, the safer alternative now
  persists into Claude's next turn instead of being a one-shot stderr
  message.
- CLAUDE.md documents the new `type: "mcp_tool"` hook (CC 2.1.118+)
  with its SessionStart caveat — MCP servers may not be connected at
  SessionStart, so detection probes stay on direct HTTP / `curl`;
  reserve `mcp_tool` for PreToolUse / PostToolUse / Stop where the
  connection is live.
- Release checklist documents that `claude plugin tag` (CC 2.1.118+) does
  NOT work for this repo's marketplace layout (it expects
  `.claude-plugin/plugin.json` at the repo root, but our plugin lives at
  `plugins/elixir-phoenix/.claude-plugin/plugin.json`). Manual
  `git tag vX.Y.Z` remains the canonical path.

### Added (contributor)

- Multi-model trigger eval — `lab/eval/trigger_scorer.py` gained a
  `--model <alias_or_full_id>` flag (default `claude-haiku-4-5`,
  preserves all existing behavior). Aliases (`haiku`/`sonnet`/`opus`)
  canonicalize to full IDs so `--model haiku` and
  `--model claude-haiku-4-5` share one cache. Non-default models land
  in `lab/eval/triggers/results/by-model/{model}/`; per-result JSON
  records the `model` field so caches are self-describing.
- `lab/eval/compare_models.py` — N-way model comparator. Loads N
  `_aggregate.json` files via `--models alias,alias,…` or
  `--aggregates path…`, prints an ASCII table sorted by per-skill
  spread with `↕`/`⚠` markers at 10%/20% disagreement, plus an
  apples-to-apples intersection mean and pairwise delta when skill
  sets differ. `--format json` for machine consumption.
- `Makefile`: `MODEL=sonnet make eval-multimodel` (full per-model
  sweep), `MODELS=haiku,sonnet make eval-compare-models` (cached
  comparison). Foundation for verifying v3.0.0 multi-agent ports
  (Codex/OpenCode/Pi) on non-Claude routing judges.
  See issue #48, T1.3 Phase 1.

### Changed

- `block-dangerous-ops.sh` Elixir-specific branches (`mix ecto.reset`,
  `mix ecto.drop`, `MIX_ENV=prod`) now self-gate on `mix.exs` presence,
  matching the PR #55 cross-project-bleed pattern. The git force-push
  branch remains intentionally global.
- SessionStart welcome echo in `hooks.json` converted to `args: []`
  exec form (CC 2.1.139+) to eliminate nested shell quoting.
- `/phx:permissions` risk-classification flags that `Bash(find:*)`
  allow rules no longer auto-approve `find -exec` / `find -delete`
  (CC 2.1.113+ tightening).

## [2.10.2] - 2026-05-20

### Fixed

- `/phx:research`, `/phx:brainstorm`, `/phx:perf`, `/phx:pr-review` failing
  with "skill not listed" when invoked via slash command (issue #53,
  reported by @bigardone). Root cause: `disable-model-invocation: true`
  was still set on these four skills, triggering Claude Code bug
  [#26251](https://github.com/anthropics/claude-code/issues/26251) where
  the model refuses to invoke a skill via the Skill tool even when the
  user typed the slash command. Removing the flag — matching the
  precedent established in commit `f1fc494` (plan/review/investigate) —
  restores reliable invocation across native CC and third-party CC
  wrappers (Conductor, OpenCode, etc.), and lets the model see these
  skills in its inventory so workflow chains
  (`/phx:brainstorm → /phx:plan`, `intent-detection → /phx:research`)
  resolve correctly.

## [2.10.1] - 2026-05-20

Patch release fixing cross-project bleed when the plugin is enabled globally
(issue #55). All Elixir-specific hooks now self-gate on `mix.exs` presence —
they no-op cleanly in non-Elixir repos instead of firing Phoenix Iron Laws on
unrelated files. `security-reminder.sh` additionally tightens its filename
match to eliminate false positives on parent directory names and non-source
files.

### Fixed

- **Hooks now self-gate on `mix.exs` presence** — no Iron Laws, security
  reminders, subagent context injection, `.claude/` directory creation, or
  plan-STOP messages in non-Elixir projects when the plugin is enabled
  globally. Affects: `security-reminder.sh`, `log-progress.sh`,
  `inject-iron-laws.sh`, `precompact-rules.sh`, `setup-dirs.sh`,
  `plan-stop-reminder.sh`, `format-elixir.sh`, `iron-law-verifier.sh`,
  `debug-statement-warning.sh` (#55).
- **`security-reminder.sh` filename matching tightened** — basename-only
  match with word-boundary separators (`_.-`) and restricted to Elixir
  source extensions (`.ex/.exs/.heex/.eex/.leex`). Eliminates false
  positives like `tokenizer.cpp` (`token`), `/admin_panel/foo.ex` (parent
  dir `admin`), `docs/session-notes.md` (wrong extension), and the
  reporter's `session-state.md` case (#55).
- **`hooks.json` Edit|Write block** — added `if:` extension filter for
  `security-reminder.sh` as defense in depth alongside the script's
  self-gating.

### Changed

- README install section: noted project-scope enable as a tidiness
  preference for multi-stack developers (global enable is now safe).

## [2.10.0] - 2026-05-16

Adds a second, **framework-agnostic companion plugin** to the
`oliver-kriska` marketplace: `catchup`. It is a fully independent
plugin (own `.claude-plugin/plugin.json`, own version `0.1.0`, own
README) — installed separately and **not** coupled to Elixir/Phoenix.
The `elixir-phoenix` bump to 2.10.0 is the marketplace release vehicle
(single root CHANGELOG); the only `elixir-phoenix`-internal changes
this release are the README companion section and a `/phx:help`
routing row. Implements GitHub issue #47.

### Added

- **`catchup` plugin — `/catchup` return-from-absence briefing.**
  Standalone plugin at `plugins/catchup/`, second entry in
  `.claude-plugin/marketplace.json`. User-triggered skill
  (`disable-model-invocation`, slash-only). Fans out to GitHub (`gh`),
  git, Linear MCP, and Google Calendar MCP, then emits **one**
  prioritized brief in the 10-element Context Brief Framework scoped to
  a personal catch-up (Intent + ranked priorities, what moved, conflict
  risks, timeline). Flags: `--since` (incl. `last-session` mtime
  auto-detect), `--sources`, `--depth quick|standard|deep`, `--focus`.
  Writes `.claude/catchup/brief-<date>.md` + a ≤25-line inline summary.
- **Impact-on-your-scope analysis** (issue #47, @druyang). First-class
  brief block: intersects files moved on the default branch by others
  in the window with the reader's in-flight scope (open-PR files, local
  feature-branch diffs, working tree); classifies **direct** vs
  **adjacent** overlap; `--depth deep` reads incoming diffs for
  per-file *semantic* impact; `--focus impact` narrows the brief to
  only this. Answers "how do these changes affect *my* work", not just
  "what did I miss".
- **Graceful-degradation contract.** Sources are detected before
  query; a missing source becomes one honest line in the brief's
  Risks/assumptions block, never an error. `git log` is the
  always-available floor (valid minimum brief). No-Linear-MCP proxy:
  harvests `[A-Z]{2,}-\d+` ticket refs from commit/PR titles
  (labelled unverified). Privacy default is excerpt-only; Slack/Gmail
  are v2 opt-in. v2 surface (scheduling, `.claude/catchup.local.md`,
  cross-project rollup) is pinned in `references/config-schema.md` but
  not built.
- **Timezone-correct windows.** Calendar words (`friday`, `yesterday`,
  a date) resolve in the **user's local TZ** (the machine running
  `/catchup`), pivot through a single `SINCE_EPOCH`, then derive a UTC
  `SINCE_ISO`. Every source is compared on that one absolute instant,
  so colleagues in other timezones are included from *your* boundary
  ("since *my* Friday", not "since each author's local Friday"). Fixes
  a UTC-vs-local resolution bug (±14h). The brief's Timeline shows the
  anchor with its TZ abbrev.
- **Sonnet delegation (cost/speed).** The `/catchup` skill is now a
  thin orchestrator: it resolves the window + sources, then spawns a
  new **`catchup-runner` agent (`model: sonnet`, `effort: medium`)**
  for the `gh`/`git` fan-out, impact analysis, and brief assembly —
  so the caller's (often Opus) session no longer pays for the bulk
  I/O and summarization. MCP (Linear/Calendar) is still pulled in the
  caller's context (subagent MCP is unreliable) and passed to the
  agent. Skill `effort` lowered `high → medium`.
- **Smarter default window — `last-active`.** Replaces `last-session`
  as the default: takes the MAX of (newest Claude session mtime for
  this repo, your last own commit's committer-date, your last own
  PR/review activity). The latest footprint is the true "you were
  last here" instant; the brief records which signal won. New
  explicit values: `--since last-session` (sessions only),
  `--since last-commit` / `last-mine` (your git/PR only).
- **`/ketchup` 🍅 easter-egg alias.** A second slash-only skill
  (`skills/ketchup/`) that forwards verbatim to `/catchup` — same
  flags, same behavior, squeezier name.
- Verified end-to-end against a busy multi-developer production repo
  (Linear/Calendar MCP absent → degradation + proxy paths exercised;
  real direct file overlaps surfaced across local branches, a
  high-churn core module as the hotspot).

### Changed

- `elixir-phoenix` README: added a "Companion plugin: `catchup`"
  install section. `/phx:help`: added a "Returning after time off"
  routing row pointing to `/catchup`.
- **`catchup` is repo-scoped by default.** New `--scope repo|all`
  flag (default `repo`). Every GitHub signal — review-requested,
  notifications/mentions — is now filtered to the repo `/catchup` ran
  in: review-requests use `gh pr list --repo "$REPO"
  --search "review-requested:@me"` (was org-wide `gh search prs`),
  and pings use the repo-scoped `/repos/$REPO/notifications` endpoint
  (was cross-repo `/notifications?all=true`). `--scope all` re-enables
  cross-repo, but those hits are listed in a separate **Other repos**
  subsection and a Risks line, never folded into the repo's own lists.

### Fixed

- **`catchup` cross-repo leakage** (production finding). A brief run
  inside one repo listed *other* repos' review queue, notifications,
  and mentions (org-wide `gh search`/cross-repo `/notifications`),
  contradicting the expectation that a per-repo catch-up is scoped to
  that repo. Now repo-scoped by default; cross-repo is opt-in and
  segregated (see Changed → `--scope`).
- **`catchup-runner` turn budget** (production finding, ccrider-
  verified). A busy real repo hit the agent's `maxTurns` mid-assembly
  so it never returned the inline summary, forcing the (often Opus)
  caller to re-summarize — defeating the Sonnet cost delegation.
  `maxTurns 25 → 60`, added a "Tool economy" section (batch shell,
  write the brief before risking the budget), and a skill-side
  `SendMessage` fallback that finishes the summary cheaply in Sonnet
  instead of in the caller.
- **`catchup` correctness audit — 3 shell bugs.** (1) `git log
  --name-only` over a range under-counts files ~70% due to history
  simplification (real repo: 44 vs 140 ground truth — missed a landed
  migration and a 14-file conflict); replaced with per-commit
  `git diff-tree --no-commit-id --name-only -r`. (2) `awk -F'|'` on
  commit subjects corrupts fields when a subject contains `|`
  (e.g. `feat(a|b):`); switched to TAB (`%x09`) — macOS awk does not
  accept `-F'\x1f'`. (3) Unbounded local-branch scan firehosed on a
  400-branch repo; bounded to your own branches active in 60d, capped.
- **`catchup` cross-repo timestamp discipline** (`--scope all`
  production finding). On a narrow window a `--scope all` brief (1)
  printed GitHub's UTC `updatedAt` (`06:36:23Z`) with a local-TZ
  label (`06:36 CEST`, actually `08:36 CEST`), and (2) promoted a
  *pre-window* standing review request to "do first" by bundling it
  with an unrelated in-window issue update. `catchup-runner` +
  `source-adapters` now state two hard rules: judge each item on its
  *own* controlling timestamp ≥ `SINCE_EPOCH` (a related in-window
  object never drags a pre-window object into Top priorities — it
  goes to the "pre-window, for completeness" line), and convert `Z`
  → `LOCAL_TZ` before printing any clock time.
- **`catchup` anonymization.** Removed client repo/ticket identifiers
  from the distributed plugin and CHANGELOG; examples use generic
  `PROJ-####` / `lib/app*` placeholders.

## [2.9.0] - 2026-05-16

Ships the `/phx:deps-audit` + `/phx:deps-vet` Hex/Elixir supply-chain
suite. Built across five internal phases and two real-project dogfood
passes (two production apps) and consolidated into a single release —
none of the interim 2.10.0–2.12.0 bumps were ever tagged or shipped
(last release was v2.8.8).

### Added

- **`/phx:deps-audit` — Hex supply-chain audit.** 8-rule MVP catalogue
  per dependency tarball: bidi Unicode (Trojan Source
  CVE-2021-42574), `Code.eval_*`/`:erlang.apply` at module scope,
  compile-time `System.cmd`/`:os.cmd`/`Port.open`,
  `:erlang.binary_to_term/1` without `:safe`, new `:git`/`:path`
  deps, maintainer rotation (Hex API), large base64 blobs, and
  Levenshtein typosquats (≤2 + 1000× download delta). Modes: B
  (working vs HEAD, default), C (vs `--base <ref>`), A (`--preview` —
  locked vs Hex latest). Wraps `mix hex.audit` (always), `mix_audit`
  (GHSA) and `osv-scanner` (OSV.dev) when present — never
  auto-installs. Output: markdown triage table + JSON sidecar
  (`.claude/deps-audit/last-run.json`) + SARIF 2.1.0 (`--sarif`).
  Eval composite **1.000**.
- **Differential CVE pass.** `scripts/diff_cves.py` runs `mix_audit`
  against OLD and NEW `mix.lock` (tmpdir copy — never mutates the
  real lock) and reports `patched` / `introduced` / `still_exposed`.
  The 25-package virgil dogfood surfaced 4 CVEs patched in real time
  that the old single-state scan missed. GHSA freshness warning when
  the advisory cache is >24h old.
- **`/phx:deps-vet` — `hex_vet.exs` audit ledger.** cargo-vet-style
  trust ledger at project root; `:safe_to_deploy` / `:safe_to_run` /
  `:does_not_implement_crypto`. Vetted `{pkg,version}` pairs
  downgrade audit findings to INFO; lock-vs-ledger disagreement →
  lock wins. `--seed` imports a curated provenance baseline,
  `--check` cross-references `mix.lock`, `--list` renders the table.
- **PreToolUse gate.** Tiered `deps-audit-gate.sh` on
  `mix deps.{get,update,compile}` (Tier 0 lock-SHA cache → Tier 1
  bidi + new-dep → Tier 2 full). Tri-mode policy
  `false | :new_only | :strict | :full` (`:new_only` default).
  `PHX_SKIP_DEPS_AUDIT=1` escape hatch.
- **LLM triage (threshold-gated).** `hex-deps-triager` (sonnet)
  triages packages scoring >10 into
  `{confidence, verdict, rationale, fp_reasons[]}`;
  `context-supervisor` (haiku) consolidates so the parent context
  sees only the verdict. Advisory-only (ordering, not severity).
- **Precision layers (optional, soft deps).** Semgrep ruleset
  (`priv/semgrep/elixir-supply-chain.yaml`) and YARA rules
  (`priv/yara/hex-malware.yar`) — skipped cleanly if absent.
- **CI + lifecycle.** `--ci` non-interactive mode (exit 0/1/2) with
  GitHub/CircleCI/GitLab/Drone samples. Monthly cassette- and
  seed-regen workflows with an org-policy 403 artifact fallback. EEF
  CNA real-CVE corpus (decimal, bandit, phoenix, postgrex, cowlib) +
  synthetic fixtures; full smoke harness (`runner.sh` +
  `lib/detectors.sh` + `fixtures.d/`).
- **Solutions auto-feed.** After a BLOCK finding, prompts (never
  auto-writes) for `/phx:compound`; future audits pre-elevate
  matching snippets from `.claude/solutions/supply-chain/`.
- **Distributed imports v1.** `imports:` allow-list in `hex_vet.exs`
  (only the plugin seed in v1), 24h TTL, renderer attribution.
- Routing wired into `/phx:help` and `/phx:intro` cheat sheets;
  contributor `references/skill-checklist.md`.

### Changed

- **Cache architecture: persistent → per-run ephemeral.** No
  `.claude/deps-audit/cache/`; each run gets a fresh `mktemp -d`
  `${AUDIT_TMPDIR}` torn down via `trap … EXIT`. A "no
  vulnerabilities" verdict now reflects *today's* Hex + GHSA, never a
  stale snapshot. Removed `prune_cache()` and the planned
  `cache_signature.json`. Persistent files retained: `last-run.json`
  (gate sidecar) and `policy.exs` (user-owned). New
  `references/audit-tmpdir.md`. Migration: `rm -rf
  .claude/deps-audit/cache/` is safe.
- **Default full 8-rule scan** with streaming `[N/M] pkg ver`
  progress; `--quick` opts down to CVE + retirement (<10s). Removed
  the prompt that let users silently skip heuristics.
- Empty `hex_vet.exs` stub defaults to
  `block_on_unvetted: :new_only`.

### Fixed

- **CRITICAL — skill installed `mix_audit` when asked**, violating
  the non-mutating contract (added the dep to `mix.exs`/`mix.lock`).
  Iron Law #2 reworded to "NEVER install … **even if asked**";
  consent-resistant guidance added. A skill that mutates "because the
  user asked" is, to a security reviewer, indistinguishable from one
  that mutates on its own.
- **CRITICAL — gate policy parser silently downgraded enforcement.**
  Took the *first* regex match in `hex_vet.exs`, so a commented
  example (`# block_on_unvetted: false`) beat a real `:strict`
  setting — fail-open. Now strips comments, takes the last
  uncommented match (Elixir last-assignment-wins), warns on multiple
  keys.
- **Phase 5 hardening (security/test review):** the CVE-diff harness
  no longer silently SKIPs fixtures missing `setup.sh`/`expected.txt`;
  `_mix_audit_run_with_lock` unsets `MIX_*` env before running
  (defense-in-depth for Iron Law #2); a failed lock-copy now bubbles
  `return 2` instead of a false-green "no vulnerabilities".
- **Reference robustness (2026-05-16 virgil dogfood):**
  cross-tool-call `${AUDIT_TMPDIR}` handoff (`export`/functions/`trap
  EXIT` do not survive separate Bash tool calls) + the quoted-heredoc
  trap; `tarball-fetcher` baked `fetch.sh` (zsh has no `export -f`);
  `python3 + urllib` is now the canonical Hex API client (curl hit
  "Malformed input to a URL function"); mandatory `2>/dev/null` on
  `Code.eval_file("mix.lock")`; expected `mix deps.audit` recompile
  documented. **deps-vet:** Iron Law #6 — confirmation counts are
  computed, not estimated (`--seed` showed `26/4` vs real `23/7`);
  dropped the false "top-100" seed label (~30 entries) and reframed
  it as a pinned provenance baseline, not current-lock certification.

### Out of scope (deferred)

- Companion `phx_deps_vet` Hex package — follow-up (separate repo).
- Multi-org distributed audit imports — after the single-import
  trust-chain proves out.
- OTP-level CVE detection (SSH, inets, public_key) — needs an OTP
  version layer separate from Hex packages.
- Auto-refresh of the GHSA cache via PreToolUse hook.
- Regenerate `hex_vet_seed.exs` against current top-package versions
  (the bundled seed is Phoenix-1.7-era) — via the monthly
  `seed-regen.yml` CI or a dedicated reviewed pass.

## [2.8.9] - 2026-05-08

### Changed

- **Skill descriptions tightened** to reduce routing false positives:
  - `audit` — removed "security" from listed scope (security skill owns
    that signal); cleaner separation from focused security/boundaries asks.
  - `assigns-audit` — leads with "Inspect" instead of "Audit" verb to
    disambiguate from `audit` skill. Trigger accuracy 0.80 → 0.90.
  - `challenge` — added "OTP designs" to scope so OTP supervision tree
    challenges route correctly. Trigger accuracy 0.80 → 1.00.
  - `document` — clarified scope to @doc/@moduledoc only, not README
    or external docs. Trigger accuracy 0.80 → 1.00.
  - `liveview-patterns` — trigger prompts tightened with explicit
    "LiveView" / "phx-" markers. Trigger accuracy 0.625 → 0.75.
  - `n1-check` — added explicit "NOT for unrelated Ecto questions or
    wider database performance" guard. Trigger accuracy 0.70 → 0.90.
- **`help` Iron Law #5** — capitalized "NEVER block" / "DO NOT redirect"
  for the eval framework's safety matcher.

### Fixed

- **Eval set contamination** — stripped 209 routing hint annotations
  (em-dash separators, arrows, parentheticals) from 38 of 42 trigger
  test files. Per Oren et al. (ICLR 2024) "Proving Test Set Contamination
  in Black Box Language Models," these annotations leaked the correct
  routing decision to haiku inside the test prompt itself, inflating
  behavioral scores by rewarding hint-following over real routing
  competence. Average accuracy held at 91% post-strip; composition
  shifted to honest baseline. Contributor-only — no user impact except
  cleaner future tournament inputs.
- **README references** — wrapped a 270-char attribution line that
  was breaking `make eval-all` lint.

### Added (contributor)

- `lab/eval/triggers/strip_hints.py` — re-runnable script that strips
  hint annotations from trigger files. Idempotent, supports `--dry-run`
  and `--stats`. Regex tightened vs unmerged PR #24's original: requires
  leading whitespace before separators (preserves inline em-dash
  punctuation) and matches only the rightmost annotation per pass
  (safer on prompts with multiple separator layers).

## [2.8.8] - 2026-05-08

### Added

- **`/phx:mix-compression` skill** (issue #40, Angle 1) — installs
  [rtk](https://github.com/rtk-ai/rtk) filters that compress
  `mix test/credo/dialyzer/compile/deps.get/ecto.migrate` output before it
  reaches the transcript. Bundled `references/rtk-filters.toml` is the
  battle-tested filter set with embedded test fixtures: short-circuits
  happy paths to one-liners (`mix test: all pass`, `mix credo: clean`)
  while preserving compile errors, test failures, and stack traces. Critical
  signals (`** (CompileError)`, `== Compilation error in`, `FAILURES`,
  dialyzer warnings, file:line frames) are never stripped. Expected gain
  on mix-heavy sessions: 5-15% per-session token reduction. Skill walks
  through detection (`which rtk`), install (homebrew + `rtk init zsh`
  shell hook), seeding `.rtk/filters.toml`, and verification via
  `rtk test mix-test`. Pointer added to `/phx:permissions` "Related"
  section. Architecture note in skill body: this lives in a skill rather
  than a `PostToolUse` hook because rtk's subprocess-wrapping is the
  correct architectural layer — hook output cannot retroactively shrink
  what's already in the transcript.

- **Retention@K convergence metric** (issue #40, Angle 3) — new
  `lab/autoresearch/retention.py` module + `retention` CLI subcommand on
  `run-iteration.py`. Computes overlap of top-K skills (by trigger
  accuracy) between consecutive iterations and appends to
  `lab/autoresearch/retention.jsonl` (gitignored, append-only ledger).
  Defaults match the TACO paper (arXiv 2604.19572): `K=30`,
  `threshold=0.9`, `streak=2`. New `target --check-retention` flag
  short-circuits to `retention_converged` when the top-K ranking has
  stabilized for two consecutive iterations — autoresearch can stop
  running mutations when the skill pool stops reshuffling. Pure-function
  core (`retention_at_k`, `compute_topk_by_trigger`, `is_converged`)
  testable without any I/O fixtures. Dev-tooling only — zero impact on
  plugin users.

### Notes

- **Issue #40 Angle 2 deferred** — evolving `compound-docs` into a rule
  pool depends on Angle 1 telemetry justifying the investment. With rtk
  carrying compression at the subprocess layer (and CC v2.1.121's
  `hookSpecificOutput.updatedToolOutput` opening a future hook path),
  there's no urgency to build a second compression layer in the plugin.
  Re-evaluate after a quarter of dogfooding rtk + Retention@K.

## [2.8.7] - 2026-05-08

### Changed

- **Iron Law #1 — SEO/dead-render exception** (issue #44) — `iron-law-judge`
  now uses 4-state detection instead of binary CRITICAL on any `Repo.*` in
  mount. Cache-backed disconnected branches (`Cache.*`, `:persistent_term`,
  ETS) are recognised as the canonical SEO/dead-render pattern and pass
  cleanly. Uncached `Repo.*` in the disconnected branch downgrades from
  BLOCKER to SUGGESTION with a "if SEO, prefer cache-backed" hint. Updated
  wording in `liveview-patterns` SKILL, `async-streams.md` reference (new
  "SEO Dead-Render Pattern" section), `liveview-architect`, root CLAUDE.md,
  `inject-iron-laws.sh`, and `intro/tutorial-content.md` so all surfaces
  stay coherent. Verified end-to-end: 6 synthetic LiveView fixtures
  classified correctly (1 CRITICAL, 4 CLEAN incl. cache-backed/persistent_term,
  1 SUGGESTION). Resolves the false-positive flagged by @javiercr.

## [2.8.6] - 2026-04-28

### Changed

- **CC changelog audit** — bumped tracked Claude Code version to **v2.1.121**
  (`.claude/cc-changelog/last-checked-version.txt`) and refreshed the audit
  notes in `memory/reference_cc_source_internals.md`. No BREAKING or
  DEPRECATION items affecting the plugin. Highlights for plugin authors:
  `PostToolUse` `hookSpecificOutput.updatedToolOutput` now works for all
  tools (previously MCP-only) — opens the door for `format-elixir.sh` /
  `error-critic.sh` to rewrite mix output instead of only appending hints;
  `--dangerously-skip-permissions` no longer prompts on writes to
  `.claude/skills/ | agents/ | commands/`, which directly unblocks
  autoresearch and skill-creator loops; `CLAUDE_CODE_FORK_SUBAGENT=1` now
  works in non-interactive `claude -p` sessions, enabling forked subagents
  in `lab/eval/` and `lab/autoresearch/` scripts; `${CLAUDE_EFFORT}` is
  now substituted inside skill content, opening up effort-driven skill
  branches that align with the plugin's existing `effort:` frontmatter
  convention; `claude ultrareview [target]` now exists as a non-interactive
  subcommand with `--json` output. Reliability fixes worth noting: MCP
  servers now auto-retry 3× on transient startup errors, the
  Esc-during-stdio-MCP regression from 2.1.105 is fixed, several memory
  leaks are closed, and `--resume` now skips corrupted transcript lines
  instead of crashing (relevant to session-scan / session-deep-dive).
  Adding `$schema` to `plugin.json` / `marketplace.json` is now supported
  by `claude plugin validate` but is deferred until the canonical schema
  URL is published.

## [2.8.5] - 2026-04-27

### Changed

- **CC changelog audit** — bumped tracked Claude Code version to **v2.1.119**
  (`.claude/cc-changelog/last-checked-version.txt`) and refreshed the audit
  notes in `memory/reference_cc_source_internals.md`. Highlights for plugin
  authors: `PostToolUse` / `PostToolUseFailure` hook inputs now include
  `duration_ms`; async `PostToolUse` hooks emitting no response no longer
  write empty session-transcript entries (our `log-progress.sh` benefits
  silently — no code change needed); skills invoked before auto-compaction
  no longer re-execute against the next user message; `--print` mode and
  `--agent <name>` now honor agent `tools:` / `disallowedTools:` and
  `permissionMode:` for built-in agents (relevant for future headless
  agent runs in `lab/eval/`). No BREAKING or DEPRECATION items affecting
  plugin code.

## [2.8.4] - 2026-04-24

### Added

- **`/narrow-bare-rescue` skill** — new user-invocable skill for auditing and
  narrowing bare `rescue _ ->` / `rescue e ->` clauses in Elixir to explicit
  exception-type lists so programmer bugs (`UndefinedFunctionError`,
  `KeyError`, typos) propagate instead of being silently swallowed. Motivated
  by the Erlang Secure Coding Guide rule **LNG-002** ("Do Not Use `catch`").
  Ships with:
  - `SKILL.md` — Iron Laws (5 rules) + 4-step workflow
    (find → taxonomy lookup → apply → verify)
  - `references/taxonomy.md` — verified exception sets for 16 work categories
    (JSON, Ecto + Postgres, Money/Decimal, File I/O, Req, ExAws, ExCmd, Regex,
    atoms-from-strings, Phoenix forms, Plug, Phoenix LiveView HEEx/MDEx,
    NimbleCSV, DOCX/PDF extraction, explicit `raise`, plus a
    "programmer-bug exceptions to EXCLUDE" table). Validated against
    Elixir 1.19 / OTP 28.
  - `references/patterns.md` — special patterns: `is_exception/1` replacement,
    Oban "log and reraise" (with `__STACKTRACE__`), ExCmd's
    `ExCmd.Stream.AbnormalExit`, module-attribute hoisting for ≥3 rescues
    sharing a taxonomy, partitioning ≥50-site cleanups into per-directory PR
    clusters, and the regression-prevention Credo check pattern.
  - `lab/eval/triggers/narrow-bare-rescue.json` — 10-prompt trigger test set.
  - Invocation: `/narrow-bare-rescue [file_path | directory | --all]`.
  - Eval: composite score 0.968 (structural), 80% trigger accuracy, 100%
    trigger precision.

## [2.8.3] - 2026-04-23

### Added

- **`/phx:review` cross-checks implementation against requirements**
  (requested by Thiago Ferrari Pimentel on Slack, 2026-04-23). The review
  now emits a `## Requirements Coverage` table with columns
  `# | Requirement | Status | Evidence`, classifying each stated
  requirement as MET / PARTIAL / UNMET / UNCLEAR. This formalizes the
  cross-check pattern already done manually in session `ba3f7890`
  (2026-04-17, a production repo) where the table was titled
  "Cross-check against Linear PROJ-8931 acceptance criteria".
- **Auto-detection of the requirements source** (no argument required).
  `/phx:review` now tries, in priority order:
  1. Explicit `$ARGUMENTS` (path to `.md`, `PROJ-8931`, or `#42`)
  2. Conversation context (recent `mcp__linear__get_issue` / `gh issue view`
     results are reused — no re-fetch)
  3. Git branch regex (`[A-Za-z][A-Za-z0-9_]+-\d+`, matching branches like
     `proj-8278-extraction-scaffolding`)
  4. Commit subjects since main (`[A-Z]+-\d+` or `#\d+`)
  5. Most recently modified `.claude/plans/*/plan.md` (extracts only
     `- [x]` completed items)
  6. None → emits `NOT AVAILABLE` with sources tried (never silent).
- **New `requirements-verifier` agent** (sonnet, read-only, `omitClaudeMd`).
  Extracts requirements from the source, Greps the diff for evidence,
  classifies each item. Spawned in parallel with other review agents
  when a source is detected.
- **New Usage**: `/phx:review PROJ-8931`, `/phx:review #42`,
  `/phx:review --no-requirements`.
- **New reference**: `skills/review/references/requirements-detection.md`
  documents sources, regexes, fetch commands, and failure handling.

### Changed

- `/phx:review` verdict now considers Requirements Coverage: any `UNMET`
  escalates to `REQUIRES CHANGES`; `PARTIAL` downgrades `PASS` →
  `PASS WITH WARNINGS`. `BLOCKED` (Iron Law violations) still takes
  precedence.
- Review template places the coverage block before per-severity findings
  — "did we deliver what we promised" is the user's first question.

### Fixed

- **`log-progress.sh` wrote entries to the wrong plan** (issue #38, bigardone).
  The hook picked the most recently modified `progress.md` across ALL plans via
  `ls -t | head -1`, so with more than one plan in `.claude/plans/` the
  `[HH:MM] Modified: <file>` lines landed in whichever plan had been touched
  last — often a completed plan, not the plan `/phx:work` was actually running.
  Bug has existed since the init commit (2026-02-13); surfaced once users
  accumulated parallel plans. The progress-file branch is removed entirely —
  the `/phx:work` skill already logs structured progress entries itself, so the
  hook-driven append was both redundant and structurally unsound (no reliable
  way to identify the active plan from inside a `PostToolUse` hook). The
  cross-project JSONL metrics branch is unchanged.

## [2.8.2] - 2026-04-17

### Changed

- **Tournament-refined skill descriptions** for `plan`, `liveview-patterns`, and
  `intent-detection`. Rewritten using concrete use-case phrases (billing, RBAC,
  Presence, `assign_async`, streams) instead of technical vocabulary. Matches the
  "users describe features, not mechanics" routing pattern observed in session
  analysis. Output from the first tournament run on skills with <75% trigger accuracy.
- **Reframed skill description 250-char target as plugin listing-budget discipline**
  — CC raised `MAX_LISTING_DESC_CHARS` from 250 to 1,536 in v2.1.105, but our
  target stays at 250. Rationale is no longer "CC hard cap"; it's "~8K skill-
  listing budget divided across ~40 skills ≈ 200 chars per description". Longer
  descriptions would crowd out other skills in the listing and hurt routing
  accuracy across the whole plugin. Updated `CLAUDE.md`, `lab/eval/matchers.py`,
  `lab/eval/scorer.py`, `lab/eval/generate_evals.py`, `lab/eval/evals/_template.json`,
  `lab/tournament/config.yaml`, `lab/tournament/prompts.py`, and
  `.claude/skills/cc-changelog/references/analysis-rules.md`. Eval threshold
  unchanged (still 250), so no skill scores should move.
- **`/phx:intro` tutorial** gains a "Playing Nicely With Claude Code Built-Ins"
  subsection covering auto mode + xhigh effort (Opus 4.7), `/focus`, recap
  feature, and `/less-permission-prompts` (all new in CC v2.1.108–2.1.111). The
  plugin's workflow commands pair with these, not replace them.

### Internal (contributor tooling — not distributed)

- **New `lab/tournament/` module** — pairwise LLM-judge tournaments on skill
  description variants, using held-out trigger prompts to pick winners once
  structural eval is saturated (composite = 1.000) but trigger accuracy lags
  (<75%). Includes config, prompts, LLM adapter, tournament core, pytest suite.
- **`make eval-tournament` target** + cached trigger-accuracy gate in
  `lab/eval/run_eval.sh` (reads `triggers/results/` JSON, fails if any skill
  <75%, points at `make eval-tournament`).
- **Autoresearch tournament mode** — `find_weakest` tournament mode + new
  `tournament` subcommand that gates on structural 1.000 and journals the result.
- **Held-out trigger test split** — trigger JSON files gain a `should_trigger_test`
  field so tournament rounds judge on prompts the training set hasn't seen.
- **Gitignore cleanup** — ignore `output/`, `raw/`, `scripts/imessage-state.json`,
  `lab/tournament/results/`, `.claude/research/`. Fixed `.claude/cc-changelog/changelog-cache.md`
  pattern (inline `# comment` on the same line made it part of the pattern, so
  the file was never actually ignored).

## [2.8.1] - 2026-04-11

### Fixed

- **`/phx:review` now actually writes findings files** — Review agents
  (`elixir-reviewer`, `testing-reviewer`, `iron-law-judge`, `security-analyzer`,
  `oban-specialist`, `deployment-validator`, `verification-runner`,
  `parallel-reviewer`) previously declared `disallowedTools: Write, Edit,
NotebookEdit` and could not write to disk. The skill told them to write
  findings to `.claude/plans/{slug}/reviews/{agent}.md`; the main context fell
  back to extracting from each agent's return message, producing the visible
  log line *"Agent didn't write the file. Let me read its output to extract
  findings."* Fixed by allowing `Write` (keeping `Edit` and `NotebookEdit`
  disallowed so source code stays protected), bumping `maxTurns` from 15 → 25
  for the six non-mechanical reviewers (burned on Read/Grep before writing on
  large diffs), and adding an explicit "write partial findings by turn ~12,
  refine later" instruction to each agent. Closes #33 — thanks @bigardone
  for the report.
- **`/phx:review` skill passes explicit `output_file` path to every agent** —
  Step 2 now includes a per-agent file mapping (`elixir.md`, `testing.md`,
  `iron-laws.md`, `security.md`, `oban.md`, `deploy.md`, `verification.md`) so
  the orchestrator can read findings deterministically instead of reparsing
  agent messages.
- **`/phx:review` skill Step 3 logs a scratchpad warning on missing output
  file** — When an agent completes but its expected findings file is missing
  (turn exhaustion, error, etc.), the skill now writes a timestamped warning
  to `.claude/plans/{slug}/scratchpad.md` and marks the extracted section as
  `⚠️ EXTRACTED FROM AGENT MESSAGE`, making the failure auditable instead of
  silent.
- **`parallel-reviewer` spawns real specialist agents instead of
  `general-purpose` impersonation** — Previously used
  `subagent_type: "general-purpose"` with "You are acting as the X agent"
  prompts as a workaround for specialists lacking `Write`. Now that real
  reviewers can write, `parallel-reviewer` uses `elixir-phoenix:elixir-reviewer`,
  `elixir-phoenix:security-analyzer`, `elixir-phoenix:testing-reviewer`, and
  `elixir-phoenix:verification-runner` directly — carrying their domain
  checklists, skills, and Iron Laws automatically.

### Changed

- **Agent checklist in `CLAUDE.md`** updated to reflect the new convention:
  review agents declare `disallowedTools: Edit, NotebookEdit` (not
  `Write, Edit, NotebookEdit`). Write is allowed for own findings file only;
  Edit blocks source code modification, upholding Review Iron Law #1.

## [2.8.0] - 2026-04-03

### Added

- **`/phx:brainstorm` — Adaptive requirements gathering** — New command skill
  implementing an interview-research-synthesis loop for ideation before planning.
  Asks context-aware questions one at a time across 6 dimensions (What, Why, Where,
  How, Edge cases, Scope), runs lightweight codebase scans between questions, and
  offers parallel research via diverge-evaluate-converge pattern. Produces
  `.claude/plans/{slug}/interview.md` that `/phx:plan` detects and consumes, skipping
  its own clarification phase. Inspired by Virgil EI, ALFA framework (2502.14860),
  MediQ (2406.00922), and LLM Discussion Framework (2405.06373). Closes #28 —
  thanks @bigardone for the feature request.
- **`/phx:plan` interview detection** — Plan skill now checks for brainstorm
  `interview.md` artifacts and skips clarification when found with `Status: COMPLETE`.
- **`/cc-changelog` contributor skill** — Automates Claude Code changelog auditing:
  fetches CC changelog from GitHub, extracts new entries since last check using semver
  comparison, and guides impact analysis against plugin components. Includes
  `fetch-cc-changelog.sh` script with caching and diff support.

### Fixed

- **xref cycle detection uses `--label compile`** — All 6 locations now use
  `mix xref graph --format cycles --label compile` instead of bare `--format cycles`.
  Prevents false positive HIGH-severity findings from benign runtime cycles caused by
  `verified_routes()` macro in standard Phoenix projects. Affected: `xref-analyzer` agent,
  `boundaries` skill, `audit` scoring, `architecture-checks`, `call-tracing` reference.
  Closes #30 — thanks @bigardone for the excellent bug report.
- **5 brainstorm issues from real-world session** — From first test session (gettext
  performance brainstorm): enforce formal Decision Points with mandatory AskUserQuestion,
  ask Scope within first 3-4 questions, improve plan handoff UX with exact copy-paste
  command, cap first research cycle at 2 agents (Iron Law #7), and track research
  iterations with soft limit after 3 cycles.

### Changed

- **`disableSkillShellExecution` resilience** — Converted executable bash fenced blocks
  to inline prose instructions across 18 skills (14 BROKEN, 4 DEGRADED). Skills now
  instruct Claude via prose ("Run `mix compile`", "Use Grep to search...") instead of
  ` ```bash ` blocks that CC may block when `disableSkillShellExecution` is enabled
  (CC v2.1.91). Tool-replaceable commands (`grep`, `cat`, `find`, `ls`) converted to
  Claude tool references (Grep, Read, Glob). Documentation/example blocks unchanged.
- **Removed `disableModelInvocation` from plan, review, investigate** — The flag
  blocked programmatic `Skill()` calls during workflow transitions (brainstorm→plan,
  work→review). Confirmed in 3+ sessions. Kept on brainstorm, research, pr-review,
  perf where unwanted auto-loading is a real risk.

## [2.7.0] - 2026-04-02

### Added

- **Comprehensive Oban Pro support** — Rewrote `oban-pro-basics.md` (80→358 lines)
  with accurate Pro.Worker APIs, args_schema, Workflows, Batches, Chunks, Relay,
  Smart Engine configuration, and Pro plugin migration guide.
- **Smart Engine gotchas** — Documented two production-validated gotchas: one partition
  limiter per queue constraint, and snooze rolling back attempt counter (caused 72k+
  orphaned jobs in real production incident).
- **Iron Law #7 (Oban)** — "SMART ENGINE: NEVER USE `attempt` TO LIMIT SNOOZES" added
  to SKILL.md, oban-specialist agent, and iron-law-judge detection rule #9b.
- **Pro Testing patterns** — Added Oban Pro Testing section to testing-patterns.md
  with `drain_jobs/1`, workflow testing, and version-check notes.
- **Smart Engine queue config** — Added Smart Engine and Pro Plugin Config sections
  to queue-config.md with global/local/rate limit examples.

### Changed

- **Replace deprecated `TaskOutput` with `Read`** — 5 orchestrator agents and 1 skill
  reference updated to use background agent notification + `Read` on output files instead
  of the deprecated `TaskOutput` tool (removed in CC v2.1.89).
- **`maxTurns` for all 20 agents** — Added turn limits to prevent runaway agents:
  `maxTurns: 10` for haiku agents, `maxTurns: 15` for sonnet/opus specialists.
  Previously only 5 orchestrators had limits.
- **Conditional skill auto-loading via `paths:`** — 6 reference skills now declare
  file patterns for automatic loading (CC v2.1.84): liveview-patterns (`*_live.ex`),
  ecto-patterns (`migrations/*.exs`), oban (`*_worker.ex`), security (`*auth*.ex`),
  testing (`*_test.exs`), deploy (`Dockerfile`, `fly.toml`). Addresses #1 gap from
  session analysis (zero skill auto-loading in 137 sessions).
- **`claude plugin validate` in CI** — Added `make validate` target that runs
  `claude plugin validate` for frontmatter + hooks.json schema checking.
- **Oban skill description** — Now mentions both `perform/1` (OSS) and `process/1` (Pro)
  for better routing when users work with Oban Pro workers.
- **Oban specialist agent** — Enhanced Pro-Specific Review checklist with partition
  constraint checks, snooze pattern detection, and new Pro Red Flags examples.
- **Iron law judge** — Added detection rule #9b for snooze + attempt guard infinite
  loop pattern in worker files (CRITICAL severity, DEFINITE confidence).

## [2.6.1] - 2026-04-01

### Added

- **Structured scratchpad** — `check-scratchpad.sh` auto-initializes template with
  Dead Ends, Decisions, Open Questions, Handoff sections. Highlights dead-end count
  on session resume. `precompact-rules.sh` injects Dead Ends into compaction context.
- **Source quality tiers in web-researcher** — T1-T5 tier classification for research
  output. Every source tagged with quality tier, synthesis notes source reliability.

### Changed

- **Hook `if` conditions** — PostToolUse hooks now use declarative `if` filters
  (e.g., `"if": "Edit(*.ex)"`) to skip non-Elixir files without spawning a shell.
  Split single `Edit|Write` matcher into three targeted groups (Edit, Write, Edit|Write).
  PostToolUseFailure hooks use `"if": "Bash(*mix*)"` to only fire on mix failures.
- **Async SessionStart hooks** — `detect-tidewave.sh` and `check-branch-freshness.sh`
  now run with `async: true`, reducing session start time by up to 32 seconds.
- **Skill descriptions optimized** — Rewrote 32 skill descriptions to fit within
  Claude Code's internal 250-character listing budget (80% were previously truncated).
- **Read-only agents get `omitClaudeMd: true`** — 16 of 20 agents that can't modify
  code now skip CLAUDE.md loading, reducing subagent context overhead.

### Fixed

- Stale command references: removed `/phx:autoresearch` from help/intro, fixed
  `/phx:learn` → `/phx:learn-from-fix` across 9 files.

### Removed

- **`verify-elixir.sh`** — Dead hook (was `exit 0` no-op). Compilation verification
  runs in `/phx:work` phase checkpoints.

## [2.6.0] - 2026-03-27

### Added

- **`/phx:help` command** — Interactive command advisor that recommends the right
  `/phx:` command based on user description or ambient context (git status, plans)
- **`/phx:permissions` skill** — Analyzes recent sessions, classifies Bash commands
  by risk (GREEN/YELLOW/RED), recommends safe additions to `settings.json`
- **`/phx:verify` project-aware discovery** — Reads `mix.exs` to detect installed
  tools (credo, dialyxir, sobelow, ex_check), adapts verification sequence.
  Uses composite aliases (`mix ci`, `mix precommit`) when available, falls back
  to individual steps if alias fails locally
- **8-dimension eval framework** (`lab/eval/`) — Deterministic scoring for skills
  (completeness, accuracy, conciseness, triggering, safety, clarity, specificity,
  behavioral) and agents (completeness, accuracy, conciseness, safety, consistency).
  24 Python matchers, per-skill eval definitions for all 40 skills + 20 agents
- **Behavioral trigger eval** — Haiku-based trigger accuracy testing (8 prompts per
  skill). Measures whether Claude routes user requests to the correct skill.
  Cost: ~$1.50 per full sweep. Baseline: 84% average accuracy
- **Autoresearch loop** (`lab/autoresearch/`) — Self-improving skill that proposes
  mutations, evaluates, keeps/reverts via git. Wrapper script (run-iteration.py),
  structural checks (checks.sh), JSONL journal with ASI failure metadata, ideas
  backlog. Proven: 20+ iterations, 100% win rate
- **Agent eval** (`lab/eval/agent_scorer.py`) — 5-dimension scoring for all 20
  agents. Checks tools validity, read-only enforcement, bypassPermissions, model/
  effort consistency. All 20 agents at perfect score
- **CI Quality Gate** — 5-job pipeline: markdown/YAML/JSON lint, Python lint (ruff),
  shell lint (shellcheck), security audits (npm audit, pip-audit), skill+agent eval.
  52 pytest tests for the eval framework
- **Makefile** — Primary command interface: `make eval`, `make test`, `make ci`,
  `make eval-fix` (auto-fix + suggest autoresearch). Language-agnostic entry point
- **`plugin-dev-workflow` local skill** — Auto-triggers when editing plugin files.
  Guides contributors through eval commands, CLI syntax, pre-commit checklist
- **Interesting findings log** — `lab/findings/interesting.jsonl` captures metrics,
  research insights, bugs, patterns during development. 45+ entries
- **Dependabot** for pip ecosystem + requirements.txt (PyYAML, pytest)
- **Staged evaluation** (from Hyperagents paper) — `/phx:autoresearch` loop runs
  cheap checks first (compile 5s), skips expensive checks (test 30s+) if cheap fail

### Changed

- **36 of 40 skill descriptions rewritten** — Added "Use when..." clauses per
  Anthropic trigger optimization guide. Domain keywords added, vague words removed.
  Behavioral sweep improved plan (0%→100% recall), quick (0%→100%), boundaries,
  document, liveview-patterns, pr-review, security
- **Iron Laws added** to 6 skills missing them (hexdocs-fetcher, learn-from-fix,
  quick, init, boundaries, verify)
- **Stale references fixed** — `/phx:learn` → `/phx:learn-from-fix` across 3 skills.
  YAML frontmatter fixed in perf and permissions (unquoted brackets)
- **Review Step 2 compressed** from 49 to 37 lines
- **Planning orchestrator** — Research cache reuse expanded with glob discovery,
  keyword grep, freshness gate (48h), agent skip mapping
- **deep-bug-investigator** — effort: high → medium (matches sonnet model)
- **`no_dangerous_patterns` matcher** — Skips Iron Laws, Red Flags, Detection,
  Checklist, Confidence Levels sections (false positive fixes for anti-pattern docs)
- **README** — Updated counts (40 skills, 20 agents), added contributing guide with
  eval commands, roadmap section
- **Permissions output format** — Fixed deprecated `Bash(name:*)` → `Bash(name *)`
  per Claude Code docs

### Fixed

- **`/phx:verify` alias fallback** — Discovery now validates aliases against
  `mix.lock` before using them. Falls back to individual steps if composite
  command fails (e.g., `mix check` when ex_check not installed locally)
- **`setup-dirs.sh`** — Added `.claude/research/` to SessionStart directory creation
- **`learn-from-fix` name mismatch** — Frontmatter corrected to match directory
- **CI yamllint** — Ignores `node_modules/` and `.claude/` directories
- **CI ruff** — Ignores E402 (imports after sys.path.insert are intentional)
- **Unused Python imports** — Cleaned across agent_scorer, generate_evals, matchers

## [2.5.0] - 2026-03-21

### Added

- **`effort` frontmatter on all 38 skills** — Skills now declare effort level
  (low/medium/high) per Claude Code v2.1.80. Mechanical skills (verify, quick,
  compound, brief) use `low`; reference skills (ecto-patterns, security) use
  `medium`; complex reasoning skills (plan, full, investigate, review) use `high`.
  Reduces token usage on simple tasks while preserving quality on complex ones
- **`effort` frontmatter on all 20 agents** — Agents declare effort matching
  their cognitive load. Haiku agents (context-supervisor, verification-runner,
  web-researcher, xref-analyzer) use `low`; sonnet specialists use `medium`;
  opus orchestrators and security-analyzer use `high`
- **`PostCompact` hook (`postcompact-verify.sh`)** — Verifies active plan state
  survived context compaction. Warns Claude to re-read plan and scratchpad files
  when unchecked tasks detected post-compaction (Claude Code v2.1.76)
- **`StopFailure` hook (`stop-failure-log.sh`)** — Logs API failures to plan
  scratchpad for resume detection. Next session's check-resume hook picks up
  the failure context and suggests `/phx:work --continue` (Claude Code v2.1.78)
- **Plugin `settings.json`** — Ships recommended defaults: `effort: medium`,
  `showTurnDuration: true`. Users inherit these unless overridden in their own
  settings (Claude Code v2.1.49)
- **`${CLAUDE_PLUGIN_DATA}` persistent storage** — setup-dirs creates
  `${CLAUDE_PLUGIN_DATA}/skill-metrics/` for cross-project metrics that survive
  plugin updates. log-progress writes edit events as JSONL for cross-project
  aggregation (Claude Code v2.1.78)
- **`${CLAUDE_SKILL_DIR}` variable in 30 skills** — Reference file paths now
  use `${CLAUDE_SKILL_DIR}/references/` instead of bare `references/`, making
  paths explicit and reliable across plugin cache locations (Claude Code v2.1.71)

### Changed

- **hooks.json** — Added PostCompact and StopFailure hook events (now 9 hook
  types total, up from 7)
- **setup-dirs.sh** — Creates persistent plugin data directory when
  `${CLAUDE_PLUGIN_DATA}` is available
- **log-progress.sh** — Writes cross-project edit metrics to JSONL in
  persistent plugin data directory
- **`/phx:permissions` skill** — Analyzes recent Claude Code sessions to identify
  frequently-approved Bash commands, classifies them by risk (GREEN/YELLOW/RED),
  and recommends safe additions to `settings.json`. Inspired by Intercom's
  permission analyzer pattern. Includes 4 Iron Laws, `--days` and `--dry-run`
  flags, and reference docs for risk classification and settings format

## [2.4.0] - 2026-03-19

### Fixed

- **Document: no-op pre-check** — `/phx:document` now checks `git diff`
  for new `.ex` files before running full audit. Prevents 35-message
  analysis sessions that conclude "PASS — nothing needed" (session bb0a0454)
- **Challenge: dedup enforcement** — Strengthened prior findings dedup
  to prevent "3 challenges to clear" problem where same critical issues
  re-appear across consecutive runs. Now MANDATORY with explicit SKIP
  for fixed issues and one-line PERSISTENT mentions
- **Investigate: no confirmatory subagents** — Added rule to avoid
  spawning parallel subagents when root cause already identified in
  main context (~80K tokens wasted in session c135330a)
- **Audit: lean agent output** — Added output efficiency rule to audit
  subagent prompts (report only issues, not clean checks)

- **Full: Stronger no-narration enforcement** — Post-PR validation (19
  sessions, 5 days) showed 30% of messages still had "Let me now..."
  preamble. Upgraded from soft suggestion to HARD rule with explicit
  prohibited phrases and self-correction instruction
- **Review agents: Verify before claiming** — Added mandatory rule to
  elixir-reviewer and oban-specialist: never claim library behavior
  without checking source/docs first. Prevents incorrect BLOCKER
  findings that inject wrong code (confirmed: session f0242cf5 had
  two agents independently make wrong Oban Pro snooze claim, causing
  revert + user correction cycle)

### Changed

- **Review: Conditional agent spawning** — Iron-law-judge now skipped when
  PostToolUse hooks already verified all files; verification-runner skipped
  when work phase passed all tests. Saves 80-150K tokens per review
  (validated across 56 sessions: iron-law-judge used 78K tokens for zero
  violations in R3 /phx:full; verification-runner was always redundant)
- **Review: Lightweight path** — For <200 lines changed, spawn only
  elixir-reviewer + security-analyzer. Saves 30-50K tokens per small review
- **Review: Diff-scoped agents** — All review agents now receive
  `git diff --name-only` with instruction to focus on NEW code only.
  Pre-existing issues get one-line mentions. Eliminates 25-50% of
  false positives from pre-existing code flagging
- **Iron-law-judge: Violations only** — Removed "Clean Checks" output
  section (was 62% of output = ~2,800 words of "checked and it's fine").
  Now outputs only violations with one summary line for clean checks
- **All review agents: No praise sections** — Removed "What's Good" from
  elixir-reviewer, "Good Practices Observed" from testing-reviewer, and
  "N/A" category listings from security-analyzer. These consumed 16-56%
  of output tokens for zero actionable value
- **Context-supervisor now mandatory for 4+ agents** — Previously
  optional, now required. Prevents 12-20K tokens of raw agent output
  flooding the parent context (never used in any of 6 review sessions)
- **Plan: Skip research from review** — New Iron Law #7: when planning
  from review/investigation output, skip research agents. The findings
  ARE the research. (56-session analysis: same finding discovered 3-4x
  across review→investigate→plan, wasting ~96K tokens)
- **Work: Scoped verification** — Per-task: compile only (format
  handled by hook). Per-phase: compile + scoped tests. Full suite
  only at final gate. Eliminates 40-50% of redundant verification runs
- **Full: Lean review + no narration** — Added Iron Laws #6 (skip
  redundant review agents) and #7 (no narration in autonomous mode).
  Execute tool calls directly without "Let me now..." preamble

### Added

- **Skill eval framework** (`evals/`) — 3-phase automated testing for plugin
  skills with structural assertions (16 matcher types, zero API cost) and
  behavioral tests (LLM-as-judge with synthetic Phoenix scenarios)
- **`/eval` command skill** — Run structural, behavioral, A/B, and regression
  evals from Claude Code sessions
- **4 synthetic test scenarios** — acme_shop (18 files, 4 bugs), demo_blog
  (10 files, 2 bugs), sample_crm (25 files, 3 bugs), tiny_api (6 files,
  greenfield)
- **9 structural assertion specs** — compound, plan, review, work, verify,
  quick, ecto-patterns, liveview-patterns, security
- **5 behavioral behavior specs** — plan, review, investigate, compound, work
- **eval-judge agent** — Sonnet-based read-only judge for behavioral scoring
- **Eval suite orchestrator** (`run_suite.py`) — baseline management, regression
  detection, A/B comparison, trend tracking
- **npm scripts**: `eval:structural`, `eval:structural:changed`, `eval:full`

## [2.3.1] - 2026-03-12

### Changed

- **Skill descriptions: full optimization pass** — Applied Skill Creator
  methodology (trigger eval queries + train/test optimization) to all 12
  auto-triggered reference skills. Average triggering accuracy improved from
  15.0/20 to 19.3/20 (+29%). Key techniques: replaced generic terms with
  specific API/file keywords, added negative boundaries to prevent skill
  overlap, used user vocabulary instead of meta-language. Biggest wins:
  intent-detection (+10), assigns-audit (+7), oban (+6), elixir-idioms (+5)

## [2.3.0] - 2026-03-11

### Added

- **Iron Law #22** — VERIFY BEFORE CLAIMING DONE: never say "should work"
  without running `mix compile && mix test` (inspired by Superpowers plugin)
- **PreToolUse `block-dangerous-ops.sh` hook** — blocks `mix ecto.reset/drop`,
  `git push --force`, and `MIX_ENV=prod` before execution
- **PostToolUse `debug-statement-warning.sh` hook** — warns about `IO.inspect`,
  `dbg()`, `IO.puts` left in production `.ex` files
- **Review conventions system** (`references/conventions.md`) — after review,
  offer to suppress accepted patterns or enforce new conventions via
  `.claude/conventions.md`. Review agents read conventions and skip suppressed
  patterns (inspired by Carmack Council plugin)
- **Pre-existing issue separation** — review findings on unchanged code marked
  PRE-EXISTING and excluded from verdict (inspired by iterative-engineering)

### Changed

- **Review system: dynamic reviewer selection** — analyze diff to select 3-5
  agents from pool instead of always spawning all 5. Always-on: elixir-reviewer,
  iron-law-judge, verification-runner. Conditional: security-analyzer,
  testing-reviewer, oban-specialist, deployment-validator
  (inspired by iterative-engineering)
- **Review system: anti-over-recommendation filter** — 5 noise-filtering
  questions applied to findings before writing review
  (inspired by Carmack Council)
- **Review system: mandatory summary table** — every review ends with
  at-a-glance `| # | Finding | Severity | Reviewer | File | New? |` table
- **Review system: lane discipline** — explicit overlap resolution rules
  between parallel review agents for consistent deduplication
- **Skill descriptions: CSO audit** — 4 skills (full, work, plan, compound)
  reworded to lead with trigger conditions instead of workflow summaries
  (inspired by Superpowers CSO discovery)
- **Skill descriptions: anti-trigger patterns** — ecto-patterns, security,
  liveview-patterns now include `DO NOT load for...` conditions
  (inspired by Anthropic Skills repo)

## [2.2.0] - 2026-03-11

### Fixed

- **PreCompact hook (`precompact-rules.sh`)** — Fixed JSON validation failure
  that broke context preservation across compaction. Claude Code's schema
  validation rejects `hookSpecificOutput` with `hookEventName: "PreCompact"`
  (only PreToolUse/PostToolUse/UserPromptSubmit are valid). Switched to
  top-level `systemMessage` field which is schema-valid for all hook types

### Changed

- **web-researcher agent** — Full rewrite as haiku fetch worker (was sonnet).
  Source-specific WebFetch extraction prompts (ElixirForum, HexDocs, GitHub,
  blogs) reduce token usage 30-50% per fetch. Parallel WebFetch calls in
  single response for 3-5x speedup. Removed unused tools (Read, Grep, Glob)
  and elixir-idioms skill preload (caused safety scanner false positives).
  Agent is now a focused data collector; synthesis stays with the caller
- **research skill (`/phx:research`)** — Added query decomposition (extracts
  2-4 focused queries from long user input instead of passing raw text to
  WebSearch), pre-flight cache check, and parallel worker spawning (1-3
  web-researcher agents per topic cluster). New Iron Law: never pass raw
  user input as WebSearch query. Removes duplicate searching (skill searches
  OR agent searches, not both)
- **planning-orchestrator** — Updated web-researcher spawn guidance: pass
  focused queries or pre-searched URLs, spawn multiple agents for multi-topic
  research
- **agent-selection reference** — Added web-researcher spawn rules (model,
  URL limits, summary size, parallel spawning)
- **research skill (`/phx:research`)** — Added Tidewave-first routing: when
  topic is about an existing dependency, uses `mcp__tidewave__get_docs`
  (version-exact, zero web tokens) before falling through to web search
- **planning-orchestrator** — Added Phase 1c research cache reuse: checks
  `.claude/research/` and `.claude/plans/*/research/` for existing research
  before spawning web-researcher agents (prevents duplicate web research
  across planning sessions)
- **intro tutorial** — Updated `/phx:research` description in cheat sheet
  to reflect parallel workers and Tidewave-first routing

### Added

- **PostToolUse iron-law-verifier.sh hook** — Programmatic code-content scanning for Iron Law
  violations after Edit/Write. Catches String.to_atom, :float for money, raw/1 with variables,
  implicit cross joins, bare GenServer.start_link, and assign_new misuse. Inspired by
  AutoHarness (Lou et al., 2026) "harness-as-action-verifier" pattern: code validates LLM
  output and feeds specific violation + line number back for targeted retry
- **PostToolUseFailure error-critic.sh hook** — Detects repeated mix command failures and
  escalates from generic hints (attempt 1) to structured critic analysis (attempt 3+).
  Tracks failure count per command, consolidates error history, and suggests /phx:investigate.
  Implements the Critic→Refiner pattern from AutoHarness: structured error consolidation
  before retry prevents debugging loops
- **harness-patterns.md reference** — New work skill reference documenting the critic-refiner
  pattern for error recovery, action verification hook architecture, and anti-patterns for
  unstructured retry loops

### Changed

- **fulltext-search.md** — Rewritten with generated columns (preferred over triggers),
  trigram similarity (pg_trgm), hybrid search with RRF, multi-language support.
  Based on [Search is Not Magic with PostgreSQL](https://www.codecon.sk/search-is-not-magic-with-postgresql)
- **oban-pro-basics.md** — Slimmed to essentials + official HexDocs links.
  Prevents stale static content; directs to upstream for latest API
- **5 skill descriptions improved** — `plan` (--existing mode), `research` (--library flag),
  `hexdocs-fetcher` (wrapper purpose), `examples` (workflow demos), `audit` (5 specific areas)
- **Official doc links added** to `otp-patterns.md`, `mix-tasks.md`, `elixir-118-features.md`,
  `oban-pro-basics.md`, `testing-patterns.md` — enables fresh doc fetching

### Fixed

- **`work` skill** — Added mandatory scratchpad read before implementing + clarify-ambiguous-tasks
  Iron Law. Addresses high correction rate (0.61) from skill-monitor data
- **`skill-monitor`** — Added skill-type weighting so analysis/check skills (verify, triage, perf,
  boundaries) use appropriate thresholds instead of universal 0.5 cutoff
- **`perf`, `boundaries`, `pr-review`** — Added "findings to plan" next-steps nudge so analysis
  results lead to actionable follow-up instead of getting lost
- **`full` skill** — Added missing Iron Laws section (5 rules: verification, cycle limits,
  state transitions, discover-first, agent output boundaries)
- **`audit` skill** — Trimmed from 192 to 154 lines (was over 185 hard limit)
- **`review` skill** — Trimmed from 190 to 169 lines (was over 185 hard limit)
- **`boundaries` skill** — Trimmed from 170 to 145 lines (was over 150 hard limit)
- **`compute-metrics.py`** — Fixed datetime.min tz-naive comparison crash in trends,
  fixed fromisoformat returning naive datetime for date-only strings

### Removed

- **3 unfinished deploy references** — `ci-templates.md`, `kubernetes-config.md`,
  `observability.md` (undocumented, incomplete, not double-checked)

## [2.1.0] - 2026-03-05

### Added

- **SubagentStart hook** — injects all 21 Iron Laws into every spawned subagent
  via `additionalContext` (fixes #1 session analysis finding: zero skill
  auto-loading in subagents)
- **PostToolUseFailure hook** — Elixir-specific debugging hints when mix
  compile/test/credo/ecto commands fail, injected via `additionalContext`
- **Skill effectiveness monitoring** (`/skill-monitor`) — per-skill metrics
  dashboard with action rate, friction, corrections tracking. Includes
  `skill-effectiveness-analyzer` agent for improvement recommendations
- **9 new reference files** — `otp-patterns.md`, `js-interop.md`,
  `ci-templates.md`, `with-and-pipes.md`, `scopes-auth.md`,
  `advanced-patterns.md`, `documentation-patterns.md`, `briefing-guide.md`,
  `execution-guide.md`
- Iron Laws sections added to skills: audit, document, investigate, research
- Changelog and semantic versioning

### Fixed

- **PostToolUse hooks broken for ~1 month** (CRITICAL) — `plan-stop-reminder`,
  `security-reminder`, `format-elixir` all wrote to stdout which is
  verbose-mode only. Now use stderr + exit 2 so Claude actually receives
  the messages
- **PreCompact rules never injected** — stdout has no context injection path
  for PreCompact. Rewritten to use JSON `hookSpecificOutput.additionalContext`
- **SessionStart hooks running on /compact** — split matchers so informational
  hooks (scratchpad, resume, branch freshness) only run on startup|resume
- **compute-metrics.py O(n^2) bug** — `messages.index()` replaced with
  `enumerate` for correct windowing and O(n) performance
- **compute-metrics.py post_test_runs always 0** — ccrider-format messages
  have empty tool input; added text-based detection fallback
- **compute-metrics.py backfill schema gap** — `backfill_from_v1` now includes
  `skill_effectiveness: {}` for consistent schema

### Changed

- All 38 skill descriptions enriched for better auto-loading triggers
  (e.g., assigns-audit now triggers on "memory leaks", "slow LiveView renders")
- Updated CLAUDE.md hooks section with all 6 hook events and output patterns
- Updated README with `/skill-monitor` in session analysis tools
- Updated `/phx:intro` tutorial hooks table with new hooks

## [2.0.0] - 2026-02-19

### Added

- Iron Law #21: never use `assign_new` for values refreshed every mount
- VERIFYING phase in `/phx:full` workflow (compile + format + credo + test
  between work and review)
- Behavioral rules in CLAUDE.md: auto-load patterns, skill loading by file
  type, Iron Laws enforcement protocol
- Elixir 1.18 deprecations reference, try/after patterns, mix tasks reference
- `/phx:brief` skill for interactive plan briefings with visual formatting
- `/docs-check` contributor tool for plugin compatibility validation
- Markdown linting with markdownlint + husky pre-commit hooks
- `learn-from-fix` rewritten to write to project memory (not plugin files)

### Changed

- Agent model tiers optimized for Sonnet 4.6: most specialists moved from
  opus to sonnet, haiku for mechanical tasks (verification, compression)
- Planning workflow improved: agent blocking, session handoff for 5+ task
  plans, research synthesis
- Review, verify, testing, and Tidewave skills enhanced
- Intro tutorial split into 6 sections (was 5) to prevent content truncation
- Session analysis migrated to v2 pipeline (scan/deep-dive/trends with
  JSONL append-only ledger)

### Fixed

- Challenge skill dedup and multiSelect support
- Parallel-reviewer and skill tool scoping permissions
- `permissionMode: bypassPermissions` applied to all 20 agents (was causing
  "Bash command permission check failed" in background agents)
- Project name leaks in skill content
- Stale counts and intro tutorial accuracy
- Template placeholder filtering in session extraction

## [1.0.0] - 2026-02-13

### Added

- Initial release
- 20 specialist agents (orchestrators, reviewers, analysts)
- 38 skills covering full development lifecycle
- 20 Iron Laws (LiveView, Ecto, Oban, Security, OTP, Elixir)
- Plan-Work-Review-Compound workflow cycle
- PostToolUse hooks: format check, security reminder, progress logging
- SessionStart hooks: directory setup, Tidewave detection
- Stop hook: warn on uncompleted plan tasks
- PreCompact hook: rule preservation across context compaction
- Tidewave MCP integration (auto-detected)
- Context supervisor pattern for multi-agent output compression
- Plan namespaces (`.claude/plans/{slug}/`)
- Compound knowledge system (`.claude/solutions/`)
