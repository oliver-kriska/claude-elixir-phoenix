# Elixir Inspector

Analyze any Elixir/Phoenix codebase across 6 layers and generate actionable improvements — Credo checks, skills, CI steps, and review prompts.

## What It Does

Install the plugin, run `/ei:scan` on your project, get concrete improvements you can apply immediately.

```
/ei:scan              # Standard analysis (~50 findings, 10 min)
/ei:scan --deep       # Deep: 20 sub-agents, 100+ findings (~20 min)
/ei:scan --gate measure  # Create quality baseline for CI
/ei:apply             # Generate Credo checks, skills, CI scripts
```

### The 6 Analysis Layers

| Layer | Source | What It Finds |
|-------|--------|---------------|
| Git History | Commits, fix patterns | Recurring bugs, hotspot files, trends |
| PR Reviews | Review comments via `gh` | Implicit team rules, process gaps |
| Code & Docs | Module analysis | Naming drift, auth gaps, i18n holes, test gaps |
| Config | .claude/ directory | Rule enforcement gaps, missing conventions |
| Sessions | Claude sessions via ccrider | Recurring tasks, debugging patterns |
| Architecture | mix xref, boundaries | God contexts, circular deps, coupling |

### Deep Mode (--deep)

Spawns 20 specialist sub-agents across 6 orchestrator layers:

- **L1**: Fix categorizer, co-change analyzer, developer patterns, hotspot trends
- **L2**: Reviewer instruction extractor, process rule miner, friction analyzer
- **L3**: Naming miner, boundary mapper, consistency checker, flag detector, error handler, test gap finder
- **L4**: Rule enforcement auditor, missing rule detector
- **L5**: Recurring task miner, debugging pattern analyzer
- **L6**: Boundary validator, coupling analyzer, growth predictor

### What You Get After `/ei:apply`

| Artifact | Format | Example |
|----------|--------|---------|
| Credo checks | `.ex` files | `no_float_for_money.ex`, `authorize_handle_event.ex` |
| Skills | `.md` files | Domain naming conventions, error handling guide |
| CI scripts | `.sh` files | Translation check, boundary validation |
| CLAUDE.md rules | Markdown | Project-specific Iron Laws |
| Review prompts | 3 formats | Human checklist, Claude prompt, GitHub Actions |

## Installation

```bash
# From marketplace
/plugin marketplace add oliver-kriska
/plugin install elixir-inspector

# Or local development
claude --plugin-dir ./plugins/elixir-inspector
```

## Prerequisites

| Tool | Required For | Install |
|------|-------------|---------|
| git | Layer 1 (Git History) | Already installed |
| `gh` CLI | Layer 2 (PR Reviews) | `brew install gh && gh auth login` |
| ccrider MCP | Layer 5 (Sessions) | [github.com/neilberkman/ccrider](https://github.com/neilberkman/ccrider) |
| mix / Elixir | Layers 3, 6 | Already installed |

## Reducing Permission Prompts

Add to your project's `.claude/settings.json`:

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

## Test Results

Tested on 3 production projects:

| Project | Findings | Critical/High | Auth Audit |
|---------|----------|---------------|------------|
| Project A (150+ modules, SaaS) | 52 | 19 high | 281/294 unguarded |
| Project B (175 files, multi-tenant) | 48 | 2 crit + 9 high | 165 unguarded |
| Project C (AI/LLM integration) | 48 | 5 crit + 15 high | 27/29 unguarded |

## Architecture

```
Scripts (Python/Bash) → JSON → LLM Agents → Findings → Report
         60-70%              30-40%
    deterministic          interpretation
```

The scripts do the heavy lifting (git log parsing, file scanning, API calls).
Agents only interpret pre-computed JSON — no raw data extraction.
This saves ~60-70% of tokens vs having agents run commands directly.

## License

MIT
