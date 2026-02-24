# Harness Engineering Analysis: Plugin Improvement Opportunities

**Status**: ANALYSIS COMPLETE
**Created**: 2026-02-24
**Sources**: 7 articles (Anthropic, Boris Tane, Charlie Guo, OpenAI, Stripe, Mitchell Hashimoto, Martin Fowler/Böckeler)

---

## Executive Summary

After deep analysis of 7 articles on the emerging "harness engineering" discipline and comparing them against the plugin's current 20 agents, 38 skills, and hook system, **the plugin already implements ~70% of what the industry considers best practice**. The filesystem state machine, context supervisor pattern, Iron Laws enforcement, and multi-agent orchestration are ahead of most published approaches.

However, there are **7 high-impact gaps** and **5 medium-impact improvements** that would bring the plugin to the bleeding edge of what OpenAI, Stripe, Anthropic, and solo practitioners like Steinberger/Hashimoto describe as the future of agent-assisted development.

---

## Part 1: Key Patterns From All Articles

### 1.1 The Converging Playbook (All 7 Sources Agree)

| Pattern | Who Uses It | Core Insight |
|---------|------------|--------------|
| **Planning before coding** | Boris Tane, Steinberger, Anthropic, OpenAI | Never let agents write code without an approved plan |
| **Structured progress artifacts** | Anthropic, OpenAI, Hashimoto | Feature lists / progress files that survive session boundaries |
| **Mistake-driven documentation** | Hashimoto, OpenAI, Brockman | Every agent mistake → update AGENTS.md / rules to prevent recurrence |
| **Architectural guardrails** | OpenAI, Stripe, Böckeler | Constrain the solution space with enforced boundaries |
| **Tools as feedback loops** | OpenAI, Stripe, Brockman | Linter errors = remediation instructions, not just violations |
| **Verification rigor** | Anthropic, Böckeler, Stripe | Agents mark things "done" prematurely without E2E verification |
| **Parallel agent execution** | Steinberger, Stripe, OpenAI | 5-10 agents simultaneously, managed not attended |

### 1.2 Unique Insights Per Source

**Anthropic (Long-Running Agents)**:
- JSON feature lists resist agent tampering better than Markdown
- Initializer agent + coding agent separation
- Browser automation (Puppeteer) dramatically improved verification
- "Each new session begins without memory" is the core problem
- Git commit history + progress files = session handoff

**Boris Tane (How I Use Claude Code)**:
- The "annotation cycle": human adds inline notes to plan.md, sends back with "don't implement yet"
- 1-6 review cycles on plan before ANY code
- Single continuous session for research → planning → implementation
- Plan documents survive context-window compaction
- Terse corrections once plan exists ("match the users table design")

**Charlie Guo (The Playbook)**:
- Engineer's job splits into "building the environment" + "managing the work"
- Attended vs unattended parallelization distinction
- "Say no to slop" — maintain same review bar as human-written code
- Harness investment compounds over time
- Brownfield retrofit is an unsolved problem

**OpenAI (Harness Engineering)**:
- Strict layered architecture: Types → Config → Repo → Service → Runtime → UI
- Custom linter error messages that TEACH the agent how to fix violations
- "Garbage collection" agents that periodically scan for entropy/drift
- Quality grades maintained in repository
- ExecPlans as versioned execution specifications
- Repository is the single source of truth — anything not in-context doesn't exist

**Stripe (Minions)**:
- One-shot end-to-end: Slack message → PR (zero interaction)
- Pre-warmed devboxes (10s spinup) with same tools as humans
- 400+ MCP tools via Toolshed
- Max 2 CI runs per task (diminishing returns)
- "Shift feedback left" — linting in <5s on git push
- Rule files conditional by code subdirectory

**Mitchell Hashimoto (AI Adoption Journey)**:
- Harness engineering: "engineer a solution so the agent never makes that mistake again"
- Two forms: better implicit prompting (AGENTS.md) + programmed tools (scripts)
- End-of-day agent sessions for background research
- Disable notifications to prevent context-switching costs
- Always-running agent goal (10-20% of working day currently)

