# Autoresearch Program — Elixir/Phoenix Plugin Skills

## Goals (ordered by priority)

1. Fix accuracy issues: stale cross-references, missing agents/skills
2. Improve conciseness: compress bloated sections, move detail to references/
   (NEVER by trimming a protected section — see "Protected Sections" below)
3. Strengthen Iron Laws: add missing prohibitions, ensure min coverage
4. Improve triggering: add domain keywords to generic descriptions
5. Fill completeness gaps: missing sections, undocumented flags
6. Improve clarity: raise action density, remove cross-section duplication
7. Improve specificity: add code examples, concrete patterns over vague guidance

## Mutable Surface (ONLY these files)

- `plugins/elixir-phoenix/skills/*/SKILL.md`
- `plugins/elixir-phoenix/skills/*/references/*.md`

## Read-Only (NEVER mutate)

- `lab/**` (eval infrastructure, this file, scripts)
- `plugins/elixir-phoenix/agents/**`
- `plugins/elixir-phoenix/hooks/**`
- `plugins/elixir-phoenix/.claude-plugin/**`
- `CLAUDE.md`
- `CHANGELOG.md`
- `README.md`

## Protected Sections (Frozen — append-only)

The `## Iron Laws` section of every SKILL.md is **slow state**: hard-won
prohibitions that must never erode. The loop MAY append a new Iron Law but MUST
NEVER delete or reword an existing one. This is a hard invariant, not a scored
tradeoff — `checks.sh` (check #7, via `scripts/protected_sections.py`) compares
the mutation against git HEAD and forces REVERT if any existing law disappears.

Rationale: SkillOpt (arXiv 2605.23904) measured that removing this fast/slow
guarantee cost 22 points on SpreadsheetBench. Conciseness gains must come from
the fast state (patterns, examples, prose), never from the protected section.

## Scoring

- 7 dimensions: completeness, accuracy, conciseness, triggering, safety, clarity, specificity
- Composite = weighted average (0.20, 0.15, 0.15, 0.10, 0.10, 0.15, 0.15)
- Eval definitions: `lab/eval/evals/{skill}.json` (skill-specific) or default
- Scorer: `python3 -m lab.eval.scorer {skill_path}`

## Keep Threshold

Keep if `new_composite >= previous_best_composite`.
On exact tie: keep (prefer newer — likely simpler or more accurate).

## Stop Conditions

### Structural mode (default)

- All target skills at composite >= 0.95
- 10 consecutive discards on same skill -> skip that skill
- 50 total consecutive discards -> stop entirely
- Human interrupts (Ctrl+C)

### Tournament mode (post-saturation)

- Activated when all structural composites >= 1.000 but trigger accuracy < 0.75
- Per-skill: incumbent A wins k=2 consecutive rounds -> converged, stop
- Per-skill: max 20 passes hard ceiling
- Global: 5 consecutive "all_perfect" target checks -> stop entirely

## Anti-Thrashing Rules

- Same skill mutated 5+ times without improvement: skip for 10 iterations
- If composite hasn't improved in 20 iterations: switch strategy
- NEVER revert a mutation that improved one dimension unless another regressed by MORE
- After a discard: analyze WHY before next attempt on same skill (ReflexiCoder)
- NEVER retry the exact same mutation type on the same section twice

## Meta-Improvement Awareness (from Hyperagents paper)

The eval framework + autoresearch loop IS a meta-improvement.
It transfers across use cases (skill improvement → user code improvement).
Do NOT accidentally simplify or remove infrastructure that enables self-improvement:

- lab/eval/ scoring (24 matchers, 8 dimensions) — the evaluation IS the value
- lab/autoresearch/scripts/ (run-iteration.py, checks.sh) — the loop IS the value
- ASI metadata in JSONL — failure context IS the value
- ideas.md backlog — deferred knowledge IS the value

When improving the autoresearch system itself, treat it as a meta-improvement:
changes to the loop/eval/scorer are higher-value than changes to individual skills.

## Simplicity Criterion

A 0.01 improvement that adds 10 lines of content? Probably not worth it.
A 0.01 improvement from removing redundancy? Definitely keep.
All else equal, shorter is better.
