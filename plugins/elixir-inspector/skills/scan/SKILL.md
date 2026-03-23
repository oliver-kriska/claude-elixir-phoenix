---
name: ei:scan
description: >
  Comprehensive Elixir/Phoenix codebase analysis across 6 layers (git history, PRs, code patterns,
  .claude config, Claude sessions, architecture). Discovers recurring bug patterns, naming drift,
  authorization gaps, architecture violations, and generates Credo checks, CI steps, and CLAUDE.md
  rules. Use --deep for 20 sub-agent supervision tree producing 100+ patterns with cross-layer
  correlation. Use --pr NUMBER for targeted PR-scoped scanning (~2 min). ALWAYS use this skill when
  the user wants to understand their codebase health, find what keeps breaking, audit code quality,
  discover implicit team conventions, detect architecture drift, identify tech debt priorities, or
  asks what should we improve, where are the weak points, why do the same bugs keep coming back,
  how healthy is this project. Also trigger on scan, analyze the codebase, audit, inspect, find
  patterns, recurring issues, code quality overview, project health check, what conventions are we
  following. Do NOT trigger for specific bug fixes, single feature implementations, or deployment
  tasks.
argument-hint: "[--quick|--full|--deep|--fresh|--pr NUMBER|--gate measure|check|--focus=LAYER|--since=DATE]"
---

# Elixir Inspector — Scan

Analyze the current project across 6 layers using deterministic scripts + LLM interpretation.

```
/ei:scan              # Standard 6-layer analysis (~50 findings, 10 min)
/ei:scan --quick      # Quick: Layers 1, 3, 6 only (~3 min)
/ei:scan --full       # Standard + deep domain analysis on Layer 3
/ei:scan --deep       # Deep: 20 sub-agents, 100+ findings, 60-100KB detailed report (~20 min)
/ei:scan --pr 42      # PR-scoped: only changed files, 3 layers (~2 min)
/ei:scan --gate measure  # Create quality baseline for ratcheting
/ei:scan --gate check    # Check current state against baseline (CI integration)
/ei:scan --focus=prs  # Single layer (git|prs|code|config|sessions|arch)
/ei:scan --since 2025-10-01
```

## Bash Call Budget: Maximum 2

1. **Step 2**: mkdir + all scripts + size check (ONE call)
2. **Step 3**: Session scorers + aggregate (ONE call, only if ccrider available)

Do NOT use Bash for prerequisites, file checks, merge, or any utility — use Read/Glob.

## Workflow

### Step 1: Setup (NO Bash calls)

Parse `$ARGUMENTS` for flags: `--quick`, `--full`, `--deep`, `--fresh`, `--pr NUMBER`, `--gate`, `--focus=LAYER`, `--since DATE`.
Derive `SCRIPTS` from skill base directory: `{base_directory}/../../scripts`.

If `--gate`: jump to Gate Mode (bottom of this document).
If `--pr NUMBER`: jump to PR Mode (bottom of this document).

Tell user: "Starting Inspector scan{mode_label}. You'll need to approve one Bash command."

**Track timing**: note the current time as `scan_start`. You'll report duration at the end.

### Step 2: Run All Scripts (ONE Bash Command)

**Script cache**: Before running scripts, check if `.claude/inspector/layers/*.json` files
exist and were modified within the last hour (use Read tool to check file). If ALL files
exist and are recent, skip script execution and tell user: "Using cached data from {time}.
Use --fresh to force re-run." Only skip if NO --fresh flag in arguments.

**For `--deep` mode**: add temporal-coupling.py and hotspot-score.py to the same Bash call:

```bash
mkdir -p .claude/inspector/layers/sessions .claude/inspector/layers/{L1,L2,L3,L4,L5,L6} && S="{SCRIPTS}" && P="{PROJECT_ROOT}" && python3 "$S/analyze-git-history.py" "$P" --since "{SINCE}" > .claude/inspector/layers/git-history.json 2>.claude/inspector/layers/git-history.err & python3 "$S/analyze-prs.py" "$P" --since "{SINCE}" > .claude/inspector/layers/pr-reviews.json 2>.claude/inspector/layers/pr-reviews.err & python3 "$S/analyze-code.py" "$P" --full > .claude/inspector/layers/code-docs.json 2>.claude/inspector/layers/code-docs.err & bash "$S/analyze-config.sh" "$P" > .claude/inspector/layers/claude-config.json 2>.claude/inspector/layers/claude-config.err & bash "$S/analyze-architecture.sh" "$P" > .claude/inspector/layers/architecture.json 2>.claude/inspector/layers/architecture.err & python3 "$S/temporal-coupling.py" "$P" --since "{SINCE}" > .claude/inspector/layers/temporal-coupling.json 2>.claude/inspector/layers/temporal-coupling.err & python3 "$S/hotspot-score.py" "$P" --since "{SINCE}" > .claude/inspector/layers/hotspot-score.json 2>.claude/inspector/layers/hotspot-score.err & wait && echo "Done" && wc -c .claude/inspector/layers/*.json
```