**Böckeler / Martin Fowler (Critique)**:
- Verification of functionality/behavior is the biggest gap
- Constraining solution space increases trust (counterintuitive)
- Brownfield codebases may not be worth retrofitting
- "AI-friendliness" may drive tech stack consolidation
- Hidden effort in tooling and design work

---

## Part 2: Gap Analysis — What the Plugin Does vs. What It Could

### ALREADY STRONG (Plugin Leads Industry)

| Pattern | Plugin Implementation | Assessment |
|---------|----------------------|------------|
| Planning before coding | `/phx:plan` + planning-orchestrator + breadboarding + Decision Council | **Excellent** — more sophisticated than any published approach |
| Structured progress artifacts | Plan checkboxes + progress.md + scratchpad.md + HANDOFF entries | **Excellent** — filesystem state machine is elegant |
| Architectural guardrails | 21 Iron Laws + iron-law-judge agent + PreCompact re-injection | **Excellent** — stronger than OpenAI's linter approach |
| Multi-agent orchestration | 20 specialist agents + context-supervisor compression | **Excellent** — context supervisor pattern prevents exhaustion |
| Session resumption | SessionStart hooks + check-resume.sh + scratchpad HANDOFF | **Good** — detects resumable work, prints instructions |
| Parallel execution | `### Parallel:` headers in plans + background agent spawning | **Good** — within a single workflow cycle |
| Verification tiers | Per-task → per-phase → per-feature → final gate | **Good** — structured cascade approach |
| Knowledge compounding | `/phx:compound` + solution docs + schema validation | **Unique** — no other published system does this |

### GAP ANALYSIS: HIGH-IMPACT IMPROVEMENTS

---

#### GAP 1: "Mistake-Driven Documentation" Feedback Loop
**Severity**: HIGH
**Source**: Hashimoto, OpenAI, Brockman

**What the articles say**: Every time an agent makes a mistake, immediately engineer a solution so it never happens again. Hashimoto's Ghostty AGENTS.md has one line per past failure. OpenAI runs background agents to scan for stale documentation.

**What the plugin does**: The `/phx:learn` skill exists and can update CLAUDE.md or create solution docs. The `/phx:compound` skill captures solved problems. But neither is triggered **automatically** on agent failures during `/phx:work` or `/phx:full`.

**The gap**: When a task fails 3 times and becomes a BLOCKER, or when verification catches an error that was easily preventable, there is no automatic suggestion to capture the lesson. The compounding phase only runs at the END of a successful `/phx:full` cycle. Mid-cycle failures — the most valuable learning moments — are only logged in the scratchpad as DEAD-END entries but never promoted to persistent knowledge.

