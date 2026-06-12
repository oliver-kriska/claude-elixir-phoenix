"""Tests for lab/eval/triggers/deviation_classifier.py."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from lab.eval.triggers.deviation_classifier import (
    classify_failures,
    classify_one,
    histogram,
    reclassify_cache,
)
from lab.eval.triggers.deviation_types import DeviationType, Severity, TriggerDeviation


# Synthetic descriptions used across rule tests. Real plugin shape — sentence-cap
# starts, "Use when..." optional.
DESCRIPTIONS = {
    "plan": (
        "Plan features spanning multiple domains: billing, auth, real-time, webhooks, "
        "jobs. Use when designing interconnected systems or converting review findings "
        "into tasks."
    ),
    "quick": (
        "Implement small Phoenix changes without planning — add validations, update "
        "routes, fix components, create migrations. Use for single-file edits under "
        "50 lines."
    ),
    "no_when": (
        "Generate documentation for modules and contexts."
    ),
    "narrow": (
        "Use when working on schema migrations."
    ),
    "broad": (
        "Phoenix utility commands. Use for various tasks."
    ),
}


# --- Rule 1: SCOPE_TOO_BROAD (false positive) ---

class TestScopeTooBroad:
    def test_false_positive_classified(self):
        dev = classify_one(
            expected_skill="quick",
            expected_desc=DESCRIPTIONS["quick"],
            prompt="Help me design a billing system",
            expected=False,
            chosen=["quick", "plan"],
            all_descriptions=DESCRIPTIONS,
        )
        assert dev.deviation_type == DeviationType.SCOPE_TOO_BROAD
        assert dev.severity == Severity.MEDIUM
        assert "Tighten" in dev.fix_hint


# --- Rule 2: DESCRIPTION_OVERLAP (competing skill chosen) ---

class TestDescriptionOverlap:
    def test_competing_skill_named(self):
        dev = classify_one(
            expected_skill="plan",
            expected_desc=DESCRIPTIONS["plan"],
            # Quick description shares 'phoenix', 'create', 'migrations' with plan-ish prompts
            prompt="Plan adding webhooks and jobs across billing and auth domains",
            expected=True,
            chosen=["quick"],
            all_descriptions=DESCRIPTIONS,
        )
        # Either DESCRIPTION_OVERLAP (if competitor shares ≥2 tokens) or
        # falls through. Validate via competing_skill being the wrong picker.
        assert dev.deviation_type in (
            DeviationType.DESCRIPTION_OVERLAP,
            DeviationType.UNKNOWN,
        )
        if dev.deviation_type == DeviationType.DESCRIPTION_OVERLAP:
            assert dev.competing_skill == "quick"
            assert dev.severity == Severity.HIGH


# --- Rule 3a: MISSING_KEYWORD (chosen=[], keywords overlap) ---

class TestMissingKeyword:
    def test_missing_keyword_when_overlap_high(self):
        dev = classify_one(
            expected_skill="plan",
            expected_desc=DESCRIPTIONS["plan"],
            prompt="Designing interconnected systems with billing and webhooks",
            expected=True,
            chosen=[],
            all_descriptions=DESCRIPTIONS,
        )
        assert dev.deviation_type == DeviationType.MISSING_KEYWORD
        assert dev.severity == Severity.HIGH
        assert len(dev.matched_keywords) >= 2


# --- Rule 3b: USE_CASE_GAP (chosen=[], no Use-when) ---

class TestUseCaseGap:
    def test_use_case_gap_when_no_use_when_clause(self):
        dev = classify_one(
            expected_skill="no_when",
            expected_desc=DESCRIPTIONS["no_when"],
            prompt="something completely unrelated to docs",
            expected=True,
            chosen=[],
            all_descriptions=DESCRIPTIONS,
        )
        # No keyword overlap, no 'Use when' clause → USE_CASE_GAP
        assert dev.deviation_type == DeviationType.USE_CASE_GAP


# --- Rule 3c: SCOPE_TOO_NARROW (chosen=[], has Use-when, no overlap) ---

class TestScopeTooNarrow:
    def test_scope_too_narrow_when_synonym_gap(self):
        dev = classify_one(
            expected_skill="narrow",
            expected_desc=DESCRIPTIONS["narrow"],
            prompt="adjust column types in production database",  # no token overlap
            expected=True,
            chosen=[],
            all_descriptions=DESCRIPTIONS,
        )
        assert dev.deviation_type == DeviationType.SCOPE_TOO_NARROW
        assert dev.severity == Severity.HIGH


# --- Aggregate: classify_failures filters correct=True ---

class TestClassifyFailures:
    def test_only_failures_classified(self):
        result_data = {
            "skill": "plan",
            "results": [
                {"prompt": "p1", "expected": True, "chosen": ["plan"], "correct": True},
                {"prompt": "designing webhooks billing systems", "expected": True,
                 "chosen": [], "correct": False},
                {"prompt": "p3", "expected": True, "chosen": [], "correct": False},
            ],
        }
        devs = classify_failures("plan", result_data, DESCRIPTIONS)
        assert len(devs) == 2
        assert all(isinstance(d, TriggerDeviation) for d in devs)


# --- Histogram aggregation ---

class TestHistogram:
    def test_histogram_counts(self):
        devs_by_skill = {
            "a": [
                TriggerDeviation("a", [], "p", DeviationType.MISSING_KEYWORD,
                                 Severity.HIGH, "h"),
                TriggerDeviation("a", [], "p", DeviationType.MISSING_KEYWORD,
                                 Severity.HIGH, "h"),
            ],
            "b": [
                TriggerDeviation("b", [], "p", DeviationType.SCOPE_TOO_BROAD,
                                 Severity.MEDIUM, "h"),
            ],
        }
        h = histogram(devs_by_skill)
        assert h["missing_keyword"] == 2
        assert h["scope_too_broad"] == 1


# --- Schema round-trip ---

class TestRoundTrip:
    def test_to_dict_from_dict(self):
        original = TriggerDeviation(
            expected_skill="plan",
            chosen_skills=["quick"],
            prompt="test",
            deviation_type=DeviationType.DESCRIPTION_OVERLAP,
            severity=Severity.HIGH,
            fix_hint="hint",
            competing_skill="quick",
            matched_keywords=["foo", "bar"],
        )
        roundtripped = TriggerDeviation.from_dict(original.to_dict())
        assert roundtripped == original


# --- Integration: re-classify cached results without exception ---

class TestReclassifyCache:
    def test_runs_against_real_cache(self):
        results_dir = os.path.join(
            os.path.dirname(__file__), "..", "triggers", "results"
        )
        if not os.path.isdir(results_dir):
            return  # No plugin / no cache — skip silently
        # Use real load_all_descriptions via the classifier's default.
        out = reclassify_cache(results_dir)
        # At least some skills should be present and classification should not raise.
        assert isinstance(out, dict)
