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
| **Total** | **3** | **11** | **29** | — |

---

## Phase 1: Fix Blockers (Must Fix)

### - [ ] 1.1 Fix `argument:` → `argument-hint:` in challenge skill
- **File**: `plugins/elixir-phoenix/skills/challenge/SKILL.md:4`
- **Issue**: Uses undocumented `argument:` field instead of `argument-hint:`
- **Impact**: Claude Code silently ignores the field — argument hint never displays
- **Fix**: Rename `argument:` to `argument-hint:` (line 4)
- **Action**: FIX

### - [ ] 1.2 Fix `argument:` → `argument-hint:` in assigns-audit skill
- **File**: `plugins/elixir-phoenix/skills/assigns-audit/SKILL.md:4`
- **Issue**: Same as 1.1 — uses `argument:` instead of `argument-hint:`
- **Impact**: Argument hint never displays during autocomplete
- **Fix**: Rename `argument:` to `argument-hint:` (line 4)
- **Action**: FIX

### - [ ] 1.3 Trim research SKILL.md from 195 → ≤185 lines
- **File**: `plugins/elixir-phoenix/skills/research/SKILL.md`
- **Issue**: 195 lines, exceeds 185-line hard limit for command skills by 10 lines
- **Fix**: Move detailed content to `references/` or trim inline examples
- **Action**: FIX

---

## Phase 2: Fix Warnings (Should Fix)

### - [ ] 2.1 Fix marketplace.json schema — move description/version under metadata
- **File**: `.claude-plugin/marketplace.json`
- **Issue**: Top-level `description` and `version` are non-standard per official schema. Should be under `metadata` object
- **Fix**: Restructure to use `metadata: { description, version }` format
- **Action**: FIX

### - [ ] 2.2 Fix version mismatch in marketplace.json
- **File**: `.claude-plugin/marketplace.json` plugin entry
- **Issue**: Plugin entry says `"version": "1.0.0"` but `plugin.json` says `"2.0.0"`. Stale/misleading
- **Fix**: Remove `version` from marketplace plugin entry (let plugin.json be single source of truth)
- **Action**: FIX (combine with 2.1)

### - [ ] 2.3 Trim work/references/execution-guide.md from 402 → ≤350 lines
- **File**: `plugins/elixir-phoenix/skills/work/references/execution-guide.md`
- **Issue**: 402 lines, exceeds 350-line hard limit for reference files by 52 lines
- **Fix**: Trim verbose examples or split into separate reference files
- **Action**: FIX

### - [ ] 2.4 Trim document/references/documentation-patterns.md from 359 → ≤350 lines
- **File**: `plugins/elixir-phoenix/skills/document/references/documentation-patterns.md`
- **Issue**: 359 lines, exceeds 350-line limit by 9 lines
- **Fix**: Minor trim — remove redundant examples or consolidate
- **Action**: FIX