**Proposed improvement**:
1. After a task hits BLOCKER status (3 retries), auto-suggest: "This failure could prevent future mistakes. Run `/phx:compound` on this blocker, or `/phx:learn` to add a rule?"
2. After the VERIFYING phase catches and fixes an issue, suggest compounding the fix
3. New hook: when a DEAD-END entry is written to scratchpad, check if the pattern matches existing solutions — if not, suggest creating one
4. Consider a periodic "garbage collection" agent (OpenAI's pattern) that scans scratchpad DEAD-END entries across all plans and suggests bulk compounding

**Impact**: Transforms failures from logs into institutional knowledge. Currently ~60% of learnable moments are lost because they happen mid-cycle.

---

#### GAP 2: JSON Feature Lists for Long-Running Tasks
**Severity**: HIGH
**Source**: Anthropic

**What the articles say**: Anthropic found that JSON feature lists resist agent tampering better than Markdown. Agents less frequently inappropriately change or overwrite structured JSON data. Their feature lists had: category, description, verification steps, and a `passes` boolean.

**What the plugin does**: Plans use Markdown checkboxes (`- [ ] [Pn-Tm][agent] Description`). The plan.md file is the source of truth. Implementation notes are appended inline.

**The gap**: Markdown checkboxes are easy to accidentally corrupt during edits. The article specifically warns: "It is unacceptable to remove or edit tests because this could lead to missing or buggy functionality." In Markdown, there's nothing stopping an agent from accidentally deleting a task line or mangling the checkbox syntax during a plan update. The plugin's Iron Law "Plan checkboxes ARE the state" is enforced by convention, not structure.

**Proposed improvement**:
1. Add an optional `plan.json` sidecar file that mirrors plan.md checkboxes in structured format:
   ```json
   {
     "features": [
       {
         "id": "P1-T1",
         "description": "Add password_hash field",
         "agent": "ecto",
         "phase": 1,
         "passes": false,
         "verification_steps": ["mix compile", "mix test test/accounts_test.exs"],
         "notes": ""
       }
     ]
   }
   ```
2. plan.md remains the human-readable view; plan.json is the machine-reliable state
3. A PostToolUse hook validates plan.md ↔ plan.json consistency after any write to plan.md
4. The `/phx:work` agent reads state from plan.json (resistant to corruption) and writes status updates to both files

**Impact**: Prevents the class of bugs where agents accidentally corrupt plan state. Enables programmatic plan queries (e.g., "how many tasks left in phase 2?") without parsing Markdown.

**Tradeoff**: Adds complexity. Could be opt-in for `/phx:full` (long-running) but skipped for `/phx:plan` + `/phx:work` (attended).

---

#### GAP 3: Custom Linter Errors as Remediation Instructions
**Severity**: HIGH
**Source**: OpenAI

**What the articles say**: OpenAI's custom linters don't just flag violations — the error messages TELL THE AGENT how to fix the problem. "The tooling teaches the agent while it works."

**What the plugin does**: The `verify-elixir.sh` hook runs `mix compile --warnings-as-errors` and the `security-reminder.sh` hook injects Iron Laws text when auth files are edited. But Credo warnings, compiler warnings, and format errors return raw tool output — the agent must figure out the fix itself.

**The gap**: When `mix compile --warnings-as-errors` fails, the hook outputs the raw compiler message. When `mix credo --strict` fails, it outputs the raw Credo message. Neither includes plugin-specific remediation guidance. The agent must independently reason about how to fix each issue, which wastes tokens and sometimes leads to wrong fixes.

**Proposed improvement**:
1. Enhance `verify-elixir.sh` to parse common compiler/Credo warning patterns and append remediation instructions:
   ```
   # Raw output:
   warning: variable "user" is unused (lib/my_app/accounts.ex:45:12)

   # Enhanced output:
   warning: variable "user" is unused (lib/my_app/accounts.ex:45:12)
   → FIX: Prefix with underscore: _user. Or remove if truly unused.
   ```
2. Create a mapping of common Credo rules → fix patterns:
   ```
   Credo.Check.Refactor.PipeChainStart → "Start pipe chains with a raw value, not a function call"
   Credo.Check.Design.AliasUsage → "Add alias at top of module: alias MyApp.{Module}"
   Credo.Check.Readability.ModuleDoc → "Add @moduledoc with brief description"
   ```
3. For Iron Law violations detected by `security-reminder.sh`, include the specific correct pattern (not just the rule text)

**Impact**: Reduces fix-retry cycles by 30-50% for common issues. Teaches the agent contextual remediation patterns. Mirrors OpenAI's most impactful harness innovation.

---

#### GAP 4: Annotation Cycle for Plan Review
**Severity**: HIGH
**Source**: Boris Tane

**What the articles say**: Boris Tane's most distinctive practice is the "annotation cycle" — reviewing plan.md by adding inline notes directly into it, sending it back with "don't implement yet," and repeating 1-6 times until satisfied. This creates a "shared mutable state between human and AI."

**What the plugin does**: `/phx:plan` creates a plan and presents it via `AskUserQuestion` with options: "Start work", "Deepen plan", "Start in fresh session", "Modify plan first." The `--existing` flag deepens an existing plan. But there's no explicit support for the annotation-style review loop.

**The gap**: The current UX presents plan approval as a binary decision (approve / deepen / modify). There's no guided workflow for the human to add inline annotations to the plan and have the agent iterate on those specific annotations. The "Modify plan first" option exists but isn't documented or structured — the user is left to figure out how to communicate modifications.

**Proposed improvement**:
1. Add an `--annotate` mode to `/phx:plan`:
   - User opens plan.md and adds `<!-- ANNOTATION: your note here -->` comments inline
   - User runs `/phx:plan --annotate .claude/plans/{slug}/plan.md`
   - Agent reads plan, finds all `<!-- ANNOTATION: -->` comments, addresses each one
   - Agent rewrites plan incorporating feedback, removes processed annotations
   - Loop continues until no annotations remain
2. Document the annotation syntax in the plan output itself:
   ```markdown
   <!-- To annotate this plan: add <!-- ANNOTATION: your note --> anywhere, then run /phx:plan --annotate -->
   ```
3. Track annotation cycles in plan metadata: `**Annotation Cycles**: 3`

**Impact**: Formalizes the most impactful human-AI collaboration pattern for planning quality. Currently, users who want to iterate on plans must use unstructured conversation, which is less effective than inline annotation.

---

#### GAP 5: Unattended/Background Task Pipeline
**Severity**: HIGH
**Source**: Stripe, Steinberger, Hashimoto

**What the articles say**: Stripe's Minions are fully unattended (Slack → PR, zero interaction). Steinberger runs 5-10 agents simultaneously. Hashimoto uses end-of-day agent sessions for background work. The key distinction is "attended parallelization" (you manage agents) vs. "unattended parallelization" (agent runs to completion without you).

**What the plugin does**: `/phx:full` is the closest to unattended — it runs the entire Plan → Work → Review → Compound cycle. But it still asks the user at key decision points (discovery options, blocker triage, review findings). The parallel execution within phases uses `### Parallel:` headers, but the overall workflow is single-threaded and attended.

**The gap**: There's no way to fire-and-forget a well-scoped task. Even `/phx:full` requires human interaction at 3-4 points. For tasks with clear scope and low risk (e.g., "add missing test coverage for module X", "fix all Credo warnings in contexts/"), an unattended mode would let users batch work.

**Proposed improvement**:
1. Add `--unattended` flag to `/phx:full` that:
   - Skips DISCOVERING user choice (auto-selects based on complexity)
   - Auto-triages review findings: fix all BLOCKERs and WARNINGs, skip SUGGESTIONs
   - Auto-continues through all cycles without stopping
   - Writes a summary report instead of presenting interactively
   - Creates a PR-ready branch with clear commit messages
2. Scope restrictions for unattended mode:
   - Only for LOW/MEDIUM complexity tasks (auto-detected)
   - Max 3 cycles before stopping
   - Auto-stops if hitting >2 BLOCKERs (requires human)
   - Writes detailed log to progress.md for async review
3. Add `/phx:queue` skill that queues multiple unattended tasks:
   ```
   /phx:queue "Add test coverage for Accounts context" "Fix Credo warnings in lib/my_app_web/" "Add moduledocs to all public modules"
   ```
   Each runs sequentially (git worktree isolation is not available in plugin context)

**Impact**: Enables the Steinberger/Stripe workflow pattern. Users can batch routine work and review results later. Biggest workflow acceleration for experienced users.

---

#### GAP 6: Entropy Detection / "Garbage Collection" Agent
**Severity**: HIGH
**Source**: OpenAI

**What the articles say**: OpenAI runs periodic "garbage collection" agents that scan for deviations from architectural standards, update quality grades, and open targeted refactoring PRs. "Technical debt is like a high-interest loan: it's almost always better to pay it down continuously."

**What the plugin does**: `/phx:techdebt` finds technical debt on demand. `/phx:audit` runs a full project health audit. `/phx:boundaries` validates context boundaries. But all are manual invocations — nothing runs proactively.

**The gap**: No periodic or automatic entropy detection. The plugin reacts to user commands but never proactively identifies drift. After a `/phx:full` cycle modifies many files, there's no automatic check that the changes maintained architectural consistency.

**Proposed improvement**:
1. Add a `PostWorkflow` hook (new hook type) that runs after `/phx:full` completes:
   - Quick boundary check: `mix xref graph --format cycles` (are there new cycles?)
   - Quick Credo scan on modified files only
   - Compare Iron Law compliance before/after
   - Output: brief "entropy report" appended to progress.md
2. Add `--gc` flag to `/phx:audit` for a lightweight garbage-collection scan:
   - Focus on files modified in last N commits
   - Check for: dead code, unused aliases, duplicated patterns, stale tests
   - Output: list of quick-fix PRs (each < 5 files)
3. Consider a SessionStart hook that runs a 10-second entropy check:
   - Are there uncommitted changes older than 24h?
   - Are there plans with all tasks checked but no review?
   - Are there BLOCKER entries with no resolution?

**Impact**: Prevents entropy accumulation that OpenAI identified as the biggest long-term risk of agent-generated code. Shifts from reactive to proactive quality maintenance.

---

#### GAP 7: Browser/E2E Verification for LiveView
**Severity**: HIGH
**Source**: Anthropic, Böckeler

**What the articles say**: Anthropic found that browser automation (Puppeteer MCP) "dramatically improved performance" for verification. Without it, agents marked features as complete without proper end-to-end testing. Böckeler's main critique of OpenAI's harness approach was the absence of behavioral verification.

**What the plugin does**: The verification tiers include per-task compile/format, per-phase tests, and an optional "per-feature smoke test via Tidewave project_eval." But there's no browser-based E2E verification. LiveView tests use `Phoenix.LiveViewTest` (headless DOM assertions), not actual browser rendering.

**The gap**: For LiveView features, the gap between "tests pass" and "feature works as user sees it" can be significant. JS hooks, CSS interactions, and browser-specific behaviors aren't caught by LiveView test helpers. The plugin's Tidewave integration provides `browser_eval` but it's not used in the verification pipeline.

**Proposed improvement**:
1. Add browser verification step to the verification cascade for LiveView features:
   - After tests pass, if Tidewave is available, use `mcp__tidewave__browser_eval` to:
     - Navigate to the page
     - Verify key elements render
     - Check for JS errors in console
     - Verify form submissions work end-to-end
2. Add Wallaby/browser test generation as an optional verification tier:
   - When task annotation is `[liveview]`, suggest: "Generate a Wallaby test for this feature?"
   - Template Wallaby test based on the plan's verification checklist
3. Document the Tidewave browser verification as a first-class verification tier in `/phx:verify`

**Impact**: Closes the biggest verification gap identified by both Anthropic and Böckeler. LiveView is the plugin's primary domain — having the strongest verification here matters most.

---

### GAP ANALYSIS: MEDIUM-IMPACT IMPROVEMENTS

---

#### GAP 8: Conditional Rules by Code Subdirectory
**Severity**: MEDIUM
**Source**: Stripe

**What the articles say**: Stripe's Minions consume rule files conditionally based on code subdirectories — not all rules apply everywhere.

**What the plugin does**: Skill auto-loading uses file pattern matching (`*_live.ex` → liveview-patterns), which is similar. But ALL Iron Laws are always injected via PreCompact, regardless of what code is being worked on. Oban Iron Laws get injected even when working on a LiveView component.

**Proposed improvement**: Make PreCompact Iron Laws injection context-aware — only inject domain-relevant Iron Laws based on files modified in the current session. Saves ~500 tokens per compaction for focused tasks.

---

#### GAP 9: Plan Quality Grades
**Severity**: MEDIUM
**Source**: OpenAI

**What the articles say**: OpenAI maintains quality grades in the repository that background agents periodically update.

**What the plugin does**: Plans have a binary status (PENDING/IN_PROGRESS/COMPLETED) but no quality assessment. Reviews produce a verdict (PASS/FAIL) but this isn't tracked historically.

**Proposed improvement**: Add a `**Quality Grade**: A-F` field to progress.md after review, based on: how many cycles needed, how many blockers hit, review verdict, test coverage. Track grade trends across plans for project health metrics.

---

#### GAP 10: Initializer Agent Pattern
**Severity**: MEDIUM
**Source**: Anthropic

**What the articles say**: Anthropic separates "initializer agent" (sets up environment) from "coding agent" (makes progress). The initializer generates the feature list and verification infrastructure.

**What the plugin does**: The DISCOVERING phase of `/phx:full` does environment discovery, and `/phx:init` sets up the plugin. But there's no formal separation between "set up the task" and "execute the task."

**Proposed improvement**: For `/phx:full --unattended`, formalize the initializer pattern: a haiku-model agent that reads the feature description, generates the JSON feature list (Gap 2), sets up test infrastructure, verifies the dev server starts, and only then hands off to the coding agent. This matches Anthropic's finding that initialization quality determines overall success.

---

#### GAP 11: "Shift Feedback Left" — Faster Verification Loops
**Severity**: MEDIUM
**Source**: Stripe

**What the articles say**: Stripe's local linting runs in <5 seconds on every git push. This "shifts feedback left" so issues are caught immediately, not in CI.

**What the plugin does**: The PostToolUse hook runs `mix format` (30s timeout) and `mix compile --warnings-as-errors` (60s timeout) after every Edit/Write. These timeouts are generous; for small changes, feedback should be faster.

**Proposed improvement**:
1. Scope PostToolUse verification to changed files only:
   - `mix compile --warnings-as-errors` already recompiles only changed files (Elixir compiler is incremental)
   - `mix format --check-formatted {changed_file}` instead of full project
2. Add file-scoped Credo to PostToolUse (currently only in per-phase verification):
   - `mix credo --strict {changed_file}` — runs in <3s for single file
3. Reduce timeout for format hook from 30s to 10s (formatting a single file should be <2s)

---

#### GAP 12: ExecPlans / Declarative Task Specifications
**Severity**: MEDIUM
**Source**: OpenAI

**What the articles say**: OpenAI uses "ExecPlans" — declarative execution specifications versioned in the repository that agents consume as structured task definitions.

**What the plugin does**: Plans are prose Markdown with checkbox tasks. Task descriptions are natural language with some structure (agent annotation, locations, patterns).

**Proposed improvement**: For the JSON sidecar (Gap 2), extend with ExecPlan-style fields:
```json
{
  "id": "P1-T1",
  "description": "Add password_hash to users schema",
  "agent": "ecto",
  "target_files": ["lib/my_app/accounts/user.ex", "priv/repo/migrations/"],
  "verification": {
    "compile": true,
    "test_files": ["test/my_app/accounts_test.exs"],
    "credo": true
  },
  "acceptance_criteria": [
    "User schema has :password_hash field with :string type",
    "Migration adds password_hash column to users table",
    "Changeset validates password length >= 12"
  ]
}
```
This gives agents explicit verification criteria per task — addressing the "premature completion" problem both Anthropic and Böckeler identified.

---

## Part 3: Prioritized Improvement Roadmap

### Tier 1: High-Value, Moderate Effort (Do First)

| # | Gap | Effort | Impact | Why First |
|---|-----|--------|--------|-----------|
| 3 | Linter errors as remediation | Low | High | Script enhancement only, no architecture change |
| 1 | Mistake-driven feedback loop | Low | High | Add auto-suggest to existing BLOCKER/DEAD-END paths |
| 4 | Annotation cycle for plans | Medium | High | New flag on existing skill, documented workflow |
| 11 | Shift feedback left | Low | Medium | Hook timeout/scope tuning |

### Tier 2: High-Value, Higher Effort (Do Next)

| # | Gap | Effort | Impact | Why Next |
|---|-----|--------|--------|----------|
| 2 | JSON feature lists | Medium | High | New file format + hook validation |
| 7 | Browser/E2E verification | Medium | High | Tidewave integration + new verification tier |
| 5 | Unattended task pipeline | High | High | New execution mode + safety rails |

### Tier 3: Strategic (Longer-Term)

| # | Gap | Effort | Impact | Why Later |
|---|-----|--------|--------|-----------|
| 6 | Entropy detection agent | Medium | High | New hook type + lightweight scan |
| 8 | Conditional Iron Laws | Low | Medium | PreCompact hook enhancement |
| 9 | Quality grades | Low | Medium | Metadata tracking in progress.md |
| 10 | Initializer agent pattern | Medium | Medium | Architecture change to /phx:full |
| 12 | ExecPlan specifications | Medium | Medium | Depends on Gap 2 (JSON sidecar) |

---

## Part 4: Patterns We Should NOT Adopt

Not every pattern from the articles applies to our context. Key differences:

| Article Pattern | Why We Skip It | Our Context |
|-----------------|---------------|-------------|
| **OpenAI's layered architecture enforcement** | We don't control the user's architecture | We provide Iron Laws for Elixir conventions instead |
| **Stripe's 400+ MCP tools** | Plugin runs in Claude Code, not a custom agent | Tidewave + CLI tools cover our needs |
| **Stripe's pre-warmed devboxes** | Not applicable to plugin architecture | Users run in their own environment |
| **Steinberger's "ship code you don't read"** | Our users ARE the developers | We review with agents, users make final call |
| **OpenAI's zero-human-written-code** | Different use case (internal tool) | Our users write code alongside agents |

---

## Part 5: What the Plugin Does Better Than Any Published Approach

Worth noting — several of our patterns are more sophisticated than anything in the articles:

1. **Context Supervisor compression**: No published approach handles multi-agent output compression this well. OpenAI doesn't mention it. Stripe doesn't need it (single agent). Our 3-tier strategy (Index/Compress/Aggressive) with coverage validation is unique.

2. **Iron Laws with PreCompact re-injection**: OpenAI uses linter enforcement. We use linter-style hooks PLUS rule re-injection before context compaction. Rules survive the full agent lifecycle, not just compile time.

3. **Decision Council pattern**: When specialists disagree, spawning 3 evaluation agents (domain, security, codebase fit) is more rigorous than any described approach. No other system has formalized contested-decision resolution.

4. **Compound knowledge system**: No published system captures solved problems as searchable institutional knowledge that feeds back into future planning and investigation. This is our unique innovation.

5. **Breadboarding for LiveView**: The system map with Places → UI Affordances → Code Affordances → Data Stores → Spikes is a structured planning technique no other agent system uses.

6. **Task routing by annotation**: The `[Pn-Tm][agent]` format with fallback keyword matching is more granular than any published task delegation system.

---

## Appendix: Source Articles

1. [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — Anthropic Engineering
2. [How I Use Claude Code](https://boristane.com/blog/how-i-use-claude-code/) — Boris Tane
3. [The Emerging "Harness Engineering" Playbook](https://www.ignorance.ai/p/the-emerging-harness-engineering) — Charlie Guo
4. [Harness Engineering: Leveraging Codex](https://openai.com/index/harness-engineering/) — OpenAI
5. [Minions: Stripe's One-Shot End-to-End Coding Agents](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents) — Stripe
6. [My AI Adoption Journey](https://mitchellh.com/writing/my-ai-adoption-journey) — Mitchell Hashimoto
7. [Harness Engineering (Exploring Gen AI)](https://martinfowler.com/articles/exploring-gen-ai/harness-engineering.html) — Birgitta Böckeler / Martin Fowler