For standard mode: omit temporal-coupling.py and hotspot-score.py.
For `--quick`: only git-history, code, and architecture.

### Step 3: Session Analysis (Layer 5)

Skip if `--quick` or ccrider unavailable. MCP tools only work in main context.

**Context budget**: Each session response is 5-50KB. To avoid context exhaustion:

- Fetch max 3 sessions in `--deep` mode, max 5 in standard mode
- Use `last_n: 50` (not 200) to limit per-session size
- Write each response to file IMMEDIATELY after fetching — do NOT parse or display it

1. `mcp__ccrider__list_recent_sessions(limit: 20)` — pick top 3 non-scan sessions by message count
2. For each: `get_session_messages(session_id, last_n: 50)` → Write IMMEDIATELY to `_tmp_{ID}.json`
3. Score + aggregate in ONE Bash command:

```bash
S="{SCRIPTS}" && for f in .claude/inspector/layers/sessions/_tmp_*.json; do ID=$(basename "$f" .json | sed 's/_tmp_//'); python3 "$S/analyze-sessions.py" "$f" --session-id "$ID" > ".claude/inspector/layers/sessions/session-${ID}.json" && rm "$f"; done && python3 "$S/analyze-sessions.py" .claude/inspector/layers/sessions/ --mode aggregate > .claude/inspector/layers/sessions-summary.json
```

### Step 4: Spawn Agents

**Smart defaults**: After scripts complete, check module count from code-docs.json:

- <50 modules: tell agents "Aim for 3-8 findings, focus on critical only"
- 50-200 modules: standard "Aim for 5-15 findings"
- 200+ modules: "Aim for 10-20 findings, be thorough"
Include the project size context in each agent prompt.

**IF `--deep` mode**: Spawn 6 ORCHESTRATOR agents (each spawns sub-agents internally):

```
Agent(subagent_type="elixir-inspector:L1-orchestrator", prompt="Deep Layer 1 analysis.\nGIT_HISTORY={PROJECT_ROOT}/.claude/inspector/layers/git-history.json\nTEMPORAL_COUPLING={PROJECT_ROOT}/.claude/inspector/layers/temporal-coupling.json\nHOTSPOT_SCORE={PROJECT_ROOT}/.claude/inspector/layers/hotspot-score.json\nOUTPUT_DIR={PROJECT_ROOT}/.claude/inspector/layers/L1\nWrite consolidated findings to OUTPUT_DIR/consolidated.md", run_in_background=true)

Agent(subagent_type="elixir-inspector:L2-orchestrator", prompt="Deep Layer 2 analysis.\nPR_REVIEWS={PROJECT_ROOT}/.claude/inspector/layers/pr-reviews.json\nOUTPUT_DIR={PROJECT_ROOT}/.claude/inspector/layers/L2\nWrite consolidated findings to OUTPUT_DIR/consolidated.md", run_in_background=true)

Agent(subagent_type="elixir-inspector:L3-orchestrator", prompt="Deep Layer 3 analysis.\nCODE_DOCS={PROJECT_ROOT}/.claude/inspector/layers/code-docs.json\nOUTPUT_DIR={PROJECT_ROOT}/.claude/inspector/layers/L3\nWrite consolidated findings to OUTPUT_DIR/consolidated.md", run_in_background=true)

Agent(subagent_type="elixir-inspector:L4-orchestrator", prompt="Deep Layer 4 analysis.\nCLAUDE_CONFIG={PROJECT_ROOT}/.claude/inspector/layers/claude-config.json\nCODE_DOCS={PROJECT_ROOT}/.claude/inspector/layers/code-docs.json\nOUTPUT_DIR={PROJECT_ROOT}/.claude/inspector/layers/L4\nWrite consolidated findings to OUTPUT_DIR/consolidated.md", run_in_background=true)

Agent(subagent_type="elixir-inspector:L5-orchestrator", prompt="Deep Layer 5 analysis.\nSESSIONS={PROJECT_ROOT}/.claude/inspector/layers/sessions-summary.json\nOUTPUT_DIR={PROJECT_ROOT}/.claude/inspector/layers/L5\nWrite consolidated findings to OUTPUT_DIR/consolidated.md", run_in_background=true)

Agent(subagent_type="elixir-inspector:L6-orchestrator", prompt="Deep Layer 6 analysis.\nARCHITECTURE={PROJECT_ROOT}/.claude/inspector/layers/architecture.json\nOUTPUT_DIR={PROJECT_ROOT}/.claude/inspector/layers/L6\nWrite consolidated findings to OUTPUT_DIR/consolidated.md", run_in_background=true)
```

Skip any layer whose JSON is empty or < 10 bytes.
Wait for ALL orchestrators. Each writes its own `L{N}/consolidated.md`.

**IF standard mode** (no `--deep`): Use the existing shallow agent prompt template from `references/layer-prompts.md`. Spawn single agents per layer. After each completes, write result to `layers/{layer}.md`.

### Step 5: Merge Findings (ALWAYS run this step)

