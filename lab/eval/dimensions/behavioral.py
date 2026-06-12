"""Behavioral dimension: Does the skill trigger correctly for real user prompts?

Uses cached trigger test results from lab/eval/triggers/results/.
If no cached results exist, returns a neutral score (dimension skipped).
Run trigger_scorer.py first to populate cache.
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
        # No cached results — return neutral (don't penalize skills without trigger tests)
        return DimensionResult(
            dimension="behavioral",
            score=1.0,
            passed=0, failed=0, total=0,
            assertions=[AssertionResult(
                id="behavioral-0",
                check_type="trigger_accuracy",
                description="Trigger test results cached",
                passed=True,
                evidence=f"No trigger cache for {skill_name} — skipping (neutral)",
            )],
        )

    with open(cache_path) as f:
        data = json.load(f)

    assertions = []

    # Assertion 1: Overall accuracy
    accuracy = data.get("accuracy", 0)
    min_accuracy = 0.75  # 6/8 correct is the minimum
    assertions.append(AssertionResult(
        id="behavioral-accuracy",
        check_type="trigger_accuracy",
        description="Trigger accuracy >= 75%",
        passed=accuracy >= min_accuracy,
        evidence=f"Trigger accuracy: {accuracy:.0%} ({data.get('correct', 0)}/{data.get('total', 0)})",
    ))

    # Assertion 2: Precision (no false triggers)
    precision = data.get("precision", 0)
    assertions.append(AssertionResult(
        id="behavioral-precision",
        check_type="trigger_precision",
        description="Trigger precision >= 80%",
        passed=precision >= 0.80,
        evidence=f"Precision: {precision:.0%} (TP={data.get('tp', 0)}, FP={data.get('fp', 0)})",
    ))

    # Assertion 3: Recall (no missed triggers)
    recall = data.get("recall", 0)
    assertions.append(AssertionResult(
        id="behavioral-recall",
        check_type="trigger_recall",
        description="Trigger recall >= 60%",
        passed=recall >= 0.60,
        evidence=f"Recall: {recall:.0%} (TP={data.get('tp', 0)}, FN={data.get('fn', 0)})",
    ))

    # Assertion 4: High-severity deviations — diagnostic, soft cap
    deviations = data.get("deviations", []) or []
    high_severity = [d for d in deviations if d.get("severity") == "high"]
    max_high = 2
    high_evidence = (
        f"High-severity deviations: {len(high_severity)} (cap {max_high})"
        if high_severity
        else "No high-severity deviations"
    )
    if high_severity:
        types = sorted({d.get("deviation_type", "?") for d in high_severity})
        high_evidence += f" — types: {types}"
    assertions.append(AssertionResult(
        id="behavioral-deviations",
        check_type="no_high_severity_deviations",
        description=f"At most {max_high} high-severity deviations",
        passed=len(high_severity) <= max_high,
        evidence=high_evidence,
    ))

    return DimensionResult.from_assertions("behavioral", assertions)
