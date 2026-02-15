# Docs-Check Findings & Fix Plan

**Date**: 2026-02-15
**Source**: Full docs-check validation against Claude Code documentation (9 pages, ~420KB)
**Plugin**: `elixir-phoenix` v2.0.0

---

## Summary

| Component | Blockers | Warnings | Info | Pass |
|-----------|----------|----------|------|------|
| Agents | 0 | 0 | 4 | 20/20 |
| Skills | 3 | 6 | 0 | 37 checked |
| Hooks | 0 | 2 | 11 | 14 |
| Config | 0 | 3 | 14 | 15 |
| **Total** | **3** | **11** | **29** | --- |

---

## Phase 1: Fix Blockers (Must Fix)

- [x] **1.1** Fix `argument:` -> `argument-hint:` in challenge skill
  - File: `plugins/elixir-phoenix/skills/challenge/SKILL.md:4`
  - Issue: Uses undocumented `argument:` field instead of `argument-hint:`
  - Action: FIX

- [x] **1.2** Fix `argument:` -> `argument-hint:` in assigns-audit skill
  - File: `plugins/elixir-phoenix/skills/assigns-audit/SKILL.md:4`
  - Issue: Same as 1.1
  - Action: FIX

- [x] **1.3** Trim research SKILL.md from 195 -> 185 lines
  - File: `plugins/elixir-phoenix/skills/research/SKILL.md`
  - Issue: 195 lines, exceeds 185-line hard limit by 10 lines
  - Action: FIX — removed inline example block (now 144 lines)

---

## Phase 2: Fix Warnings (Should Fix)

- [x] **2.1** Fix marketplace.json schema — move description/version under metadata
  - File: `.claude-plugin/marketplace.json`
  - Issue: Top-level `description` and `version` are non-standard per official schema
  - Action: FIX — restructured to `metadata: { description, version }`

- [x] **2.2** Fix version mismatch in marketplace.json
  - File: `.claude-plugin/marketplace.json` plugin entry
  - Issue: Plugin entry says `"version": "1.0.0"` but plugin.json says `"2.0.0"`
  - Action: FIX — removed version from marketplace entry (single source of truth)

- [x] **2.3** Trim work/references/execution-guide.md from 402 -> 350 lines
  - File: `plugins/elixir-phoenix/skills/work/references/execution-guide.md`
  - Issue: 402 lines, exceeds 350-line hard limit by 52 lines
  - Action: FIX — trimmed examples (now 344 lines)

- [x] **2.4** Trim document/references/documentation-patterns.md from 359 -> 350 lines
  - File: `plugins/elixir-phoenix/skills/document/references/documentation-patterns.md`
  - Issue: 359 lines, exceeds 350-line limit by 9 lines
  - Action: FIX — condensed README template (now 345 lines)

- [x] **2.5** Add `stop_hook_active` guard to Stop hook script
  - File: `plugins/elixir-phoenix/hooks/scripts/check-pending-plans.sh`
  - Issue: Docs recommend checking `stop_hook_active` to prevent infinite loops
  - Action: FIX — added stdin parsing + early exit guard

- [x] **2.6** Remove superfluous matcher from Stop hook
  - File: `plugins/elixir-phoenix/hooks/hooks.json` (Stop event)
  - Issue: `"matcher": ""` on Stop event is silently ignored
  - Action: FIX — removed matcher field from Stop event

---

## Phase 3: Evaluate New Features (Info — Adopt or Skip)

### Agents — New Capabilities

- [x] **3.1** Add `maxTurns` to runaway-prone agents
  - Feature: `maxTurns` field prevents agents from spinning indefinitely
  - Candidates: deep-bug-investigator (30), parallel-reviewer (25), workflow-orchestrator (50), call-tracer (25), planning-orchestrator (40)
  - Action: ADD

- [ ] **3.2** Evaluate `Task(agent_type)` restriction syntax
  - Feature: Orchestrators can restrict which subagent types they spawn
  - Action: SKIP — current orchestrators have explicit subagent prompts inline

- [ ] **3.3** Evaluate per-agent `hooks` in frontmatter
  - Feature: Agents can define their own lifecycle hooks
  - Action: SKIP — no clear use case yet

- [ ] **3.4** Evaluate `mcpServers` field for agents
  - Feature: Agents can explicitly bind to MCP servers
  - Action: SKIP — Tidewave detection handled at session level

