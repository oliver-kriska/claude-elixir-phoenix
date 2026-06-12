#!/usr/bin/env python3
"""Autoresearch iteration wrapper — single command replaces 5+ manual steps.

Inspired by pi-autoresearch's typed MCP tools (init/run/log), adapted for
our deterministic scorer + git state machine.

Usage:
    # Score a skill and compare against baseline
    python3 lab/autoresearch/scripts/run-iteration.py score <skill-name>

    # Evaluate mutation: score + checks + compare + decide keep/revert
    python3 lab/autoresearch/scripts/run-iteration.py eval <skill-name> [--hypothesis "..."]

    # Keep current changes (commit + journal + state update)
    python3 lab/autoresearch/scripts/run-iteration.py keep <skill-name> <dimension> <old> <new> --desc "..." [--asi '{"key": "val"}']

    # Revert current changes (git checkout + journal)
    python3 lab/autoresearch/scripts/run-iteration.py revert <skill-name> <dimension> <old> <new> --desc "..." [--asi '{"key": "val"}']

    # Find the weakest skill+dimension
    python3 lab/autoresearch/scripts/run-iteration.py target [--strategy targeted|sweep|random]

    # Show current state summary
    python3 lab/autoresearch/scripts/run-iteration.py status
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, PROJECT_ROOT)

from lab.eval.scorer import score_skill, find_eval, find_all_skills, PLUGIN_ROOT
from lab.eval.schemas import EvalDefinition
from lab.eval.triggers.deviation_classifier import RESULTS_DIR as TRIGGER_RESULTS_DIR
from lab.eval.triggers.deviation_types import DeviationType, TriggerDeviation

RESULTS_FILE = os.path.join(PROJECT_ROOT, "lab", "autoresearch", "results.jsonl")
STATE_FILE = os.path.join(PROJECT_ROOT, "lab", "autoresearch", "autoresearch.md")
CHECKS_SCRIPT = os.path.join(PROJECT_ROOT, "lab", "autoresearch", "scripts", "checks.sh")


def load_deviations(skill_name: str) -> list[TriggerDeviation]:
    """Read cached trigger deviations for one skill. Returns [] if no cache."""
    path = os.path.join(TRIGGER_RESULTS_DIR, f"{skill_name}.json")
    if not os.path.isfile(path):
        return []
    with open(path) as f:
        data = json.load(f)
    return [TriggerDeviation.from_dict(d) for d in data.get("deviations", [])]


def pick_dominant_deviation(deviations: list[TriggerDeviation]) -> TriggerDeviation | None:
    """Pick the deviation that should drive the next mutation.
    Priority: high severity > medium > low, then most common type."""
    if not deviations:
        return None
    high = [d for d in deviations if d.severity.value == "high"]
    pool = high or deviations
    # Group by type, pick most common
    from collections import Counter
    type_counts = Counter(d.deviation_type for d in pool)
    dominant_type, _ = type_counts.most_common(1)[0]
    # Return first deviation of that type (preserves competing_skill / matched_keywords)
    for d in pool:
        if d.deviation_type == dominant_type:
            return d
    return pool[0]


def score_one(skill_name: str) -> dict:
    """Score a single skill, return full result dict."""
    skill_path = os.path.join(PLUGIN_ROOT, "skills", skill_name, "SKILL.md")
    eval_path = find_eval(skill_name)
    eval_def = EvalDefinition.from_file(eval_path) if eval_path else None
    result = score_skill(skill_path, eval_def)
    return result.to_dict()


def score_all() -> dict[str, dict]:
    """Score all skills, return {name: result_dict}."""
    results = {}
    for skill_path in find_all_skills():
        name = os.path.basename(os.path.dirname(skill_path))
        eval_path = find_eval(name)
        eval_def = EvalDefinition.from_file(eval_path) if eval_path else None
        result = score_skill(skill_path, eval_def)
        results[name] = result.to_dict()
    return results


def run_checks(skill_name: str) -> tuple[bool, str]:
    """Run structural checks. Returns (passed, output)."""
    if not os.path.isfile(CHECKS_SCRIPT):
        return True, "No checks.sh found — skipping"
    try:
        result = subprocess.run(
            ["bash", CHECKS_SCRIPT, skill_name],
            capture_output=True, text=True, timeout=30, cwd=PROJECT_ROOT
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "CHECKS TIMEOUT after 30s"
    except Exception as e:
        return False, f"CHECKS ERROR: {e}"


def append_journal(entry: dict):
    """Append one JSONL entry to results file."""
    with open(RESULTS_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def read_journal_tail(n: int = 5) -> list[dict]:
    """Read last N journal entries."""
    if not os.path.isfile(RESULTS_FILE):
        return []
    entries = []
    with open(RESULTS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries[-n:]


def get_iteration_count() -> int:
    """Count total iterations from journal."""
    if not os.path.isfile(RESULTS_FILE):
        return 0
    count = 0
    with open(RESULTS_FILE) as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def git_commit(skill_name: str, message: str) -> bool:
    """Git add + commit for a skill directory."""
    skill_dir = os.path.join("plugins", "elixir-phoenix", "skills", skill_name)
    try:
        subprocess.run(["git", "add", skill_dir], check=True, capture_output=True, cwd=PROJECT_ROOT)
        subprocess.run(["git", "commit", "-m", message], check=True, capture_output=True, cwd=PROJECT_ROOT)
        return True
    except subprocess.CalledProcessError as e:
        print(f"GIT ERROR: {e.stderr.decode()}", file=sys.stderr)
        return False


def git_revert(skill_name: str) -> bool:
    """Git checkout to revert skill changes."""
    skill_dir = os.path.join("plugins", "elixir-phoenix", "skills", skill_name)
    try:
        subprocess.run(["git", "checkout", "--", skill_dir], check=True, capture_output=True, cwd=PROJECT_ROOT)
        return True
    except subprocess.CalledProcessError as e:
        print(f"GIT REVERT ERROR: {e.stderr.decode()}", file=sys.stderr)
        return False


def find_weakest(strategy: str = "targeted") -> dict | None:
    """Find weakest skill+dimension. Returns {skill, dimension, score, composite, mode}.

    Mode is "structural" for dimension scores < 1.0, or "tournament" when all
    structural dimensions are 1.0 but trigger accuracy is below threshold.
    Returns None when everything is perfect.
    """
    all_scores = score_all()

    if strategy == "targeted":
        # First check for structural weaknesses
        weakest = None
        for name, data in all_scores.items():
            for dim_name, dim_data in data["dimensions"].items():
                if dim_data["score"] < 1.0:
                    if weakest is None or dim_data["score"] < weakest["dim_score"]:
                        weakest = {
                            "skill": name,
                            "dimension": dim_name,
                            "dim_score": dim_data["score"],
                            "composite": data["composite"],
                            "mode": "structural",
                            "failing_checks": [
                                a["desc"] for a in dim_data["assertions"] if not a["passed"]
                            ],
                        }
        if weakest:
            return weakest

        # All structural perfect — check trigger accuracy
        try:
            from lab.tournament.description_tournament import find_weak_skills
            weak = find_weak_skills(threshold=0.75)
            if weak:
                skill_name, accuracy = weak[0]  # Worst first
                target = {
                    "skill": skill_name,
                    "dimension": "trigger_accuracy",
                    "dim_score": accuracy,
                    "composite": 1.0,
                    "mode": "tournament",
                    "failing_checks": [f"trigger accuracy {accuracy:.0%} < 75%"],
                }
                # Augment with deviation taxonomy — drives mutation strategy
                deviations = load_deviations(skill_name)
                dominant = pick_dominant_deviation(deviations)
                if dominant:
                    target["deviation_type"] = dominant.deviation_type.value
                    target["severity"] = dominant.severity.value
                    target["fix_hint"] = dominant.fix_hint
                    target["competing_skill"] = dominant.competing_skill
                    target["matched_keywords"] = list(dominant.matched_keywords)
                    target["strategy"] = _strategy_for(dominant.deviation_type)
                    target["deviation_count"] = len(deviations)
                return target
        except ImportError:
            pass

        return None  # All perfect

    elif strategy == "sweep":
        for name in sorted(all_scores.keys()):
            data = all_scores[name]
            if data["composite"] < 1.0:
                # Find weakest dimension for this skill
                worst_dim = min(
                    data["dimensions"].items(),
                    key=lambda x: x[1]["score"]
                )
                return {
                    "skill": name,
                    "dimension": worst_dim[0],
                    "dim_score": worst_dim[1]["score"],
                    "composite": data["composite"],
                    "mode": "structural",
                    "failing_checks": [
                        a["desc"] for a in worst_dim[1]["assertions"] if not a["passed"]
                    ],
                }
        return None  # All perfect

    elif strategy == "random":
        import random
        below = [(n, d) for n, d in all_scores.items() if d["composite"] < 1.0]
        if not below:
            return None
        name, data = random.choice(below)
        dims_below = [(dn, dd) for dn, dd in data["dimensions"].items() if dd["score"] < 1.0]
        if not dims_below:
            return None
        dim_name, dim_data = random.choice(dims_below)
        return {
            "skill": name,
            "dimension": dim_name,
            "dim_score": dim_data["score"],
            "composite": data["composite"],
            "mode": "structural",
            "failing_checks": [a["desc"] for a in dim_data["assertions"] if not a["passed"]],
        }

    return None


def cmd_score(args):
    """Score a skill and print result."""
    result = score_one(args.skill)
    print(json.dumps({
        "skill": args.skill,
        "composite": result["composite"],
        "dimensions": {k: v["score"] for k, v in result["dimensions"].items()},
    }))


def cmd_eval(args):
    """Evaluate mutation: score + checks + compare against previous."""
    # Score
    result = score_one(args.skill)
    new_composite = result["composite"]

    # Run checks
    checks_passed, checks_output = run_checks(args.skill)

    # Read previous best from journal
    journal = read_journal_tail(50)
    prev_best = 0.0
    for entry in journal:
        if entry.get("skill") == args.skill and entry.get("kept"):
            prev_best = max(prev_best, entry.get("new_composite", 0))
    if prev_best == 0.0:
        # No prior journal entry — use current score as baseline comparison
        # (caller should have scored before mutation)
        prev_best = new_composite

    improved = new_composite >= prev_best
    verdict = "KEEP" if improved and checks_passed else "REVERT"
    reason = ""
    if not checks_passed:
        verdict = "REVERT"
        reason = f"checks failed: {checks_output}"
    elif not improved:
        reason = f"regression: {prev_best:.3f} -> {new_composite:.3f}"

    output = {
        "skill": args.skill,
        "composite": new_composite,
        "previous_best": prev_best,
        "delta": round(new_composite - prev_best, 4),
        "checks_passed": checks_passed,
        "checks_output": checks_output if not checks_passed else "PASSED",
        "verdict": verdict,
        "reason": reason,
        "dimensions": {k: round(v["score"], 4) for k, v in result["dimensions"].items()},
        "failing": [
            {"dim": k, "check": a["desc"], "evidence": a["evidence"][:80]}
            for k, v in result["dimensions"].items()
            for a in v["assertions"] if not a["passed"]
        ],
    }
    print(json.dumps(output))


def cmd_keep(args):
    """Keep mutation: commit + journal + state."""
    iteration = get_iteration_count() + 1
    msg = f"autoresearch: {args.skill} {args.dimension} {args.old}->{args.new}"

    if not git_commit(args.skill, msg):
        print(json.dumps({"error": "git commit failed"}))
        sys.exit(1)

    asi = {}
    if args.asi:
        try:
            asi = json.loads(args.asi)
        except json.JSONDecodeError:
            asi = {"raw": args.asi}

    entry = {
        "iteration": iteration,
        "skill": args.skill,
        "dimension": args.dimension,
        "old_composite": float(args.old),
        "new_composite": float(args.new),
        "kept": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "description": args.desc,
        "asi": asi,
    }
    if args.deviation_type:
        entry["deviation_type"] = args.deviation_type
    if args.strategy_applied:
        entry["strategy_applied"] = args.strategy_applied
    append_journal(entry)
    print(json.dumps({"status": "kept", "iteration": iteration, "commit_msg": msg}))


def cmd_revert(args):
    """Revert mutation: git checkout + journal."""
    iteration = get_iteration_count() + 1

    git_revert(args.skill)

    asi = {}
    if args.asi:
        try:
            asi = json.loads(args.asi)
        except json.JSONDecodeError:
            asi = {"raw": args.asi}

    entry = {
        "iteration": iteration,
        "skill": args.skill,
        "dimension": args.dimension,
        "old_composite": float(args.old),
        "new_composite": float(args.new),
        "kept": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "description": args.desc,
        "asi": asi,
    }
    if args.deviation_type:
        entry["deviation_type"] = args.deviation_type
    if args.strategy_applied:
        entry["strategy_applied"] = args.strategy_applied
    append_journal(entry)
    print(json.dumps({"status": "reverted", "iteration": iteration}))


def cmd_target(args):
    """Find weakest skill+dimension."""
    if getattr(args, "check_retention", False):
        from lab.autoresearch.retention import is_converged
        if is_converged(streak=args.retention_streak):
            print(json.dumps({
                "status": "retention_converged",
                "message": "AUTORESEARCH_COMPLETE_VIA_RETENTION",
            }))
            return
    target = find_weakest(args.strategy)
    if target is None:
        print(json.dumps({"status": "all_perfect", "message": "AUTORESEARCH_COMPLETE"}))
    else:
        print(json.dumps(target))


def cmd_retention(args):
    """Compute Retention@K, append to ledger, print status."""
    from lab.autoresearch.retention import check_retention
    result = check_retention(
        k=args.k,
        threshold=args.threshold,
        streak=args.streak,
    )
    print(json.dumps(result, indent=2 if args.pretty else None))


# Deviation-type → mutation strategy. Phase 4b dispatch table.
_STRATEGIES: dict[DeviationType, str] = {
    DeviationType.MISSING_KEYWORD: "inject_keywords",
    DeviationType.SCOPE_TOO_NARROW: "synonym_expand",
    DeviationType.DESCRIPTION_OVERLAP: "disambiguate",
    DeviationType.USE_CASE_GAP: "add_use_when",
    DeviationType.SCOPE_TOO_BROAD: "tighten_scope",
    DeviationType.UNKNOWN: "random_rewrite",
}


def _strategy_for(deviation_type: DeviationType) -> str:
    return _STRATEGIES.get(deviation_type, "random_rewrite")


def cmd_deviations(args):
    """Inspect classified trigger deviations across cached results."""
    from collections import Counter

    if args.skill:
        devs = load_deviations(args.skill)
        if not devs:
            print(json.dumps({"skill": args.skill, "deviations": []}))
            return
        dominant = pick_dominant_deviation(devs)
        out = {
            "skill": args.skill,
            "count": len(devs),
            "by_type": dict(Counter(d.deviation_type.value for d in devs)),
            "by_severity": dict(Counter(d.severity.value for d in devs)),
            "deviations": [d.to_dict() for d in devs],
            "dominant": dominant.to_dict() if dominant else None,
            "strategy": _strategy_for(dominant.deviation_type) if dominant else None,
        }
        print(json.dumps(out, indent=2 if args.pretty else None))
        return

    # Aggregate across all skills
    all_devs: dict[str, list[TriggerDeviation]] = {}
    if not os.path.isdir(TRIGGER_RESULTS_DIR):
        print(json.dumps({"error": "no_trigger_cache"}))
        sys.exit(1)
    for fname in sorted(os.listdir(TRIGGER_RESULTS_DIR)):
        if not fname.endswith(".json") or fname.startswith("_"):
            continue
        skill = fname[:-5]
        devs = load_deviations(skill)
        if devs:
            all_devs[skill] = devs

    type_counter: Counter = Counter()
    severity_counter: Counter = Counter()
    strategy_counter: Counter = Counter()
    for devs in all_devs.values():
        for d in devs:
            type_counter[d.deviation_type.value] += 1
            severity_counter[d.severity.value] += 1
            strategy_counter[_strategy_for(d.deviation_type)] += 1

    output = {
        "skills_with_deviations": len(all_devs),
        "total_deviations": sum(len(d) for d in all_devs.values()),
        "by_type": dict(type_counter),
        "by_severity": dict(severity_counter),
        "by_strategy": dict(strategy_counter),
    }
    if args.histogram:
        total = output["total_deviations"]
        print(f"Deviation distribution across {output['skills_with_deviations']} skills "
              f"({total} total):")
        for dtype in DeviationType:
            n = type_counter.get(dtype.value, 0)
            pct = (n / total * 100) if total else 0
            strat = _STRATEGIES.get(dtype, "?")
            print(f"  {dtype.value:22s} {n:4d}  ({pct:5.1f}%)  → {strat}")
    else:
        print(json.dumps(output, indent=2 if args.pretty else None))


def cmd_tournament(args):
    """Run description tournament for a skill."""
    from lab.tournament.description_tournament import (
        load_all_descriptions,
        load_trigger_prompts,
        run_tournament,
    )
    from lab.tournament.config import load_config

    skill_name = args.skill
    config = load_config()

    # Gate: structural score must be 1.000
    result = score_one(skill_name)
    if result["composite"] < 0.999:
        print(json.dumps({
            "error": "structural_gate_failed",
            "skill": skill_name,
            "composite": result["composite"],
            "message": "Skill must pass structural eval (1.000) before tournament",
        }))
        sys.exit(1)

    # Load tournament inputs
    all_descriptions = load_all_descriptions()
    trigger_prompts = load_trigger_prompts(skill_name, split="train")
    if not trigger_prompts:
        print(json.dumps({"error": "no_trigger_file", "skill": skill_name}))
        sys.exit(1)

    # Run tournament
    tournament_result = run_tournament(skill_name, all_descriptions, trigger_prompts, config)

    # Journal the result
    iteration = get_iteration_count() + 1
    entry = {
        "iteration": iteration,
        "skill": skill_name,
        "dimension": "trigger_accuracy",
        "old_composite": result["composite"],
        "new_composite": result["composite"],  # structural unchanged
        "kept": tournament_result["changed"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "description": f"tournament: {tournament_result['passes']} passes, "
                       f"converged={tournament_result['converged']}",
        "asi": {
            "type": "tournament",
            "passes": tournament_result["passes"],
            "converged": tournament_result["converged"],
            "description_before": tournament_result["description_before"],
            "description_after": tournament_result["description_after"],
            "history": tournament_result["history_summary"],
        },
    }
    append_journal(entry)

    print(json.dumps(tournament_result, indent=2))


def cmd_status(args):
    """Show current state summary."""
    all_scores = score_all()
    perfect = sum(1 for v in all_scores.values() if v["composite"] >= 0.999)
    avg = sum(v["composite"] for v in all_scores.values()) / len(all_scores) if all_scores else 0
    iterations = get_iteration_count()
    journal = read_journal_tail(5)

    below = {k: v["composite"] for k, v in all_scores.items() if v["composite"] < 0.95}

    output = {
        "total_skills": len(all_scores),
        "perfect": perfect,
        "average": round(avg, 4),
        "iterations": iterations,
        "below_threshold": below,
        "recent": [
            {"skill": e["skill"], "kept": e["kept"], "desc": e.get("description", "")[:60]}
            for e in journal
        ],
    }
    print(json.dumps(output, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Autoresearch iteration wrapper")
    sub = parser.add_subparsers(dest="command", required=True)

    # score
    p_score = sub.add_parser("score", help="Score a skill")
    p_score.add_argument("skill")
    p_score.set_defaults(func=cmd_score)

    # eval
    p_eval = sub.add_parser("eval", help="Evaluate mutation (score + checks + compare)")
    p_eval.add_argument("skill")
    p_eval.add_argument("--hypothesis", default="")
    p_eval.set_defaults(func=cmd_eval)

    # keep
    p_keep = sub.add_parser("keep", help="Keep mutation (commit + journal)")
    p_keep.add_argument("skill")
    p_keep.add_argument("dimension")
    p_keep.add_argument("old")
    p_keep.add_argument("new")
    p_keep.add_argument("--desc", required=True)
    p_keep.add_argument("--asi", default="{}")
    p_keep.add_argument("--deviation-type", default="",
                        help="Deviation type that drove this mutation (Phase 4b)")
    p_keep.add_argument("--strategy-applied", default="",
                        help="Mutation strategy applied (e.g., inject_keywords)")
    p_keep.set_defaults(func=cmd_keep)

    # revert
    p_revert = sub.add_parser("revert", help="Revert mutation (git checkout + journal)")
    p_revert.add_argument("skill")
    p_revert.add_argument("dimension")
    p_revert.add_argument("old")
    p_revert.add_argument("new")
    p_revert.add_argument("--desc", required=True)
    p_revert.add_argument("--asi", default="{}")
    p_revert.add_argument("--deviation-type", default="",
                          help="Deviation type that drove this mutation (Phase 4b)")
    p_revert.add_argument("--strategy-applied", default="",
                          help="Mutation strategy applied (e.g., inject_keywords)")
    p_revert.set_defaults(func=cmd_revert)

    # tournament
    p_tournament = sub.add_parser("tournament", help="Run description tournament for a skill")
    p_tournament.add_argument("skill")
    p_tournament.set_defaults(func=cmd_tournament)

    # target
    p_target = sub.add_parser("target", help="Find weakest skill+dimension")
    p_target.add_argument("--strategy", default="targeted", choices=["targeted", "sweep", "random"])
    p_target.add_argument("--check-retention", action="store_true",
                          help="Short-circuit to retention_converged when Retention@K stable")
    p_target.add_argument("--retention-streak", type=int, default=2,
                          help="Consecutive iterations above threshold required (default: 2)")
    p_target.set_defaults(func=cmd_target)

    # retention
    p_retention = sub.add_parser("retention",
                                  help="Compute Retention@K convergence over top-K trigger accuracy")
    p_retention.add_argument("--k", type=int, default=30, help="Top-K size (default: 30)")
    p_retention.add_argument("--threshold", type=float, default=0.9,
                              help="Retention threshold (default: 0.9)")
    p_retention.add_argument("--streak", type=int, default=2,
                              help="Consecutive iterations required for convergence (default: 2)")
    p_retention.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    p_retention.set_defaults(func=cmd_retention)

    # deviations
    p_dev = sub.add_parser("deviations", help="Inspect classified trigger deviations")
    p_dev.add_argument("--skill", help="Show deviations for one skill")
    p_dev.add_argument("--histogram", action="store_true", help="Print type histogram with strategies")
    p_dev.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    p_dev.set_defaults(func=cmd_deviations)

    # status
    p_status = sub.add_parser("status", help="Show current state")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
