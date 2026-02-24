# Plugin Improvement Plan: Harness Engineering Patterns

**Status**: IMPLEMENTATION PLAN
**Created**: 2026-02-24
**Updated**: 2026-02-24 — Incorporated Shape Up methodology insights from PR #7 (rjs/shaping-skills analysis)
**Based on**: Deep analysis of 7 high-impact gaps (7 parallel agents, ~430k tokens of research) + Shape Up methodology cross-pollination

---

## Overview

This plan synthesizes detailed research from 7 specialist agents, each of which read 20-40 plugin files and produced implementation specifications. The plan is organized into 4 implementation waves with concrete file changes, effort estimates, and dependencies.

---

## Wave 1: Quick Wins (Low Risk, High Impact)

**Timeline**: 1-2 days | **Files changed**: ~12 | **Lines added**: ~290

These require only text additions to existing skills — no new files, no architecture changes, no hooks.

### 1A. Mistake-Driven Feedback Loop — Suggestion Text

Add compound/learn suggestions at 3 failure recovery points.

| File | Change | Lines |
|------|--------|-------|
| `skills/work/SKILL.md` | After "With blockers:" section (~line 121), add: suggest `/phx:compound` after resolving blockers | +5 |
| `skills/work/references/error-recovery.md` | After "Recovery After BLOCKER" step 4, add step 5: "Ask user: Should I capture this fix as a lesson?" | +8 |
| `skills/review/SKILL.md` | In BLOCKED verdict section (~line 155), add: "After you fix these, run `/phx:compound` to document what you learned" | +5 |
| `agents/workflow-orchestrator.md` | In BLOCKED state handler, add: "Still compound resolved blockers + dead-ends even on partial completion" | +10 |
| `agents/planning-orchestrator.md` | In plan.md template, add Source section: capture user's original feature description verbatim | +8 |

**Why first**: Zero risk. Purely additive text. Immediately captures ~40% more learning moments. Source capture (from Shape Up) preserves original intent across context compaction.

