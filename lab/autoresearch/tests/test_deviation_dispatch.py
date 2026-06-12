"""Tests for Phase 4b — deviation_type → mutation strategy dispatch."""

import importlib.util
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, PROJECT_ROOT)

# run-iteration.py uses a hyphen, so import via spec.
SCRIPT_PATH = os.path.join(
    PROJECT_ROOT, "lab", "autoresearch", "scripts", "run-iteration.py"
)
spec = importlib.util.spec_from_file_location("run_iteration", SCRIPT_PATH)
run_iteration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_iteration)

from lab.eval.triggers.deviation_types import DeviationType, Severity, TriggerDeviation


class TestStrategyDispatch:
    """Each deviation type maps to a distinct mutation strategy."""

    def test_missing_keyword_maps_to_inject(self):
        assert run_iteration._strategy_for(DeviationType.MISSING_KEYWORD) == "inject_keywords"

    def test_scope_too_narrow_maps_to_synonym(self):
        assert run_iteration._strategy_for(DeviationType.SCOPE_TOO_NARROW) == "synonym_expand"

    def test_description_overlap_maps_to_disambiguate(self):
        assert run_iteration._strategy_for(DeviationType.DESCRIPTION_OVERLAP) == "disambiguate"

    def test_use_case_gap_maps_to_use_when(self):
        assert run_iteration._strategy_for(DeviationType.USE_CASE_GAP) == "add_use_when"

    def test_scope_too_broad_maps_to_tighten(self):
        assert run_iteration._strategy_for(DeviationType.SCOPE_TOO_BROAD) == "tighten_scope"

    def test_unknown_falls_back_to_random(self):
        assert run_iteration._strategy_for(DeviationType.UNKNOWN) == "random_rewrite"

    def test_every_deviation_type_has_strategy(self):
        for dtype in DeviationType:
            assert run_iteration._strategy_for(dtype), f"{dtype} has no strategy"


class TestPickDominantDeviation:
    def test_returns_none_for_empty(self):
        assert run_iteration.pick_dominant_deviation([]) is None

    def test_prefers_high_severity(self):
        devs = [
            TriggerDeviation("a", [], "low prompt",
                             DeviationType.SCOPE_TOO_BROAD, Severity.MEDIUM, "h"),
            TriggerDeviation("a", [], "high prompt",
                             DeviationType.MISSING_KEYWORD, Severity.HIGH, "h"),
        ]
        dom = run_iteration.pick_dominant_deviation(devs)
        assert dom.severity == Severity.HIGH

    def test_prefers_most_common_type(self):
        devs = [
            TriggerDeviation("a", [], "p1", DeviationType.MISSING_KEYWORD, Severity.HIGH, "h"),
            TriggerDeviation("a", [], "p2", DeviationType.MISSING_KEYWORD, Severity.HIGH, "h"),
            TriggerDeviation("a", [], "p3", DeviationType.SCOPE_TOO_NARROW, Severity.HIGH, "h"),
        ]
        dom = run_iteration.pick_dominant_deviation(devs)
        assert dom.deviation_type == DeviationType.MISSING_KEYWORD


class TestLoadDeviations:
    def test_returns_empty_list_when_no_cache(self, tmp_path, monkeypatch):
        monkeypatch.setattr(run_iteration, "TRIGGER_RESULTS_DIR", str(tmp_path))
        assert run_iteration.load_deviations("nonexistent") == []
