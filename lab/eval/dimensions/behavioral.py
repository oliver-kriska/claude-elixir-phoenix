"""Behavioral dimension: Does the skill trigger correctly for real user prompts?

Uses cached trigger test results from lab/eval/triggers/results/.
If no cached results exist, returns a neutral score (dimension skipped).
Run trigger_scorer.py first to populate cache.

Two tiers:
  - Standard: should_trigger / should_not_trigger (thresholds: 75% accuracy, 80% precision, 60% recall)
  - Hard: hard_should_trigger / hard_should_not_trigger (threshold: 50% accuracy)
    Hard prompts test terse, typo-laden, multi-intent, and confusable-pair routing.

Research basis:
  - CheckList (Ribeiro et al., ACL 2020) — capabilities × test types matrix
  - Proving Test Set Contamination (Oren et al., ICLR 2024) — uncontaminated negatives
  - "Not All Negatives are Equal" (Suresh & Ong, EMNLP 2021) — confusable pairs
"""

import json
import os

from lab.eval.schemas import AssertionResult, DimensionResult, EvalDimension


TRIGGERS_RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "triggers", "results"
)


def score(content: str, dimension: EvalDimension, skill_path: str = "", plugin_root: str = "") -> DimensionResult:
    """Score behavioral dimension using cached trigger results."""
    skill_name = os.path.basename(os.path.dirname(skill_path)) if skill_path else ""
    cache_path = os.path.join(TRIGGERS_RESULTS_DIR, f"{skill_name}.json")

    if not os.path.isfile(cache_path):
        # No cached results — penalize to incentivize running trigger tests
        # score=0.5 instead of 1.0: untested skills shouldn't get free behavioral points
        return DimensionResult(
            dimension="behavioral",
            score=0.5,
            passed=0, failed=1, total=1,
            assertions=[AssertionResult(
                id="behavioral-0",
                check_type="trigger_accuracy",
                description="Trigger test results cached",
                passed=False,
                evidence=f"No trigger cache for {skill_name} — run trigger_scorer.py first",
            )],
        )

    with open(cache_path) as f:
        data = json.load(f)

    assertions = []

    # --- Standard tier assertions ---

    # Use standard-tier metrics if available, fall back to combined
    standard = data.get("standard", data)

    accuracy = standard.get("accuracy", 0)
    min_accuracy = 0.75  # 6/8 correct is the minimum
    assertions.append(AssertionResult(
        id="behavioral-accuracy",
        check_type="trigger_accuracy",
        description="Standard trigger accuracy >= 75%",
        passed=accuracy >= min_accuracy,
        evidence=f"Standard accuracy: {accuracy:.0%} ({standard.get('correct', 0)}/{standard.get('total', 0)})",
    ))

    precision = standard.get("precision", 0)
    assertions.append(AssertionResult(
        id="behavioral-precision",
        check_type="trigger_precision",
        description="Standard trigger precision >= 80%",
        passed=precision >= 0.80,
        evidence=f"Standard precision: {precision:.0%} (TP={standard.get('tp', 0)}, FP={standard.get('fp', 0)})",
    ))

    recall = standard.get("recall", 0)
    assertions.append(AssertionResult(
        id="behavioral-recall",
        check_type="trigger_recall",
        description="Standard trigger recall >= 60%",
        passed=recall >= 0.60,
        evidence=f"Standard recall: {recall:.0%} (TP={standard.get('tp', 0)}, FN={standard.get('fn', 0)})",
    ))

    # --- Hard tier assertions (CheckList-inspired) ---
    # Lower thresholds: hard prompts are deliberately adversarial
    # Neutral if no hard prompts exist yet (don't penalize)

    hard = data.get("hard")
    if hard and hard.get("total", 0) > 0:
        hard_accuracy = hard.get("accuracy", 0)
        assertions.append(AssertionResult(
            id="behavioral-hard-accuracy",
            check_type="trigger_hard_accuracy",
            description="Hard trigger accuracy >= 50%",
            passed=hard_accuracy >= 0.50,
            evidence=f"Hard accuracy: {hard_accuracy:.0%} ({hard.get('correct', 0)}/{hard.get('total', 0)})",
        ))

        hard_recall = hard.get("recall", 0)
        assertions.append(AssertionResult(
            id="behavioral-hard-recall",
            check_type="trigger_hard_recall",
            description="Hard trigger recall >= 40%",
            passed=hard_recall >= 0.40,
            evidence=f"Hard recall: {hard_recall:.0%} (TP={hard.get('tp', 0)}, FN={hard.get('fn', 0)})",
        ))

    return DimensionResult.from_assertions("behavioral", assertions)
