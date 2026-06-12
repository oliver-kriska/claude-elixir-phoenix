"""Trigger-routing deviation taxonomy.

Inspired by Future AGI's BranchDeviation pattern (simulate/services/branch_deviation_analyzer.py).
Instead of binary pass/fail on trigger accuracy, classify *why* haiku misroutes a prompt.

Each TriggerDeviation feeds into:
- behavioral dimension (high-severity count → assertion)
- autoresearch (deviation type → mutation strategy)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DeviationType(str, Enum):
    """Why a trigger test failed. Drives autoresearch mutation strategy."""

    MISSING_KEYWORD = "missing_keyword"
    """`chosen == []`. Prompt keywords overlap with expected description but haiku
    didn't pick it up. Fix: inject the missing prompt keywords into description."""

    SCOPE_TOO_NARROW = "scope_too_narrow"
    """`chosen == []`. Prompt keywords are absent from expected description (synonym
    gap). Fix: expand description with synonyms (e.g., 'build' alongside 'create')."""

    DESCRIPTION_OVERLAP = "description_overlap"
    """Wrong skill chosen; its description shares top-3 keywords with expected
    skill. `competing_skill` names the winner. Fix: add disambiguating clause."""

    USE_CASE_GAP = "use_case_gap"
    """Expected description lacks 'Use when...' structure. Description tells WHAT
    not WHEN. Fix: enforce 'Use when...' prefix or suffix."""

    SCOPE_TOO_BROAD = "scope_too_broad"
    """False positive — `expected=False` but `chosen` contains expected_skill.
    Description triggers on prompts outside skill scope. Fix: tighten scope."""

    UNKNOWN = "unknown"
    """Heuristics couldn't classify. Flag for manual review."""


class Severity(str, Enum):
    HIGH = "high"      # Recall-impacting (false negative on a should_trigger prompt)
    MEDIUM = "medium"  # Precision-impacting (false positive)
    LOW = "low"        # Single-prompt edge case


@dataclass
class TriggerDeviation:
    """One classified trigger-routing failure."""

    expected_skill: str
    chosen_skills: list[str]
    prompt: str
    deviation_type: DeviationType
    severity: Severity
    fix_hint: str
    competing_skill: str | None = None
    matched_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_skill": self.expected_skill,
            "chosen_skills": list(self.chosen_skills),
            "prompt": self.prompt,
            "deviation_type": self.deviation_type.value,
            "severity": self.severity.value,
            "fix_hint": self.fix_hint,
            "competing_skill": self.competing_skill,
            "matched_keywords": list(self.matched_keywords),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TriggerDeviation":
        return cls(
            expected_skill=d["expected_skill"],
            chosen_skills=list(d.get("chosen_skills", [])),
            prompt=d["prompt"],
            deviation_type=DeviationType(d["deviation_type"]),
            severity=Severity(d["severity"]),
            fix_hint=d.get("fix_hint", ""),
            competing_skill=d.get("competing_skill"),
            matched_keywords=list(d.get("matched_keywords", [])),
        )


# Strategy hints surfaced to autoresearch. Phase 4b dispatches on deviation_type.
FIX_HINTS: dict[DeviationType, str] = {
    DeviationType.MISSING_KEYWORD: (
        "Inject missing prompt keywords into description (within 250-char budget)."
    ),
    DeviationType.SCOPE_TOO_NARROW: (
        "Add synonym expansion — prompt uses words absent from description."
    ),
    DeviationType.DESCRIPTION_OVERLAP: (
        "Add disambiguating clause distinguishing this skill from the competing one."
    ),
    DeviationType.USE_CASE_GAP: (
        "Add 'Use when...' clause — description states what but not when."
    ),
    DeviationType.SCOPE_TOO_BROAD: (
        "Tighten description scope — remove ambiguous trigger keywords."
    ),
    DeviationType.UNKNOWN: (
        "Heuristic could not classify — manual review recommended."
    ),
}
