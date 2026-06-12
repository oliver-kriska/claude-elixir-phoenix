"""Heuristic classifier for trigger-routing failures.

Runs on existing cached trigger results. No API calls.

Pipeline:
    classify_failures(skill_name, result_json, all_descriptions)
        → list[TriggerDeviation]
    classify_all_cached(results_dir, all_descriptions)
        → dict[skill_name, list[TriggerDeviation]]

CLI:
    python3 -m lab.eval.triggers.deviation_classifier --histogram
    python3 -m lab.eval.triggers.deviation_classifier --skill plan
    python3 -m lab.eval.triggers.deviation_classifier --reclassify
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

EVAL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(os.path.dirname(EVAL_DIR))
sys.path.insert(0, PROJECT_ROOT)

from lab.eval.triggers.deviation_types import (
    DeviationType,
    FIX_HINTS,
    Severity,
    TriggerDeviation,
)

PLUGIN_ROOT = os.path.join(PROJECT_ROOT, "plugins", "elixir-phoenix")
RESULTS_DIR = os.path.join(EVAL_DIR, "triggers", "results")

# Stopwords excluded from keyword overlap. Kept tight — domain words like
# "test", "build", "create" carry routing signal and stay in.
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "i", "if", "in", "is", "it", "its", "me", "my", "of", "on", "or",
    "out", "should", "so", "that", "the", "this", "to", "use", "want", "we",
    "what", "when", "where", "which", "with", "you", "your", "do", "does",
    "can", "how", "after", "before", "into", "via", "but", "not", "no",
})

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]+")
_USE_WHEN_RE = re.compile(r"\b[Uu]se\s+(?:when|after|for|to)\b")


def _tokenize(text: str) -> set[str]:
    """Lowercase tokens longer than 2 chars, minus stopwords."""
    return {
        t.lower()
        for t in _TOKEN_RE.findall(text)
        if len(t) > 2 and t.lower() not in _STOPWORDS
    }


def _keyword_overlap(prompt: str, description: str) -> set[str]:
    """Tokens shared between prompt and description."""
    return _tokenize(prompt) & _tokenize(description)


def _has_use_when(description: str) -> bool:
    return bool(_USE_WHEN_RE.search(description))


def _find_strongest_competitor(
    expected_desc: str,
    chosen: list[str],
    all_descriptions: dict[str, str],
) -> tuple[str | None, set[str]]:
    """Among chosen skills, find the one whose description shares most tokens
    with the expected skill's description. Returns (skill_name, shared_tokens)."""
    expected_tokens = _tokenize(expected_desc)
    best_name = None
    best_shared: set[str] = set()
    for name in chosen:
        desc = all_descriptions.get(name, "")
        if not desc:
            continue
        shared = _tokenize(desc) & expected_tokens
        if len(shared) > len(best_shared):
            best_name = name
            best_shared = shared
    return best_name, best_shared


def classify_one(
    expected_skill: str,
    expected_desc: str,
    prompt: str,
    expected: bool,
    chosen: list[str],
    all_descriptions: dict[str, str],
) -> TriggerDeviation:
    """Classify one failed trigger result. Caller filters `correct=True` cases."""

    # Rule 1: False positive — should_not_trigger but skill was chosen
    if not expected and expected_skill in chosen:
        # If other skills were also chosen, surface the strongest competitor —
        # disambiguating against THAT skill is the actionable fix path.
        other_chosen = [c for c in chosen if c != expected_skill]
        competitor, _ = _find_strongest_competitor(
            expected_desc, other_chosen, all_descriptions
        ) if other_chosen else (None, set())
        return TriggerDeviation(
            expected_skill=expected_skill,
            chosen_skills=chosen,
            prompt=prompt,
            deviation_type=DeviationType.SCOPE_TOO_BROAD,
            severity=Severity.MEDIUM,
            fix_hint=FIX_HINTS[DeviationType.SCOPE_TOO_BROAD],
            competing_skill=competitor,
            matched_keywords=sorted(_keyword_overlap(prompt, expected_desc)),
        )

    # Rule 2: False negative + competing skill chosen
    if expected and chosen and expected_skill not in chosen:
        competitor, shared = _find_strongest_competitor(
            expected_desc, chosen, all_descriptions
        )
        if competitor and len(shared) >= 2:
            return TriggerDeviation(
                expected_skill=expected_skill,
                chosen_skills=chosen,
                prompt=prompt,
                deviation_type=DeviationType.DESCRIPTION_OVERLAP,
                severity=Severity.HIGH,
                fix_hint=FIX_HINTS[DeviationType.DESCRIPTION_OVERLAP],
                competing_skill=competitor,
                matched_keywords=sorted(shared),
            )

    # Rule 3: False negative + chosen == [] (or no overlapping competitor)
    if expected and not chosen:
        prompt_in_desc = _keyword_overlap(prompt, expected_desc)
        if len(prompt_in_desc) >= 2:
            # Description had the keywords; haiku just missed it
            return TriggerDeviation(
                expected_skill=expected_skill,
                chosen_skills=chosen,
                prompt=prompt,
                deviation_type=DeviationType.MISSING_KEYWORD,
                severity=Severity.HIGH,
                fix_hint=FIX_HINTS[DeviationType.MISSING_KEYWORD],
                matched_keywords=sorted(prompt_in_desc),
            )
        # No keyword overlap → check structure first
        if not _has_use_when(expected_desc):
            return TriggerDeviation(
                expected_skill=expected_skill,
                chosen_skills=chosen,
                prompt=prompt,
                deviation_type=DeviationType.USE_CASE_GAP,
                severity=Severity.HIGH,
                fix_hint=FIX_HINTS[DeviationType.USE_CASE_GAP],
                matched_keywords=sorted(prompt_in_desc),
            )
        # Has Use-when but no keyword overlap → synonym gap
        return TriggerDeviation(
            expected_skill=expected_skill,
            chosen_skills=chosen,
            prompt=prompt,
            deviation_type=DeviationType.SCOPE_TOO_NARROW,
            severity=Severity.HIGH,
            fix_hint=FIX_HINTS[DeviationType.SCOPE_TOO_NARROW],
            matched_keywords=sorted(prompt_in_desc),
        )

    # Rule 4: should_not_trigger + chosen has other skills (not expected)
    # This is technically "correct" from the expected skill's perspective —
    # but classify_failures should not have called us with correct=True.
    return TriggerDeviation(
        expected_skill=expected_skill,
        chosen_skills=chosen,
        prompt=prompt,
        deviation_type=DeviationType.UNKNOWN,
        severity=Severity.LOW,
        fix_hint=FIX_HINTS[DeviationType.UNKNOWN],
        matched_keywords=sorted(_keyword_overlap(prompt, expected_desc)),
    )


