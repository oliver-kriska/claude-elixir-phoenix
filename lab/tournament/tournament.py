"""Core tournament engine — Borda scoring, blinding, convergence.

Adapted from NousResearch/autoreason run_v2.py. The three proven components
transfer directly: randomization, Borda aggregation, and convergence detection.
"""

import random
from dataclasses import dataclass, field


@dataclass
class TournamentState:
    """Tracks tournament progress across passes."""

    incumbent: str
    pass_number: int = 0
    consecutive_a_wins: int = 0
    history: list = field(default_factory=list)


def randomize_for_judge(versions: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Shuffle versions to neutral labels (PROPOSAL 1/2/3...).

    Each judge call gets its own randomization to prevent positional bias.

    Args:
        versions: {"A": text, "B": text, "AB": text}

    Returns:
        (formatted_text, order_map) where order_map maps "1" -> "A" etc.
    """
    items = list(versions.items())
    random.shuffle(items)

    order_map = {}
    parts = []
    for i, (label, content) in enumerate(items, 1):
        order_map[str(i)] = label
        parts.append(f"PROPOSAL {i}:\n---\n{content}\n---")

    return "\n\n".join(parts), order_map


def parse_ranking(text: str, order_map: dict[str, str]) -> list[str] | None:
    """Extract RANKING from judge response, map back to original labels.

    Scans from bottom of response upward for 'RANKING:' line, extracts
    position digits, maps through order_map to original labels (A/B/AB).

    Returns None if no valid ranking found.
    """
    valid_chars = set(order_map.keys())

    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip().lstrip("#").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            nums = [c for c in raw if c in valid_chars]
            if len(nums) >= 2 and len(set(nums)) == len(nums):
                return [order_map.get(n, n) for n in nums]

    return None


def aggregate_borda(
    rankings: list[list[str]],
    tiebreak_winner: str = "A",
) -> tuple[str, dict[str, int], list[list[str]]]:
    """Borda count over ranked lists.

    Points: N for 1st, N-1 for 2nd, ... 1 for last (where N = number of candidates).
    For 3 candidates: 3 pts for 1st, 2 for 2nd, 1 for 3rd.
    On tie, tiebreak_winner wins (conservative — favors incumbent).

    Args:
        rankings: List of rankings from judges. Each is [best, ..., worst].
            None entries are filtered out.
        tiebreak_winner: Label that wins ties (default "A" = incumbent).

    Returns:
        (winner, scores_dict, valid_rankings)
    """
    valid = [r for r in rankings if r is not None]
    if not valid:
        return tiebreak_winner, {}, []

    # Collect all labels
    labels = set()
    for r in valid:
        labels.update(r)

    n = len(labels)
    scores = {label: 0 for label in labels}

    for ranking in valid:
        for pos, label in enumerate(ranking):
            if label in scores and pos < n:
                scores[label] += (n - pos)

    # Sort by score descending, tiebreak_winner wins ties
    priority = {label: (0 if label == tiebreak_winner else i + 1)
                for i, label in enumerate(sorted(labels))}

    ranked = sorted(scores.keys(), key=lambda k: (-scores[k], priority[k]))
    winner = ranked[0]

    return winner, scores, valid


def check_convergence(state: TournamentState, k: int = 2) -> bool:
    """Check if incumbent A has won k consecutive rounds."""
    return state.consecutive_a_wins >= k
