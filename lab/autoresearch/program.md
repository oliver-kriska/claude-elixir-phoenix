# Autoresearch Program — Elixir/Phoenix Plugin Skills

## Goals (ordered by priority)

1. Fix accuracy issues: stale cross-references, missing agents/skills
2. Improve conciseness: compress bloated sections, move detail to references/
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

## Scoring

- 8 dimensions: completeness, accuracy, conciseness, triggering, safety, clarity, specificity, **behavioral**
- Structural composite = weighted average (0.20, 0.15, 0.15, 0.10, 0.10, 0.15, 0.15)
- Behavioral (8th dimension) = haiku routing accuracy on trigger test prompts
  - Standard tier: should_trigger/should_not_trigger (threshold: 75% accuracy)
  - Hard tier: terse/typo/multi-intent/confusable prompts (threshold: 50% accuracy)
  - Scored via `trigger_scorer.py`, cached in `lab/eval/triggers/results/`
- `cmd_eval` now spot-checks behavioral accuracy for the mutated skill (~$0.01, ~30s)
- Eval definitions: `lab/eval/evals/{skill}.json` (skill-specific) or default
- Scorer: `python3 -m lab.eval.scorer {skill_path}`

## Proxy-Gold Tracking (Gao et al., ICML 2023)

The structural composite is the **proxy** reward model. Behavioral trigger
accuracy is the **gold** reward model. Per "Scaling Laws for Reward Model
Overoptimization," proxy reward increases monotonically while gold reward
peaks then declines when overoptimized.

- `cmd_eval` logs both `proxy_score` and `gold_score` in output
- REVERT if behavioral accuracy drops below 60%
- REVERT if proxy improves but behavioral regresses by >10% (divergence)
- SPIN convergence: warn when proxy delta < 0.001 for 5+ iterations

## Keep Threshold

Keep if `new_composite >= previous_best_composite`.
On exact tie: keep (prefer newer — likely simpler or more accurate).

## Stop Conditions

- All target skills at composite >= 0.95
- 10 consecutive discards on same skill -> skip that skill
- 50 total consecutive discards -> stop entirely
- Human interrupts (Ctrl+C)

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