def classify_failures(
    skill_name: str,
    result_data: dict,
    all_descriptions: dict[str, str],
) -> list[TriggerDeviation]:
    """Classify every incorrect result entry for a single skill."""
    expected_desc = all_descriptions.get(skill_name, "")
    if not expected_desc:
        return []

    deviations = []
    for entry in result_data.get("results", []):
        if entry.get("correct", True):
            continue
        deviations.append(classify_one(
            expected_skill=skill_name,
            expected_desc=expected_desc,
            prompt=entry.get("prompt", ""),
            expected=bool(entry.get("expected", False)),
            chosen=list(entry.get("chosen", [])),
            all_descriptions=all_descriptions,
        ))
    return deviations


def reclassify_cache(
    results_dir: str | None = None,
    all_descriptions: dict[str, str] | None = None,
) -> dict[str, list[TriggerDeviation]]:
    """Walk every cached trigger result, classify failures, write deviations
    back to each JSON. No API calls.

    Returns: dict[skill_name, list[TriggerDeviation]]
    """
    from lab.eval.trigger_scorer import load_all_descriptions

    results_dir = results_dir or RESULTS_DIR
    all_descriptions = all_descriptions or load_all_descriptions()

    out: dict[str, list[TriggerDeviation]] = {}
    if not os.path.isdir(results_dir):
        return out

    for fname in sorted(os.listdir(results_dir)):
        if not fname.endswith(".json") or fname.startswith("_"):
            continue
        path = os.path.join(results_dir, fname)
        with open(path) as f:
            data = json.load(f)
        skill = data.get("skill") or fname[:-5]
        deviations = classify_failures(skill, data, all_descriptions)
        out[skill] = deviations
        data["deviations"] = [d.to_dict() for d in deviations]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
    return out


def histogram(deviations_by_skill: dict[str, list[TriggerDeviation]]) -> Counter:
    """Aggregate deviation type counts across all skills."""
    counter: Counter = Counter()
    for devs in deviations_by_skill.values():
        for d in devs:
            counter[d.deviation_type.value] += 1
    return counter


def main():
    parser = argparse.ArgumentParser(description="Classify trigger-routing failures")
    parser.add_argument("--skill", help="Classify one skill's cached result")
    parser.add_argument("--reclassify", action="store_true",
                        help="Re-classify all cached results in place (writes deviations)")
    parser.add_argument("--histogram", action="store_true",
                        help="Print deviation-type distribution across all skills")
    parser.add_argument("--results-dir", help="Override results directory")
    args = parser.parse_args()

    from lab.eval.trigger_scorer import load_all_descriptions
    all_descriptions = load_all_descriptions()
    results_dir = args.results_dir or RESULTS_DIR

    if args.skill:
        path = os.path.join(results_dir, f"{args.skill}.json")
        if not os.path.isfile(path):
            print(f"No cached result at {path}", file=sys.stderr)
            sys.exit(1)
        with open(path) as f:
            data = json.load(f)
        devs = classify_failures(args.skill, data, all_descriptions)
        print(json.dumps([d.to_dict() for d in devs], indent=2))
        return

    if args.reclassify or args.histogram:
        result = reclassify_cache(results_dir, all_descriptions)
        if args.histogram:
            counts = histogram(result)
            total = sum(counts.values())
            print(f"Deviation histogram across {len(result)} skills "
                  f"({total} total failures):")
            for dtype in DeviationType:
                n = counts.get(dtype.value, 0)
                pct = (n / total * 100) if total else 0
                print(f"  {dtype.value:22s} {n:4d}  ({pct:5.1f}%)")
            unknown_pct = (counts.get("unknown", 0) / total * 100) if total else 0
            if unknown_pct > 30:
                print(f"\nWARN: 'unknown' is {unknown_pct:.1f}% — heuristics may need tightening.",
                      file=sys.stderr)
        else:
            print(f"Reclassified {len(result)} skills.")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
