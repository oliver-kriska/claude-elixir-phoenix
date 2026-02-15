---
name: docs-check
description: |
  CONTRIBUTOR TOOL - Validate plugin against latest Claude Code documentation.
  Catches breaking changes, deprecations, discovers new features.
  Run before releases or periodically. NOT part of the distributed plugin.
argument-hint: "[--quick|--full|--focus=agents|skills|hooks|config]"
---

# Plugin Documentation Compatibility Check

Validates plugin agents, skills, hooks, and config against the latest
Claude Code documentation to catch breaking changes and discover new features.

## Usage

```text
/docs-check                    # Full validation (all components)
/docs-check --quick            # Structural checks only (no docs fetch, no tokens)
/docs-check --focus=agents     # Validate only agents
/docs-check --focus=skills     # Validate only skills
/docs-check --focus=hooks      # Validate only hooks
/docs-check --focus=config     # Validate only plugin.json/marketplace.json
```

## Architecture (OTP Supervision Pattern)

```text
┌──────────────────────────────────────────────────────────────┐
│  docs-validation-orchestrator (opus)                         │
│                                                              │
│  SCAN → FETCH DOCS → SPAWN WORKERS → COMPRESS → REPORT      │
│   │         │              │             │          │        │
│   ↓         ↓              ↓             ↓          ↓        │
│ inventory  curl only    4 parallel    context    unified     │
│ plugin     (no tokens)  subagents     supervisor report      │
│ components              (general)     (haiku)                │
└──────────────────────────────────────────────────────────────┘
```

## Workflow

### 1. Inventory

Scan `plugins/elixir-phoenix/` to determine what exists:
agents, skills, hooks, plugin config, marketplace config.

### 2. Fetch Docs (Targeted)

Download ONLY the doc pages relevant to existing components.
Uses `curl` — raw download, zero token cost. See `references/doc-pages.md`.

### 3. Spawn Validation Workers

One `general-purpose` subagent per component type, in parallel.
Each receives: cached doc content + plugin files + validation rules.
Workers write to `.claude/docs-check/reports/{type}-report.md`.

### 4. Compress (Context Supervisor)

If 3+ workers, spawn `context-supervisor` (haiku) to compress.
Priority: KEEP ALL breaking changes, COMPRESS suggestions, AGGRESSIVE on passed.

### 5. Structural Checks (Always Run)

Fast local checks — no docs or tokens needed:
agent frontmatter, skill structure, hook events, config schema.

### 6. Report & Action

Write `.claude/docs-check/docs-check-{date}.md`.
If issues found: offer to create branch and PR with fixes.

## Execution

Delegate to the `docs-validation-orchestrator` agent:

```text
Task(subagent_type: "docs-validation-orchestrator")
```

Pass the user's flags (--quick, --focus, etc.) in the prompt.

## Iron Laws

1. **NEVER fetch llms-full.txt** — targeted pages only
2. **curl for docs, not WebFetch** — no token waste on downloading
3. **Workers get docs IN PROMPT** — no runtime fetching
4. **Structural checks always run** — even if docs fetch fails
5. **Breaking changes are BLOCKERS** — surface prominently

## References

- `references/validation-rules.md` — Per-component validation checklists
- `references/doc-pages.md` — Component-to-URL mapping and fetch strategy