### - [ ] 2.5 Add `stop_hook_active` guard to Stop hook script
- **File**: `plugins/elixir-phoenix/hooks/scripts/check-pending-plans.sh`
- **Issue**: Docs recommend checking `stop_hook_active` to prevent infinite loops. Currently safe (exits 0, doesn't block), but fragile if hook is later enhanced to block
- **Fix**: Add stdin parsing + early exit guard at top of script
- **Action**: FIX (defensive)

### - [ ] 2.6 Remove superfluous matcher from Stop hook
- **File**: `plugins/elixir-phoenix/hooks/hooks.json` (Stop event)
- **Issue**: `"matcher": ""` on Stop event is silently ignored — Stop doesn't support matchers
- **Fix**: Remove the `matcher` field from Stop event entry
- **Action**: SKIP — cosmetic only, no behavioral impact. Low priority

---

## Phase 3: Evaluate New Features (Info — Adopt or Skip)

### Agents — New Capabilities

### - [ ] 3.1 Add `maxTurns` to runaway-prone agents
- **Feature**: `maxTurns` field prevents agents from spinning indefinitely
- **Docs**: sub-agents.md — positive integer, limits API round-trips
- **Candidates**: `deep-bug-investigator` (spawns 4 subagents), `workflow-orchestrator`, `parallel-reviewer`
- **Action**: ADD — good safety net for orchestrator agents, prevents cost runaway

### - [ ] 3.2 Evaluate `Task(agent_type)` restriction syntax
- **Feature**: Orchestrators can restrict which subagent types they spawn
- **Docs**: sub-agents.md
- **Impact**: Adds safety — prevents orchestrators from spawning arbitrary agents
- **Action**: SKIP for now — current orchestrators already have explicit subagent prompts inline. Reassess when agent count grows

### - [ ] 3.3 Evaluate per-agent `hooks` in frontmatter
- **Feature**: Agents can define their own lifecycle hooks
- **Docs**: sub-agents.md
- **Action**: SKIP — no clear use case yet. Plugin-level hooks cover current needs

### - [ ] 3.4 Evaluate `mcpServers` field for agents
- **Feature**: Agents can explicitly bind to MCP servers
- **Docs**: sub-agents.md
- **Action**: SKIP — Tidewave detection is handled at session level. Per-agent MCP binding adds complexity without clear benefit

### Skills — New Capabilities

### - [ ] 3.5 Evaluate `context: fork` for skills
- **Feature**: Skills can fork context to avoid polluting parent conversation
- **Docs**: skills.md
- **Action**: SKIP — our orchestrator pattern already handles context isolation via Task subagents

### - [ ] 3.6 Evaluate `allowed-tools` for skills
- **Feature**: Skills can restrict which tools are available during execution
- **Docs**: skills.md
- **Action**: SKIP — tool restrictions are already managed at agent level via `tools`/`disallowedTools`

### - [ ] 3.7 Evaluate `user-invocable: false` for internal skills
- **Feature**: Skills can be marked non-invocable (only loaded by agents via `skills:` field)
- **Docs**: skills.md
- **Candidates**: Reference-only skills loaded by agents but not useful as standalone commands
- **Action**: ADD — audit skills list and mark pure-reference skills as non-invocable. Reduces command clutter

### - [ ] 3.8 Evaluate dynamic context `!`command`` syntax
- **Feature**: Skills can inject dynamic output from shell commands into context
- **Docs**: skills.md
- **Action**: SKIP — interesting but niche. No current skill would benefit enough to justify the added complexity

### - [ ] 3.9 Evaluate positional `$ARGUMENTS[N]` access
- **Feature**: Skills can access individual positional arguments by index
- **Docs**: skills.md
- **Action**: SKIP — current skills use `$ARGUMENTS` as a whole string. No need for positional parsing yet

### Hooks — New Capabilities

### - [ ] 3.10 Add `timeout` to short-running hook scripts
- **Feature**: Custom timeout per hook (default is 600s/10min)
- **Docs**: hooks.md
- **Candidates**: Format hooks (30s), progress logging (15s), compile check (60s)
- **Action**: ADD — prevents stalled scripts from blocking Claude. Low effort, high safety value

### - [ ] 3.11 Add `statusMessage` to visible hooks
- **Feature**: Custom spinner text during hook execution
- **Docs**: hooks.md
- **Candidates**: PostToolUse format hook → "Formatting Elixir...", compile hook → "Compiling..."
- **Action**: ADD — improves UX with zero risk

### - [ ] 3.12 Add `async: true` to fire-and-forget hooks
- **Feature**: Hooks that don't need to block can run asynchronously
- **Docs**: hooks.md
- **Candidates**: `log-progress.sh` (pure logging, no output needed)
- **Action**: ADD — progress logging shouldn't block Claude

### - [ ] 3.13 Evaluate `SubagentStart` hook for Iron Laws injection
- **Feature**: Hook fires when any subagent starts — could inject Iron Laws context
- **Docs**: hooks.md
- **Action**: SKIP — subagents already get Iron Laws via preloaded skills. Adding a hook would double the injection

### - [ ] 3.14 Evaluate `SessionEnd` hook for cleanup
- **Feature**: Hook fires when session ends
- **Docs**: hooks.md
- **Action**: SKIP — no temp artifacts need cleanup currently. Plans persist intentionally

### - [ ] 3.15 Evaluate `TaskCompleted` hook
- **Feature**: Hook fires when a task completes
- **Docs**: hooks.md
- **Action**: SKIP — interesting for enforcing `mix test` after task completion, but would slow down iterative workflows

### - [ ] 3.16 Evaluate `prompt`/`agent` hook types
- **Feature**: Hooks that use LLM evaluation instead of shell commands
- **Docs**: hooks.md
- **Candidates**: Stop hook could use LLM to evaluate plan completeness instead of grep
- **Action**: SKIP for now — shell-based hooks are deterministic and cheap. LLM hooks add latency and cost

### Config — New Capabilities

### - [ ] 3.17 Add `homepage` and `repository` to plugin.json
- **Feature**: Optional metadata for public distribution
- **Docs**: plugins-reference.md
- **Action**: ADD — low effort, improves discoverability

### - [ ] 3.18 Add `tags` to marketplace plugin entry
- **Feature**: Searchability tags for marketplace listing
- **Docs**: plugin-marketplaces.md
- **Action**: ADD — `["elixir", "phoenix", "liveview", "oban", "ecto"]` improves findability

---

## Execution Plan

### Batch 1: Blockers (immediate)
1. Fix `argument:` → `argument-hint:` in 2 skills (1.1, 1.2)
2. Trim research/SKILL.md to ≤185 lines (1.3)

### Batch 2: Config fixes
3. Restructure marketplace.json (2.1, 2.2)
4. Add homepage/repository to plugin.json (3.17)
5. Add tags to marketplace entry (3.18)

### Batch 3: Size limit fixes
6. Trim work/references/execution-guide.md to ≤350 (2.3)
7. Trim document/references/documentation-patterns.md to ≤350 (2.4)

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
- 2.6: Stop matcher removal (cosmetic)
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
