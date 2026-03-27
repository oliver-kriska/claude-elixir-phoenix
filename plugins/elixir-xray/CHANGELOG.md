# Changelog

All notable changes to the Elixir X-Ray plugin.

## [0.9.0-beta] - 2026-03-23

### Added

- `/xray:compare` skill — compare scans to show resolved findings, new issues, severity changes
- `/xray:fix` skill — interactive menu to auto-implement findings (pick all, top N, category, or specific IDs)
- `/xray:scan --pr NUMBER` — PR-scoped scanning, 3 layers, ~2 min
- ROI scoring — `roi_score = (frequency × severity) / effort` in merged findings
- Root cause chain detection — code findings linked to git/PR symptoms
- Community patterns library — "How You Compare" context for findings
- Confidence reasoning per finding — explains why confidence is high/medium/low
- False positive rate notes in agent prompts — manages expectations
- Smart defaults by project size — <50 modules: 3-8 findings, 50-200: 5-15, 200+: 10-20
- Scan duration tracking in reports
- Layer error summaries in reports (explains skipped/failed layers)
- Dependency freshness check (mix hex.info comparison)
- PR reviewer quote extraction (actual comment text, not just themes)
- Script cache with `--fresh` flag (reuse <1hr old JSON data)
- PreCompact hook — recovery instructions if context compaction fires during scan
- Scan history saving for `/xray:compare`

### Changed

- `/xray:fix` now interactive by default (grouped menu with ROI scores)
- Merge-findings.py ALWAYS runs in deep mode (was bypassed)
- Session fetching capped at 3 sessions × 50 messages in deep mode (token budget)
- Orchestrator prompts use explicit labeled paths (no more EISDIR)
- Finding caps per layer: L1=15, L2=12, L3=18
- Report template includes: Top ROI, Root Cause Chains, How You Compare, Artifact Inventory, Layer Errors

### Fixed

- Token exhaustion on large projects with many sessions
- Orchestrator sub-agents getting directory instead of file paths
- Merge script bypassed in deep mode

## [2.0.2] - 2026-03-21

### Fixed

- JSON output capping in all 8 scripts to prevent "File content exceeds maximum" errors in sub-agents
- Optimized skill descriptions for better triggering accuracy

## [2.0.0] - 2026-03-21

### Added

- **Deep scan mode** (`/xray:scan --deep`) — 6 orchestrator agents spawn 20 specialist sub-agents
- **Quality gate** (`/xray:scan --gate measure/check`) — baseline ratcheting for CI integration
- **Temporal coupling analysis** — Jaccard co-change detection for hidden file dependencies
- **Hotspot scoring** — Tornhill-style composite risk (change frequency x complexity x bug ratio x trend)
- **Authorization audit** — scans all LiveView handle_event callbacks for missing auth checks
- **Feature flag detection** — finds FunWithFlags/LaunchDarkly/custom flag patterns
- **Soft-delete audit** — checks deleted_at schemas against unfiltered queries
- **Money field audit** — flags :float type on money-named fields
- **Error handling patterns** — counts raise vs {:error} vs Logger.error per context
- **Three-level deduplication** — title similarity, semantic linking, contradiction detection
- **Theme assignment** — groups findings by connected components for report organization
- **Detailed report template** — 60-100KB comprehensive per-theme analysis document
- 6 orchestrator agents (L1-L6) with inline sub-agent prompts and graceful degradation

### Changed

- Scan skill rewritten with --deep and --gate flags
- merge-findings.py enhanced with semantic linking, contradictions, themes
- analyze-code.py enhanced with 5 new analysis sections
- Setup hook creates L1-L6 subdirectories for deep scan

## [0.3.4] - 2026-03-20

### Fixed

- Session scorer message parsing for ccrider format
- Bash scripts use `set -u` only (no -e or pipefail) for graceful failure
- Filter bash-stdout/bash-stderr from session messages
- Skip messages >5000 chars (tool output dumps)

## [0.3.3] - 2026-03-20

### Changed

- Reduced permission prompts: all scripts in ONE Bash call, Bash budget max 2
- Merge script skippable if layer files readable directly
- Removed `which gh` Bash check (no Bash in Step 1)

## [0.3.2] - 2026-03-20

### Fixed

- Scan skill derives script path from base directory (not Glob which matches old cache versions)

## [0.3.1] - 2026-03-20

### Changed

- Scan skill rewritten (192 -> 130 lines) with behavioral reasoning
- All agent prompts: "Read ONLY this file" instruction strengthened
- Report template reference added with consistent structure

## [0.3.0] - 2026-03-20

### Added

- Existing Credo check cross-referencing in analyze-code.py
- Time-trending per git fix pattern (worsening/stable/improving)
- Report template with executive summary and impact estimates
- Project description from README in analyze-code.py output

### Changed

- Config analyzer checks both CLAUDE.md and AGENTS.md
- All 6 analysis agents: "read ONLY JSON, do NOT read project files"
- Finding count guidance: "5-15 findings, focus on highest impact"

## [0.2.0] - 2026-03-20

### Fixed

- PR analysis retry with exponential backoff (3 attempts)
- Session scorer robust ccrider format handling with debug logging
- Agents return text instead of writing files (orchestrator handles writing)
- Inline YAML array parsing in merge-findings.py

## [0.1.5] - 2026-03-20

### Fixed

- Script path resolution from skill base directory (not Glob)
- Removed `pipefail` from bash scripts

### Changed

- Agent Write tool added to analysis agents
- Version bump discipline for cache refresh

## [0.1.0] - 2026-03-20

### Added

- Initial release with 6-layer analysis (git, PRs, code, config, sessions, architecture)
- 7 analysis scripts (Python/Bash)
- 11 agents (6 analyzers + 5 generators)
- 4 skills (/xray:scan, /xray:apply, /xray:brief, /xray:intro)
- Finding schema with YAML frontmatter
- Scoring methodology (severity x effort x automatable x confidence)
