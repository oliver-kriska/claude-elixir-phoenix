# Plugin Improvement Plan: Harness Engineering Patterns

**Status**: IMPLEMENTATION PLAN
**Created**: 2026-02-24
**Based on**: Deep analysis of 7 high-impact gaps (7 parallel agents, ~430k tokens of research)

---

## Overview

This plan synthesizes detailed research from 7 specialist agents, each of which read 20-40 plugin files and produced implementation specifications. The plan is organized into 4 implementation waves with concrete file changes, effort estimates, and dependencies.

---

## Wave 1: Quick Wins (Low Risk, High Impact)

**Timeline**: 1-2 days | **Files changed**: ~8 | **Lines added**: ~200

These require only text additions to existing skills — no new files, no architecture changes, no hooks.

### 1A. Mistake-Driven Feedback Loop — Suggestion Text

Add compound/learn suggestions at 3 failure recovery points.

| File | Change | Lines |
|------|--------|-------|
| `skills/work/SKILL.md` | After "With blockers:" section (~line 121), add: suggest `/phx:compound` after resolving blockers | +5 |
| `skills/work/references/error-recovery.md` | After "Recovery After BLOCKER" step 4, add step 5: "Ask user: Should I capture this fix as a lesson?" | +8 |
| `skills/review/SKILL.md` | In BLOCKED verdict section (~line 155), add: "After you fix these, run `/phx:compound` to document what you learned" | +5 |
| `agents/workflow-orchestrator.md` | In BLOCKED state handler, add: "Still compound resolved blockers + dead-ends even on partial completion" | +10 |

**Why first**: Zero risk. Purely additive text. Immediately captures ~40% more learning moments.

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

---

## Wave 2: New Capabilities (Medium Risk, High Impact)

**Timeline**: 3-5 days | **New files**: ~8 | **Modified files**: ~10 | **Lines added**: ~1,500

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

### 2B. Annotation Cycle — Full Implementation

Create the `--annotate` mode for iterative plan review.

| File | Type | Lines | Purpose |
|------|------|-------|---------|
| `skills/plan/SKILL.md` | MODIFY | +50 | Add `--annotate` mode section with syntax and workflow |
| `skills/plan/references/planning-workflow.md` | MODIFY | +80 | Add "Annotation Cycles" section with examples |
| `skills/plan/references/annotation-guide.md` | NEW | ~200 | Complete annotation reference: syntax, types, priorities, examples |

**Key design decisions**:
- Annotation syntax: `<!-- ANNOTATION: {priority} | {type} | {note} -->` (HTML comments, safe in Markdown)
- Priority: CRITICAL / HIGH / MEDIUM / LOW
- Type: TASK / SCOPE / DECISION / RISK / SPIKE / PATTERN / GENERAL
- Agent processes annotations in priority order, removes each after addressing
- Task IDs [Pn-Tm] NEVER deleted (Iron Law for annotations)
- Cycle tracking: `**Annotation Cycles**: n` in plan metadata
- Scratchpad gets `ANNOTATION CYCLE {n}` entries

**vs. `--existing`**: Annotation cycles are lightweight (no new agents spawned), fast (1-3 min per cycle). `--existing` is for deep research. Users combine both.

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
  ├── 1A: Mistake-driven suggestions ──→ immediate
  ├── 1B: Annotation UX ──→ immediate
  └── 1C: Hook tuning ──→ immediate

Wave 2 (depends on Wave 1 for annotation foundations)
  ├── 2A: Remediation patterns ──→ immediate (parallel with 2B)
  ├── 2B: Full annotation cycle ──→ depends on 1B
  └── 2C: Runtime smoke tests ──→ immediate (parallel)

Wave 3 (independent of Wave 2, but benefits from it)
  ├── 3A: JSON feature lists ──→ immediate
  ├── 3B: Entropy detection ──→ immediate
  └── 3C: E2E templates ──→ depends on 2C (smoke test patterns)

Wave 4 (depends on Waves 1-3 being stable)
  └── 4A: Unattended mode ──→ depends on 3A (JSON state), 3B (entropy), 2A (remediation)
```

---

## Total Effort Summary

| Wave | New Files | Modified Files | Lines Added | Risk | Timeline |
|------|-----------|----------------|-------------|------|----------|
| 1 | 0 | 8 | ~200 | Low | 1-2 days |
| 2 | 4 | 7 | ~1,500 | Medium | 3-5 days |
| 3 | 12 | 8 | ~2,500 | Medium-High | 5-8 days |
| 4 | 0 | 5 | ~350 | High | 5-8 days |
| **Total** | **16** | **28** | **~4,550** | | **~3-4 weeks** |

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

---

## Appendix: Source Articles

1. [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — Anthropic
2. [How I Use Claude Code](https://boristane.com/blog/how-i-use-claude-code/) — Boris Tane
3. [The Emerging "Harness Engineering" Playbook](https://www.ignorance.ai/p/the-emerging-harness-engineering) — Charlie Guo
4. [Harness Engineering: Leveraging Codex](https://openai.com/index/harness-engineering/) — OpenAI
5. [Minions: Stripe's One-Shot Coding Agents](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents) — Stripe
6. [My AI Adoption Journey](https://mitchellh.com/writing/my-ai-adoption-journey) — Mitchell Hashimoto
7. [Harness Engineering (Exploring Gen AI)](https://martinfowler.com/articles/exploring-gen-ai/harness-engineering.html) — Böckeler / Martin Fowler