### Skills — New Capabilities

- [ ] **3.5** Evaluate `context: fork` for skills
  - Feature: Skills can fork context to avoid polluting parent conversation
  - Action: SKIP — orchestrator pattern already handles context isolation via Task

- [ ] **3.6** Evaluate `allowed-tools` for skills
  - Feature: Skills can restrict which tools are available during execution
  - Action: SKIP — tool restrictions managed at agent level

- [x] **3.7** Evaluate `user-invocable: false` for internal skills
  - Feature: Skills can be marked non-invocable (only loaded by agents)
  - Applied to: ecto-patterns, liveview-patterns, security, testing, oban, elixir-idioms, phoenix-contexts, compound-docs
  - Action: ADD

- [ ] **3.8** Evaluate dynamic context injection syntax
  - Feature: Skills can inject dynamic output from shell commands
  - Action: SKIP — niche, no current skill benefits

- [ ] **3.9** Evaluate positional `$ARGUMENTS[N]` access
  - Feature: Skills can access individual positional arguments by index
  - Action: SKIP — current skills use `$ARGUMENTS` as whole string

### Hooks — New Capabilities

- [x] **3.10** Add `timeout` to short-running hook scripts
  - Feature: Custom timeout per hook (default 600s is too long)
  - Applied: 15-60s timeouts on all hook scripts
  - Action: ADD

- [x] **3.11** Add `statusMessage` to visible hooks
  - Feature: Custom spinner text during hook execution
  - Applied: "Formatting Elixir...", "Compiling...", "Detecting Tidewave...", "Checking for resumable work..."
  - Action: ADD

- [x] **3.12** Add `async: true` to fire-and-forget hooks
  - Feature: Non-blocking hook execution
  - Applied: log-progress.sh
  - Action: ADD

- [ ] **3.13** Evaluate `SubagentStart` hook for Iron Laws injection
  - Action: SKIP — subagents already get Iron Laws via preloaded skills

- [ ] **3.14** Evaluate `SessionEnd` hook for cleanup
  - Action: SKIP — no temp artifacts need cleanup

- [ ] **3.15** Evaluate `TaskCompleted` hook
  - Action: SKIP — would slow iterative workflows

- [ ] **3.16** Evaluate `prompt`/`agent` hook types
  - Action: SKIP — shell hooks are deterministic and cheap

### Config — New Capabilities

- [x] **3.17** Add `homepage` and `repository` to plugin.json
  - Action: ADD — improves discoverability

- [x] **3.18** Add `tags` to marketplace plugin entry
  - Applied: `["elixir", "phoenix", "liveview", "oban", "ecto"]`
  - Action: ADD

---

## Execution Plan

### Batch 1: Blockers (immediate)

1. Fix `argument:` -> `argument-hint:` in 2 skills (1.1, 1.2)
2. Trim research/SKILL.md to 185 lines (1.3)

### Batch 2: Config fixes

3. Restructure marketplace.json (2.1, 2.2)
4. Add homepage/repository to plugin.json (3.17)
5. Add tags to marketplace entry (3.18)

### Batch 3: Size limit fixes

6. Trim work/references/execution-guide.md to 350 (2.3)
7. Trim document/references/documentation-patterns.md to 350 (2.4)

### Batch 4: Hook improvements

8. Add `stop_hook_active` guard (2.5)
9. Add `timeout` to hook scripts (3.10)
10. Add `statusMessage` to visible hooks (3.11)
11. Add `async: true` to log-progress hook (3.12)

### Batch 5: Agent safety

12. Add `maxTurns` to orchestrator agents (3.1)

### Batch 6: Skill cleanup

13. Audit and mark internal skills as `user-invocable: false` (3.7)

### Skipped (no action needed)

- 3.2: `Task(agent_type)` restriction (premature)
- 3.3: Per-agent hooks (no use case)
- 3.4: Agent mcpServers (handled at session level)
- 3.5: `context: fork` (covered by Task pattern)
- 3.6: `allowed-tools` (covered by agent-level tools)
- 3.8: Dynamic context injection (niche)
- 3.9: Positional arguments (not needed)
- 3.13: SubagentStart hook (would double Iron Laws)
- 3.14: SessionEnd hook (nothing to clean up)
- 3.15: TaskCompleted hook (slows iteration)
- 3.16: prompt/agent hook types (adds cost/latency)