**ALWAYS run merge-findings.py** — even in deep mode. This computes ROI scores, root cause
chains, cross-layer themes, and contradictions that individual layer agents cannot produce.

```bash
python3 "{SCRIPTS}/merge-findings.py" .claude/inspector/layers/ > .claude/inspector/findings-merged.json
```

Read the merged JSON. It contains:

- `findings` with `roi_score`, `priority_score`, `related_to`, `root_cause_of`, `contradicts`, `theme`
- `top_roi` — top 5 findings by ROI (highest bang for the buck)
- `root_cause_chains` — which code findings cause which git/PR symptoms
- `themes` — grouped findings for the detailed report
- `contradictions` — rules documented but violated

### Step 6: Report Generation

Read `findings-merged.json` AND the layer .md files. Use BOTH for the report.

For `--deep`: read `L{N}/consolidated.md` for narrative detail + `findings-merged.json` for scoring/themes.
For standard: read `layers/{layer}.md` + `findings-merged.json`.

Generate TWO reports for `--deep` mode:

1. `report.md` — executive summary + dashboard
2. `detailed-report.md` — per-theme analysis (see `references/detailed-report-template.md`)

For standard mode: generate only `report.md`.

Read `references/report-template.md` for structure. Key sections:

| Section | Content |
|---------|---------|
| Executive summary | "{N} findings, {M} high, {K} automatable. Top 5 wins prevent ~{X}%." |
| Dashboard | Per-layer table with sub-analysis count (deep) or findings (standard) |
| **Top ROI fixes** | From `top_roi` in merged JSON — "fix this, prevent N recurrences" |
| Quick wins | Top 5 automatable + small effort |
| **Root cause chains** | From `root_cause_chains` — "fix L3-002 → resolves L1-003 + L2-005" |
| Structural concerns | Top 5 high severity + larger effort |
| Rule gaps | From L4: rules documented but violated |
| **How You Compare** | Reference `common-patterns.md` — "5/10 common patterns found" |
| Roadmap | Week 1 / Weeks 2-4 / Month 2+ |
| **Layer Errors** | For failed/skipped layers, read .err files and explain: "L2: GitHub API 502", "L5: 1 session (need 3+)" |
| **Scan Duration** | Calculate from scan_start: "Completed in Xm Ys (scripts: As, agents: Bs)" |

Write to `.claude/inspector/`. Present dashboard + summary to user.

**History saving** (enables `/ei:compare`): After writing reports, save a timestamped copy:

```bash
mkdir -p .claude/inspector/history/ && cp .claude/inspector/findings-merged.json .claude/inspector/history/scan-$(date +%Y-%m-%d).json
```

See `references/history-saving.md` for details.

## Gate Mode (`--gate`)

Quality gate for CI integration. NO agents needed — Python script only.

```
/ei:scan --gate measure   # Scan project, create baseline.json
/ei:scan --gate check     # Compare against baseline, exit 0 (pass) or 1 (fail)
```

Run:

```bash
python3 "{SCRIPTS}/quality-gate.py" {SUBCOMMAND} "{PROJECT_ROOT}" --baseline .claude/inspector/baseline.json
```

Present results to user. For `check`: show pass/fail per category + any regressions.

## PR Mode (`--pr NUMBER`)

Targeted scan of files changed in a specific PR. Much faster than full scan (~2 min).

1. Get changed files: `gh pr diff NUMBER --name-only` (in the ONE Bash call)
2. Run only relevant scripts:
   - git history: `--since` set to PR base branch merge-base
   - code analysis: pass changed file list (focus on those files)
   - architecture: check if changed files introduce NEW violations
3. Skip: config layer, session layer (not relevant for single PR)
4. Spawn 3 agents (L1, L3, L6) — not 6
5. Report format: "This PR introduces:" + cross-reference with existing findings

```bash
# PR mode Bash call (ONE command)
PR_FILES=$(gh pr diff {NUMBER} --name-only 2>/dev/null) && mkdir -p .claude/inspector/layers/sessions && S="{SCRIPTS}" && P="{PROJECT_ROOT}" && echo "$PR_FILES" > .claude/inspector/layers/pr-files.txt && python3 "$S/analyze-git-history.py" "$P" --since "$(git merge-base HEAD main)" > .claude/inspector/layers/git-history.json 2>.claude/inspector/layers/git-history.err & python3 "$S/analyze-code.py" "$P" --since "$(git merge-base HEAD main)" > .claude/inspector/layers/code-docs.json 2>.claude/inspector/layers/code-docs.err & bash "$S/analyze-architecture.sh" "$P" > .claude/inspector/layers/architecture.json 2>.claude/inspector/layers/architecture.err & wait && echo "Done" && wc -c .claude/inspector/layers/*.json
```

## References

- `references/finding-schema.md` — YAML frontmatter format
- `references/scoring-methodology.md` — Priority scoring formula
- `references/report-template.md` — Standard report template
- `references/detailed-report-template.md` — Deep mode comprehensive template
- `references/layer-prompts.md` — Agent mapping and session handling
- `references/history-saving.md` — Scan history for `/ei:compare`
