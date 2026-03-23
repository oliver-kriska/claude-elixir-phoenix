# Elixir Inspector Plugin

Analyze Elixir/Phoenix codebases across 6 layers and generate actionable improvement artifacts.

## Commands

| Command | Purpose |
|---------|---------|
| `/ei:scan` | Standard 6-layer analysis (~50 findings, 10 min) |
| `/ei:scan --quick` | Quick 3-layer scan (git, code, architecture, ~3 min) |
| `/ei:scan --full` | Standard + deep domain analysis on Layer 3 |
| `/ei:scan --deep` | Deep: 20 sub-agents, 100+ findings, detailed report (~20 min) |
| `/ei:scan --gate measure` | Create quality baseline for CI ratcheting |
| `/ei:scan --gate check` | Check current state against baseline (CI integration) |
| `/ei:apply` | Generate artifacts from scan results |
| `/ei:apply --pick` | Interactive cherry-pick which artifacts to generate |
| `/ei:brief` | Interactive walkthrough of scan findings |
| `/ei:compare` | Compare current scan against previous to show progress/regressions |
| `/ei:intro` | Plugin introduction and usage guide |

## The 6 Analysis Layers

| Layer | Source | Requires |
|-------|--------|----------|
| L1: Git History | Commits, fix patterns, hotspots, temporal coupling | git |
| L2: Pull Requests | PR comments, code review feedback, process rules | `gh` CLI |
| L3: Code & Docs | Naming, docs, gettext, tests, auth audit, feature flags, soft-delete, money fields, error patterns | - |
| L4: Claude Config | .claude/ skills, agents, CLAUDE.md rules, enforcement gaps | - |
| L5: Claude Sessions | Recurring asks, debugging patterns | ccrider MCP |
| L6: Architecture | Boundaries, coupling, drift, dead code, growth prediction | mix xref |

## Deep Mode (`--deep`)

Spawns 6 orchestrator agents (haiku), each coordinating 2-6 specialist sub-agents:

```
L1: 4 sub-agents (fix categorizer, co-change, dev patterns, hotspot trends)
L2: 3 sub-agents (reviewer instructions, process rules, friction analysis)
L3: 6 sub-agents (naming, boundaries, consistency, flags, errors, test gaps)
L4: 2 sub-agents (rule enforcement audit, missing rule detector)
L5: 2 sub-agents (recurring tasks, debugging patterns)
L6: 3 sub-agents (boundary validator, coupling, growth predictor)
```

Produces TWO reports: `report.md` (dashboard) + `detailed-report.md` (comprehensive per-theme analysis).

## Architecture: Script-First, LLM-Second

**60-70% of analysis is deterministic scripts**, 30-40% is LLM interpretation.

```
scripts/analyze-git-history.py   → layers/git-history.json
scripts/analyze-prs.py           → layers/pr-reviews.json
scripts/analyze-code.py          → layers/code-docs.json
scripts/analyze-config.sh        → layers/claude-config.json
scripts/analyze-sessions.py      → layers/sessions.json
scripts/analyze-architecture.sh  → layers/architecture.json
scripts/temporal-coupling.py     → layers/temporal-coupling.json  (deep mode)
scripts/hotspot-score.py         → layers/hotspot-score.json      (deep mode)
scripts/quality-gate.py          → baseline.json                  (gate mode)
scripts/merge-findings.py        → findings-merged.json
```

## Output Directory

```
.claude/inspector/
├── report.md                # Dashboard summary
├── detailed-report.md       # Deep mode: per-theme comprehensive analysis
├── baseline.json            # Gate mode: quality baseline
├── layers/                  # Per-layer analysis (preserved)
│   ├── L1/-L6/              # Deep mode: sub-agent outputs + consolidated.md
│   └── sessions/            # Session analysis files
├── history/                 # Timestamped scan snapshots for /ei:compare
│   ├── scan-2026-03-01.json
│   └── scan-2026-03-15.json
├── generated/               # Artifacts from /ei:apply
│   ├── credo-checks/        # .ex files
│   ├── skills/              # .md skill files
│   ├── ci-scripts/          # Shell scripts
│   ├── review-prompts/      # 3 formats
│   ├── claude-md-rules.md
│   └── iron-laws.md
└── config.md
```

## Iron Laws

1. **Scripts extract data, agents interpret** — agents NEVER run git log, gh pr list, or raw grep
2. **ONE agent per layer** (standard) or **ONE orchestrator per layer** (deep) — clear boundaries
3. **All agents get pre-computed JSON** — not raw command output
4. **Findings use YAML frontmatter** — with inline arrays: `artifact_types: [credo-check, ci-step]`
5. **Generated artifacts stay in .claude/inspector/generated/** — never write to project lib/ directly
6. **Orchestrators handle file writing** — sub-agents return text, orchestrator writes .md files
7. **Bash call budget: max 2** — one for scripts, one for session scoring

## Framework Detection

### Ash Framework

If `use Ash.Resource` or `use Ash.Domain` detected:

- Warn: "This project uses Ash Framework. Some Ecto-specific analysis may not apply."
- Skip Ecto-specific checks in Layer 3 and Layer 6

## Prerequisites

- **Required**: git, Elixir/mix (for xref, compile validation)
- **Layer 2**: `gh` CLI authenticated (for PR analysis)
- **Layer 5**: ccrider MCP (for Claude session analysis)
- **Layer 6**: mix xref (standard with Elixir)

## Permissions Setup (Reduce Prompts)

Add to `.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 **/elixir-inspector/**)",
      "Bash(bash **/elixir-inspector/**)",
      "Bash(SCRIPTS=*)",
      "Bash(mkdir -p *)"
    ]
  }
}
```
