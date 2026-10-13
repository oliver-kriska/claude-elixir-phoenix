"""Behavioral dimension: Does the skill trigger correctly for real user prompts?

Structural scoring is deterministic and therefore ignores the local, Git-ignored
trigger cache by default. Set ``EVAL_USE_TRIGGER_CACHE=1`` for an explicit local
diagnostic that incorporates cached results. Fresh paid runs are gated directly
by ``trigger_scorer.py``.
"""

import json
import os

from lab.eval.plugins import DEFAULT_PLUGIN, namespace_map, plugin_dir, plugin_root_for
from lab.eval.schemas import AssertionResult, DimensionResult, EvalDimension


TRIGGERS_RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "triggers", "results"
)
CACHE_OPT_IN_ENV = "EVAL_USE_TRIGGER_CACHE"


def _neutral(skill_name: str, evidence: str) -> DimensionResult:
    return DimensionResult(
        dimension="behavioral",
        score=1.0,
        passed=0, failed=0, total=0,
        assertions=[AssertionResult(
            id="behavioral-0",
            check_type="trigger_accuracy",
            description="Trigger cache explicitly enabled",
            passed=True,
            evidence=evidence,
        )],
    )


def cache_stem(skill_path: str) -> str:
    """Trigger cache stem: bare for phx, `{namespace}-{skill}` for other plugins (matches trigger_scorer)."""
    name = os.path.basename(os.path.dirname(skill_path))
    root = plugin_root_for(skill_path)
    if root == plugin_dir(DEFAULT_PLUGIN):
        return name
    namespace = next((ns for ns, r in namespace_map().items() if r == root), os.path.basename(root))
    return f"{namespace}-{name}"


def score(content: str, dimension: EvalDimension, skill_path: str = "", plugin_root: str = "") -> DimensionResult:
    """Score cached trigger results only after an explicit opt-in."""
    skill_name = os.path.basename(os.path.dirname(skill_path)) if skill_path else ""
    cache_path = os.path.join(TRIGGERS_RESULTS_DIR, f"{cache_stem(skill_path) if skill_path else ''}.json")

    if os.environ.get(CACHE_OPT_IN_ENV) != "1":
        return _neutral(
            skill_name,
            f"Local trigger cache disabled for deterministic scoring; set {CACHE_OPT_IN_ENV}=1 to include it",
        )

    if not os.path.isfile(cache_path):
        return _neutral(
            skill_name,
            f"No trigger cache for {skill_name} — skipping (neutral)",
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
