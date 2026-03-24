# Changelog

All notable changes to the Elixir/Phoenix Claude Code plugin.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Planning orchestrator Phase 1c** — Expanded research cache reuse from 3 lines
  to actionable implementation steps: discover candidates via glob, relevance
  check via keyword grep, freshness gate (48h), agent skip mapping, and
  scratchpad logging. Prevents redundant web/hex agent spawns when prior
  `/phx:research` output exists

### Fixed

- **`setup-dirs.sh`** — Added `.claude/research/` to SessionStart directory
  creation so the research output directory exists before `/phx:research` runs

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
