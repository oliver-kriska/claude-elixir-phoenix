"""Retention@K convergence metric for autoresearch.

Adapted from TACO (arXiv 2604.19572) — instead of running fixed iterations,
stop when the top-K skill ranking by trigger accuracy stabilizes:

    Retention_K^(i) = |TopK(R^(i-1)) ∩ TopK(R^(i))| / K

When Retention@K ≥ threshold for `convergence_streak` consecutive iterations,
autoresearch has converged. Defaults match the paper: K=30, threshold=0.9,
streak=2.

Why one level above per-skill tournaments:
- `description_tournament.py` already has k=2 consecutive-A-wins convergence
  for a single skill description.
- Retention@K answers the orthogonal question: "Has the SET of top skills
  stopped reshuffling?" Useful for deciding when to stop running the whole
  autoresearch loop, not when one skill is done.
"""

import json
import os
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRIGGER_RESULTS_DIR = os.path.join(PROJECT_ROOT, "lab", "eval", "triggers", "results")
RETENTION_LEDGER = os.path.join(PROJECT_ROOT, "lab", "autoresearch", "retention.jsonl")


def compute_topk_by_trigger(k: int = 30) -> list[tuple[str, float]]:
    """Read cached trigger results, return top-K skills by accuracy.

    Returns list of (skill_name, accuracy) sorted descending by accuracy,
    truncated to k entries. Skills without cached results are excluded.
    Ties are broken by skill name (alphabetical) for determinism.
    """
    if not os.path.isdir(TRIGGER_RESULTS_DIR):
        return []

    scores: list[tuple[str, float]] = []
    for fname in sorted(os.listdir(TRIGGER_RESULTS_DIR)):
        if not fname.endswith(".json") or fname.startswith("_"):
            continue
        skill = fname[:-5]
        path = os.path.join(TRIGGER_RESULTS_DIR, fname)
        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        accuracy = data.get("accuracy")
        if accuracy is None:
            continue
        scores.append((skill, float(accuracy)))

    # Sort by accuracy desc, then skill name asc (deterministic tiebreak)
    scores.sort(key=lambda x: (-x[1], x[0]))
    return scores[:k]


def retention_at_k(prev_topk: list[str], curr_topk: list[str], k: int) -> float:
    """Compute Retention@K — overlap fraction between two top-K lists.

    Args:
        prev_topk: Skill names from previous iteration's top-K
        curr_topk: Skill names from current iteration's top-K
        k: Denominator (use the configured K, not actual list lengths,
            so partial pools don't inflate retention)

    Returns:
        |prev ∩ curr| / k. Always between 0.0 and 1.0.
    """
    if k <= 0:
        return 0.0
    overlap = len(set(prev_topk) & set(curr_topk))
    return overlap / k


def load_last_entry() -> dict | None:
    """Read the most recent retention.jsonl entry. None if ledger empty/missing."""
    if not os.path.isfile(RETENTION_LEDGER):
        return None
    last = None
    with open(RETENTION_LEDGER) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                last = json.loads(line)
            except json.JSONDecodeError:
                continue
    return last


def append_entry(entry: dict) -> None:
    """Append one entry to retention.jsonl (creating dir if needed)."""
    os.makedirs(os.path.dirname(RETENTION_LEDGER), exist_ok=True)
    with open(RETENTION_LEDGER, "a") as f:
        f.write(json.dumps(entry) + "\n")


def check_retention(k: int = 30, threshold: float = 0.9, streak: int = 2) -> dict:
    """Compute current retention vs previous, append to ledger, report status.

    Returns:
        {
            "k": int,
            "threshold": float,
            "top_k": list[str],         # current top-K skill names
            "retention": float | None,  # None on first iteration (no prev)
            "above_threshold": bool,
            "consecutive_above": int,   # streak count after this iteration
            "converged": bool,          # True iff streak >= configured streak
            "iteration": int,           # 1-indexed count of ledger entries
        }
    """
    curr_pairs = compute_topk_by_trigger(k=k)
    curr_topk = [s for s, _ in curr_pairs]

    prev = load_last_entry()
    prev_topk = prev["top_k"] if prev else []
    prev_consecutive = prev.get("consecutive_above", 0) if prev else 0
    prev_iteration = prev.get("iteration", 0) if prev else 0

    if prev is None:
        retention = None
        above = False
        consecutive = 0
    else:
        retention = retention_at_k(prev_topk, curr_topk, k=k)
        above = retention >= threshold
        consecutive = prev_consecutive + 1 if above else 0

    converged = consecutive >= streak

    entry = {
        "iteration": prev_iteration + 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "k": k,
        "threshold": threshold,
        "top_k": curr_topk,
        "top_k_with_accuracy": [{"skill": s, "accuracy": a} for s, a in curr_pairs],
        "retention": retention,
        "above_threshold": above,
        "consecutive_above": consecutive,
        "converged": converged,
    }
    append_entry(entry)

    return {
        "k": k,
        "threshold": threshold,
        "top_k": curr_topk,
        "retention": retention,
        "above_threshold": above,
        "consecutive_above": consecutive,
        "converged": converged,
        "iteration": entry["iteration"],
    }


def is_converged(streak: int = 2) -> bool:
    """Quick check from ledger — has retention converged?"""
    last = load_last_entry()
    if last is None:
        return False
    return last.get("consecutive_above", 0) >= streak
