---
name: ei:intro
description: >
  Walk through the Elixir Inspector plugin commands and Credo check generation workflow.
  Use when a new user asks what is Inspector, how does ei:scan work, what commands are
  available, or needs an introduction to codebase audit and review features.
effort: low
argument-hint: ""
---

# Elixir Inspector — Introduction

Welcome to the Elixir Inspector plugin! This plugin analyzes your Elixir/Phoenix codebase across **6 layers** and generates actionable improvements.

## What It Does

Inspector scans your project's **code, git history, pull requests, documentation,
Claude sessions, and architecture** to find recurring patterns and pain points.
Then it generates concrete artifacts you can immediately use:

| Output | What You Get |
|--------|-------------|
| **Credo checks** | Custom `.ex` checks for your project's specific rules |
| **Claude Code skills** | Domain-specific rules and conventions as `.md` skills |
| **CLAUDE.md rules** | Iron Laws and behavioral instructions for your project |
| **CI/CD scripts** | Translation checks, boundary validation, format enforcement |
| **Code review prompts** | 3 formats: generic checklist, Claude system prompt, GitHub Actions |

## Prerequisites

| Tool | Required For | Install |
|------|-------------|---------|
| git | Layer 1 (Git History) | Already installed |
| `gh` CLI | Layer 2 (PR Reviews) | `brew install gh && gh auth login` |
| ccrider MCP | Layer 5 (Sessions) | See [ccrider](https://github.com/neilberkman/ccrider) |
| mix / Elixir | Layer 3, 6 (Code, Architecture) | Already installed |

## Commands

```
/ei:scan              # Full 6-layer analysis
/ei:scan --quick      # Quick scan (3 layers: git, code, architecture)
/ei:scan --full       # Deep domain analysis mode
/ei:apply             # Generate all artifacts from scan results
/ei:apply --pick      # Cherry-pick which artifacts to generate
/ei:brief             # Interactive walkthrough of findings
```

## Typical Workflow

```
1. /ei:scan           → Analyzes your project (~5-10 min full, ~2-3 min quick)
2. /ei:brief          → Walk through findings, understand what was found
3. /ei:apply --pick   → Generate the artifacts you want
4. Review & adopt     → Copy generated files from .claude/inspector/generated/
```

## Example Output

After running `/ei:scan`, you'll see a dashboard like:

```
| Layer       | Findings | Critical | Automatable | Top Suggestion              |
|-------------|----------|----------|-------------|-----------------------------|
| Git History |    8     |    1     |      5      | Credo check: missing gettext|
| PR Reviews  |    5     |    0     |      3      | CI step: format check       |
| Code & Docs |   12     |    2     |      7      | Skill: naming conventions   |
| Config      |    2     |    0     |      2      | CLAUDE.md: add Iron Laws    |
| Sessions    |    4     |    1     |      3      | Skill: test after new module|
| Architecture|    6     |    2     |      1      | Credo: no Repo in web layer |

Total: 37 findings | 6 critical | 21 automatable
```

## Iron Laws

1. **NEVER modify project files** — intro is informational only, DO NOT write or edit code
2. **MUST NOT run scan automatically** — only explain commands, let user decide when to run
3. **DO NOT skip prerequisites check** — warn if `gh` CLI or ccrider are not available

## References

- `${CLAUDE_SKILL_DIR}/../scan/references/report-template.md` — Report structure reference
- `${CLAUDE_SKILL_DIR}/../scan/references/finding-schema.md` — Finding format reference

Ready to start? Run `/ei:scan` on your project!
