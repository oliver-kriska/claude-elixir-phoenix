# Changelog

All notable changes to the Elixir/Phoenix Claude Code plugin.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