> **Origin**: Source capture idea from [rjs/shaping-skills](https://github.com/rjs/shaping-skills) analysis (PR #7)

### 1B. Annotation Cycle — Plan Approval UX

Add annotation guidance to existing plan approval flow.

| File | Change | Lines |
|------|--------|-------|
| `agents/planning-orchestrator.md` | In "CRITICAL: After Writing Plan" section (~line 505), expand "Adjust the plan" option with annotation syntax instructions | +30 |
| `hooks/scripts/plan-stop-reminder.sh` | Add 4-line check: if plan has `**Annotation Cycles**:` field, skip reminder (not a new plan) | +4 |

**Why first**: Users already see "Adjust the plan" but don't know what to do with it. This makes it actionable.

### 1C. Shift Feedback Left — Hook Tuning

Optimize existing hook timeouts and scoping.

| File | Change | Lines |
|------|--------|-------|
| `hooks/hooks.json` | Reduce format hook timeout from 30s to 15s. Add file-scoped Credo check to PostToolUse Edit matcher | +8 |

**Why first**: Pure config change. Faster feedback loops immediately.

### 1D. Demo Statements for Plan Phases (from Shape Up)

Add requirement that each plan phase declares what's observable after completion.

| File | Change | Lines |
|------|--------|-------|
| `skills/plan/SKILL.md` | In plan template section, add: each phase MUST include `**Demo**: After this phase, [observable outcome]` | +10 |
| `skills/plan/references/planning-workflow.md` | Add "Demo Statements" subsection with examples: good ("user can log in via OAuth") vs bad ("auth module refactored") | +5 |

**Rule**: Flag phases that are purely backend with no observable output. Suggest reordering to ensure each phase delivers visible progress. A phase without a demo statement is a horizontal layer — Shape Up's core slicing discipline.

> **Origin**: Vertical slicing discipline from [rjs/shaping-skills](https://github.com/rjs/shaping-skills) (PR #7)

### 1E. Naming Test for Review Agents (from Shape Up)

Add "one verb per function" design smell check to review agents.

| File | Change | Lines |
|------|--------|-------|
| `agents/elixir-review-agent.md` | Add to checklist: "For each new function: can it be named with ONE idiomatic verb? Need 'or' to connect two verbs → suggest splitting. Name matches downstream effect, not this step → suggest renaming" | +15 |

**Why first**: Pure text addition to existing agent. Zero risk. Catches naming smells that indicate SRP violations — particularly valuable in Elixir where function naming conventions are strong.

> **Origin**: Naming test from `/breadboard-reflection` in [rjs/shaping-skills](https://github.com/rjs/shaping-skills) (PR #7)

### 1F. Plan Ripple-Check Hook (from Shape Up)

Add lightweight consistency reminder when plan artifacts are edited.

| File | Change | Lines |
|------|--------|-------|
| `hooks/hooks.json` | Add PostToolUse Edit matcher: if edited file is `plans/*/plan.md`, remind about progress.md + scratchpad.md consistency | +12 |
| `hooks/scripts/plan-ripple-check.sh` | NEW (~20 lines) | Check if plan.md was edited. If so, output reminder: "Plan changed — verify progress.md and scratchpad.md are still consistent" | +20 |

**Why first**: Lightweight precursor to Wave 3's entropy detection (3B) and JSON sidecar (3A). Catches plan/progress drift at the cheapest possible level. The full machine-reliable check comes in Wave 3.

> **Origin**: Ripple-check hook pattern from [rjs/shaping-skills](https://github.com/rjs/shaping-skills) (PR #7)

---

## Wave 2: New Capabilities (Medium Risk, High Impact)

**Timeline**: 3-5 days | **New files**: ~8 | **Modified files**: ~12 | **Lines added**: ~1,570

### 2A. Linter Errors as Remediation Instructions

Create error pattern → fix mapping and enhanced verification script.

| File | Type | Lines | Purpose |
|------|------|-------|---------|
| `hooks/scripts/error-matcher.sh` | NEW | ~150 | Parse compile/credo errors, look up remediation, output structured fix |
| `hooks/remediation-patterns.json` | NEW | ~400 | 40 patterns: 15 compiler warnings + 15 Credo rules + 10 Iron Laws → fix instructions |
| `skills/investigate/references/compiler-warnings.md` | NEW | ~250 | Detailed guide to common Elixir compiler warnings with fixes |
| `hooks/scripts/verify-elixir.sh` | MODIFY | ~80 | Uncomment/restructure to call error-matcher.sh (currently exits 0) |
| `hooks/hooks.json` | MODIFY | +5 | Wire error-matcher into PostToolUse Edit chain |

**Key design decisions**:
- Error matcher adds ~15ms latency (regex parse + JSON lookup) — negligible
- Remediation output format: `ERROR: {file:line}` → `REMEDIATION: {checklist + Elixir pattern}`
- Iron Law violations include specific correct code pattern, not just rule text
- Example output:
  ```
  ERROR: lib/my_app_web/user_live.ex:28
    function Accounts.get_user/1 is undefined

  REMEDIATION:
    1. Check spelling and arity: Is it get_user/1 or get_user/2?
    2. Is the module imported? Add: import MyApp.Accounts
    3. Does the function exist? grep -n "def get_user" lib/
    Elixir pattern: Accounts.get_user(user_id)  # full module path
  ```

**Impact**: Reduces fix-retry cycles by ~30-50% for common errors. This is OpenAI's single most impactful harness innovation.

### 2B. Annotation Cycle — Full Implementation (Enhanced with Shape Up)

Create the `--annotate` mode for iterative plan review, with requirements extraction and fit-check matrix.

| File | Type | Lines | Purpose |
|------|------|-------|---------|
| `skills/plan/SKILL.md` | MODIFY | +50 | Add `--annotate` mode section with syntax and workflow |
| `skills/plan/references/planning-workflow.md` | MODIFY | +110 | Add "Annotation Cycles" + "Requirements Extraction" + "Fit-Check Matrix" sections |
| `skills/plan/references/annotation-guide.md` | NEW | ~200 | Complete annotation reference: syntax, types, priorities, examples |
| `agents/planning-orchestrator.md` | MODIFY | +30 | Add requirements extraction step between research and task generation |

**Key design decisions**:
- Annotation syntax: `<!-- ANNOTATION: {priority} | {type} | {note} -->` (HTML comments, safe in Markdown)
- Priority: CRITICAL / HIGH / MEDIUM / LOW
- Type: TASK / SCOPE / DECISION / RISK / SPIKE / PATTERN / GENERAL
- Agent processes annotations in priority order, removes each after addressing
- Task IDs [Pn-Tm] NEVER deleted (Iron Law for annotations)
- Cycle tracking: `**Annotation Cycles**: n` in plan metadata
- Scratchpad gets `ANNOTATION CYCLE {n}` entries

**vs. `--existing`**: Annotation cycles are lightweight (no new agents spawned), fast (1-3 min per cycle). `--existing` is for deep research. Users combine both.

#### 2B+. Requirements Extraction Step (from Shape Up)

Before generating tasks, the planning-orchestrator enumerates explicit requirements (Rs) — what must be true regardless of implementation approach. This is Shape Up's core insight: requirements must be standalone, not dependent on any specific shape.

**Flow change in planning-orchestrator**:
```
BEFORE: Research → Task generation → Plan
AFTER:  Research → Requirements extraction → Task generation → Plan
```

**Requirements section in plan.md**:
```markdown
## Requirements

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| R1 | User can reset password via email | Must | User request |
| R2 | Token expires after 24 hours | Must | Security policy |
| R3 | Rate limit: max 3 resets per hour | Should | Best practice |
```

**Why this matters**: Catches missing requirements BEFORE task generation. Today we jump from research straight to tasks — requirements can fall through the cracks, especially for security and edge cases.

#### 2B++. Fit-Check Matrix for Contested Decisions (from Shape Up)

When the decision council identifies 2+ competing approaches, produce an R × S fit-check grid alongside the council arguments. This makes trade-offs visible at a glance.

**Trigger**: Decision council has 2+ options AND ≥3 requirements extracted.

**Format in plan.md**:
```markdown
## Fit Check: [Decision Name]

| Req | Description | Option A: GenServer | Option B: ETS | Option C: Agent |
|-----|-------------|:---:|:---:|:---:|
| R1 | Concurrent access | ✅ | ✅ | ❌ |
| R2 | Survives restart | ❌ | ❌ | ✅ |
| R3 | Sub-ms reads | ❌ | ✅ | ❌ |
| **Score** | | **1/3** | **2/3** | **1/3** |
```

**Key rule**: ✅/❌ only — no "maybe" or "partial". Forces clear thinking. Notes in a separate column if needed.

> **Origin**: Fit-check matrix and requirements extraction from [rjs/shaping-skills](https://github.com/rjs/shaping-skills) (PR #7)

### 2C. Runtime Smoke Tests (Tier A)

Add Tidewave `project_eval` verification step after tests pass.

| File | Type | Lines | Purpose |
|------|------|-------|---------|
| `skills/work/SKILL.md` | MODIFY | +15 | Add "Per-Feature Behavioral Smoke Test (Tidewave)" section |
| `skills/work/references/execution-guide.md` | MODIFY | +40 | Add 4 smoke test templates by annotation type |
| `agents/verification-runner.md` | MODIFY | +15 | Add Step 5: Optional smoke test if Tidewave available |
| `agents/workflow-orchestrator.md` | MODIFY | +10 | In VERIFYING: add conditional smoke test after mix test |
| `skills/verify/references/validation-checklist.md` | MODIFY | +20 | "Automated Smoke Tests (Tidewave)" checklist |

**Smoke test templates** (by task annotation):
- `[ecto]`: `Repo.transaction` → create/fetch/verify/rollback (no data persists)
- `[liveview]`: `get_logs level: :error` after feature exercise
- `[oban]`: Enqueue test job → verify in `oban_jobs` table → check state
- `[security]`: Test invalid input rejection via changeset

**Key constraint**: Conditional on Tidewave availability. Graceful degradation (skip silently if not running). Max 3 retries, then BLOCKER.

---

## Wave 3: Structural Changes (Medium-High Risk, High Impact)

**Timeline**: 5-8 days | **New files**: ~12 | **Modified files**: ~8 | **Lines added**: ~2,500

### 3A. JSON Feature Lists (Plan Sidecar)

Add machine-reliable plan state alongside Markdown.

| File | Type | Lines | Purpose |
|------|------|-------|---------|
| `hooks/scripts/generate-plan-json.sh` | NEW | ~100 | Parse plan.md → generate plan.json on plan creation |
| `hooks/scripts/validate-plan-integrity.sh` | NEW | ~80 | Validate plan.md structure + plan.json schema after edits |
| `hooks/scripts/sync-plan-state.sh` | NEW | ~60 | Sync plan.md checkbox state → plan.json after task completion |
| `skills/work/references/plan-json-format.md` | NEW | ~200 | Full JSON schema, sync mechanism, migration workflow |
| `hooks/hooks.json` | MODIFY | +15 | Wire generate/validate/sync into PostToolUse Write and Edit |
| `skills/work/SKILL.md` | MODIFY | +5 | Mention plan.json role in task loading |
| `skills/work/references/resume-strategies.md` | MODIFY | +20 | Add integrity check section |
| `skills/plan/SKILL.md` | MODIFY | +5 | Plans now include plan.json |

**JSON schema** (key fields per task):
```json
{
  "task_id": "P1-T1",
  "description": "Add password_hash field",
  "agent": "ecto",
  "status": "pending|in_progress|completed|blocked",
  "implementation_note": "",
  "metadata": { "locations": [], "retry_count": 0 }
}
```

**Key design decisions**:
- plan.md is ALWAYS source of truth during execution
- plan.json is shadow copy for validation and recovery
- Sync is async (doesn't block execution)
- Migration: old plans auto-generate plan.json on first `/phx:work`
- Mismatch detection: user chooses "trust markdown" or "trust JSON"

**Why Wave 3**: Needs generate/validate/sync scripts. More moving parts. But high value for long-running `/phx:full` sessions.

### 3B. Entropy Detection System

Create entropy detection agent, skill, hooks, and baseline tracking.

| File | Type | Lines | Purpose |
|------|------|-------|---------|
| `agents/entropy-detector.md` | NEW | ~280 | Haiku model agent: reads metrics, compares baseline, reports drift |
| `skills/entropy/SKILL.md` | NEW | ~100 | `/phx:entropy` command docs |
| `skills/entropy/references/metrics-glossary.md` | NEW | ~120 | What each metric means, healthy ranges |
| `skills/entropy/references/entropy-patterns.md` | NEW | ~150 | Common drift scenarios + recovery strategies |
| `skills/entropy/references/baseline-strategy.md` | NEW | ~100 | When to save/reset baseline, decision trees |
| `hooks/scripts/check-entropy.sh` | NEW | ~40 | SessionStart: quick quality fingerprint (<15s, non-blocking) |
| `hooks/scripts/post-workflow-entropy.sh` | NEW | ~50 | Post-workflow: compare to baseline after `/phx:full` |
| `skills/audit/SKILL.md` | MODIFY | +80 | Add `--gc` mode + `--save-baseline` + `--reset-baseline` flags |
| `hooks/hooks.json` | MODIFY | +15 | Add entropy check to SessionStart + post-workflow integration |

**Baseline file** (`.claude/metrics/baseline.json`):
```json
{
  "timestamp": "2026-02-24T10:30:00Z",
  "scores": { "architecture": 85, "performance": 78, "security": 92, "tests": 88 },
  "metrics": { "compile_warnings": 0, "credo_violations": 5, "circular_deps": 0 }
}
```

**Key design decisions**:
- Entropy checks are NEVER blocking — purely informational
- SessionStart fingerprint runs in background (<15s)
- Post-workflow check spawns haiku agent for comparison
- `--gc` mode is 2-3 minute lightweight scan (vs 10-15 min full audit)
- Health status: HEALTHY / DEGRADED / CRITICAL
- Findings categorized: REGRESSION / STAGNATION / IMPROVEMENT

### 3C. E2E Test Detection & Generation (Tier B)

Detect Wallaby/Playwright and generate E2E test templates.

| File | Type | Lines | Purpose |
|------|------|-------|---------|
| `hooks/scripts/detect-e2e.sh` | NEW | ~30 | Detect Wallaby/Playwright in mix.exs + int_test env |
| `skills/testing/references/e2e-wallaby-template.md` | NEW | ~100 | Wallaby E2E test template for LiveView features |
| `skills/testing/references/e2e-playwright-template.md` | NEW | ~100 | PhoenixTest.Playwright E2E test template |
| `agents/verification-runner.md` | MODIFY | +15 | Add Step 4b: E2E tests if available |

---

## Wave 4: Unattended Pipeline (High Risk, High Impact)

**Timeline**: 5-8 days | **Modified files**: ~5 | **Lines added**: ~350

### 4A. Unattended Mode for `/phx:full`

Add `--unattended` flag that auto-pilots through all decision points.

| File | Type | Lines | Purpose |
|------|------|-------|---------|
| `skills/full/SKILL.md` | MODIFY | +60 | Document `--unattended` flag, defaults, safety rails |
| `agents/workflow-orchestrator.md` | MODIFY | +40 | Add unattended branch in DISCOVERING and REVIEWING |
| `agents/planning-orchestrator.md` | MODIFY | +30 | Auto-resolution for contested architectural decisions |
| `skills/full/references/execution-steps.md` | MODIFY | +50 | Phase-by-phase unattended differences |
| `skills/full/references/safety-recovery.md` | MODIFY | +20 | Exit conditions for unattended mode |

**Auto-decision rules at each phase**:

| Phase | Decision Point | Auto-Selection |
|-------|---------------|----------------|
| DISCOVERING | Workflow depth | Complexity ≤2 + non-security → "just do it"; 3-6 → "plan it"; 7+ → "research it" |
| DISCOVERING | Security features | Always force planning (never "just do it") |
| PLANNING | Contested decisions | Unanimous council → that option; codebase precedent → match; fallback → maintainability default |
| REVIEWING | Finding triage | All BLOCKERs → fix; WARNINGs ≤3 → fix; WARNINGs >3 → skip (logged); SUGGESTIONs → skip |

**Safety rails** (stricter than normal mode):
| Parameter | Normal | Unattended |
|-----------|--------|-----------|
| max-cycles | 10 | **6** |
| max-retries | 3 | **2** |
| max-blockers | 5 | **3** |

**Mandatory exit conditions** (must stop and alert):
- Cycle limit reached
- Blocker limit reached
- Test suite >50% failing
- Fatal compilation error
- Same verification failure 2+ cycles (loop detection)

**Logging**: Every auto-decision logged to progress.md with timestamp, reasoning, confidence level (HIGH/MEDIUM/LOW), and options considered.

**Why Wave 4**: Highest risk. Requires all prior waves to be stable. Auto-decisions can go wrong. But biggest workflow acceleration for experienced users.

---

## Implementation Dependencies

```
Wave 1 (no dependencies)
  ├── 1A: Mistake-driven suggestions + source capture ──→ immediate
  ├── 1B: Annotation UX ──→ immediate
  ├── 1C: Hook tuning ──→ immediate
  ├── 1D: Demo statements (Shape Up) ──→ immediate
  ├── 1E: Naming test (Shape Up) ──→ immediate
  └── 1F: Plan ripple-check (Shape Up) ──→ immediate

Wave 2 (depends on Wave 1 for annotation foundations)
  ├── 2A: Remediation patterns ──→ immediate (parallel with 2B)
  ├── 2B: Full annotation cycle + requirements extraction + fit-check ──→ depends on 1B, 1D
  └── 2C: Runtime smoke tests ──→ immediate (parallel)

Wave 3 (independent of Wave 2, but benefits from it)
  ├── 3A: JSON feature lists ──→ immediate (1F ripple-check is lightweight precursor)
  ├── 3B: Entropy detection ──→ immediate (1F ripple-check is lightweight precursor)
  └── 3C: E2E templates ──→ depends on 2C (smoke test patterns)

Wave 4 (depends on Waves 1-3 being stable)
  └── 4A: Unattended mode ──→ depends on 3A (JSON state), 3B (entropy), 2A (remediation)
```

---

## Total Effort Summary

| Wave | New Files | Modified Files | Lines Added | Risk | Timeline |
|------|-----------|----------------|-------------|------|----------|
| 1 | 1 | 12 | ~290 | Low | 1-2 days |
| 2 | 4 | 9 | ~1,570 | Medium | 3-5 days |
| 3 | 12 | 8 | ~2,500 | Medium-High | 5-8 days |
| 4 | 0 | 5 | ~350 | High | 5-8 days |
| **Total** | **17** | **34** | **~4,710** | | **~3-4 weeks** |

> Wave 1 and Wave 2 increases reflect Shape Up methodology additions from PR #7.

---

## What We're NOT Doing (and Why)

| Pattern | Decision | Rationale |
|---------|----------|-----------|
| OpenAI's layered architecture enforcement | SKIP | We don't control user's architecture; Iron Laws serve this purpose |
| Stripe's 400+ MCP tools | SKIP | Tidewave + CLI tools cover our needs |
| Stripe's pre-warmed devboxes | SKIP | Not applicable to plugin architecture |
| Anthropic's Puppeteer browser automation | SKIP | Claude Code is CLI-only; use `project_eval` + Wallaby/Playwright instead |
| `/phx:queue` (batch multiple unattended tasks) | DEFER | Wait to see if `--unattended` adoption justifies queuing |
| Adaptive defaults (ML on historical runs) | DEFER | Need usage data first |
| Slack/Discord integration for unattended | DEFER | Nice-to-have, not core |
| Shape Up letter notation (R0, S-A, C1...) | SKIP | Decision council handles this more efficiently; notation adds learning curve |
| Mermaid diagrams as primary plan output | SKIP | Plan checkboxes → executable tasks is more useful for development |
| `/phx:map` affordance mapping skill | DEFER | Valuable for complex LiveView flows but separate scope; revisit post-Wave 4 |

---

## Success Criteria

After all 4 waves:

1. **Mistake-driven loop**: >50% of BLOCKERs and DEAD-ENDs result in compound docs (vs ~0% today)
2. **Plan quality**: Users iterate 2-4 annotation cycles before work (vs 0 today)
3. **Fix-retry reduction**: 30-50% fewer compile/credo retry cycles due to remediation hints
4. **Plan integrity**: Zero plan corruption incidents during `/phx:full` (JSON sidecar catches mismatches)
5. **Verification depth**: Runtime smoke tests catch bugs that unit tests miss (Tier A)
6. **Entropy awareness**: Quality drift detected within 1 session (vs never today)
7. **Unattended capability**: Well-scoped tasks complete without human interaction
8. **Requirements coverage**: Every plan with 3+ tasks has an explicit Requirements table (vs 0% today)
9. **Vertical slicing**: Every plan phase has a demo statement — no purely horizontal phases (vs unchecked today)
10. **Decision visibility**: Contested decisions produce fit-check matrix (vs prose-only council output today)

---

## Appendix: Source Articles

1. [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — Anthropic
2. [How I Use Claude Code](https://boristane.com/blog/how-i-use-claude-code/) — Boris Tane
3. [The Emerging "Harness Engineering" Playbook](https://www.ignorance.ai/p/the-emerging-harness-engineering) — Charlie Guo
4. [Harness Engineering: Leveraging Codex](https://openai.com/index/harness-engineering/) — OpenAI
5. [Minions: Stripe's One-Shot Coding Agents](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents) — Stripe
6. [My AI Adoption Journey](https://mitchellh.com/writing/my-ai-adoption-journey) — Mitchell Hashimoto
7. [Harness Engineering (Exploring Gen AI)](https://martinfowler.com/articles/exploring-gen-ai/harness-engineering.html) — Böckeler / Martin Fowler
8. [rjs/shaping-skills](https://github.com/rjs/shaping-skills) — Shape Up methodology plugin (analyzed in PR #7)

## Appendix: PR #7 Integration Summary

The following items were incorporated from the [shaping-skills analysis](https://github.com/oliver-kriska/claude-elixir-phoenix/pull/7) (Shape Up methodology by rjs):

| PR #7 Idea | Incorporated As | Wave |
|-------------|----------------|------|
| Source material capture | 1A: Source section in plan.md template | 1 |
| Demo statements / vertical slicing | 1D: Demo statements for plan phases | 1 |
| Naming test for design smells | 1E: Naming test for review agents | 1 |
| Ripple-check hook | 1F: Plan ripple-check hook (precursor to 3A/3B) | 1 |
| Requirements extraction (R1, R2...) | 2B+: Requirements extraction step | 2 |
| Fit-check matrix (R × S grid) | 2B++: Fit-check matrix for contested decisions | 2 |
| `/phx:map` affordance mapping | DEFERRED: Separate scope, post-Wave 4 | — |
| Shape letter notation | NOT ADOPTED: Decision council handles this | — |
| Mermaid diagrams as primary output | NOT ADOPTED: Checkboxes more actionable | — |
