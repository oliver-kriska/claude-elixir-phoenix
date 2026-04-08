# Changelog

All notable changes to the Elixir/Phoenix Claude Code plugin.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`/phx:lfg` — Autonomous feature pipeline** — Strict sequential pipeline
  (plan -> work -> verify -> review -> compound -> done) that runs to completion
  without manual gates. Inspired by Compound Engineering's LFG workflow, adapted
  for Elixir/Phoenix with Iron Laws enforcement and `mix compile --warnings-as-errors`
  verification at every phase boundary. Best for clear, well-scoped features where
  discovery and replanning are not needed.
- **`/phx:slfg` — Swarm autonomous pipeline** — Same pipeline as LFG but uses
  swarm mode for parallel execution. Work phase launches parallel subagents for
  independent implementation units. Review and verify run concurrently in a parallel
  phase, followed by sequential autofix. Delivers faster for plans with independent
  task units.

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
  `` ```bash `` blocks that CC may block when `disableSkillShellExecution` is enabled
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
