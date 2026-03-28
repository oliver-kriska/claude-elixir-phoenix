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

RESULTS_FILE = os.path.join(PROJECT_ROOT, "lab", "autoresearch", "results.jsonl")
STATE_FILE = os.path.join(PROJECT_ROOT, "lab", "autoresearch", "autoresearch.md")
CHECKS_SCRIPT = os.path.join(PROJECT_ROOT, "lab", "autoresearch", "scripts", "checks.sh")


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
    """Find weakest skill+dimension. Returns {skill, dimension, score, composite}."""
    all_scores = score_all()

    if strategy == "targeted":
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
                            "failing_checks": [
                                a["desc"] for a in dim_data["assertions"] if not a["passed"]
                            ],
                        }
        return weakest

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


def _spot_check_behavioral(skill_name: str) -> dict | None:
    """Spot-check behavioral trigger accuracy for one skill.

    Runs haiku-based routing test on the mutated skill only (~$0.01, ~30s).
    Returns trigger metrics dict or None if no trigger file exists.

    Research basis:
      - Gao et al. (ICML 2023) "Scaling Laws for Reward Model Overoptimization"
        — track proxy (structural) vs gold (behavioral) to detect divergence
      - Karwowski et al. (ICLR 2024) "Goodhart's Law in RL"
        — early stopping when proxy stops correlating with gold
    """
    try:
        from lab.eval.trigger_scorer import (
            load_trigger_file, score_skill_triggers, load_all_descriptions,
        )
    except ImportError:
        return None

    trigger_data = load_trigger_file(skill_name)
    if not trigger_data:
        return None

    all_descs = load_all_descriptions()
    result = score_skill_triggers(skill_name, trigger_data, all_descs)
    return {
        "accuracy": result.get("accuracy", 0),
        "precision": result.get("precision", 0),
        "recall": result.get("recall", 0),
        "standard_accuracy": result.get("standard", {}).get("accuracy"),
        "hard_accuracy": result.get("hard", {}).get("accuracy") if result.get("hard") else None,
    }


def cmd_eval(args):
    """Evaluate mutation: score + checks + compare against previous.

    Includes behavioral spot-check (proxy-gold divergence tracking)
    per Gao et al. ICML 2023.
    """
    # Score (structural — proxy metric)
    result = score_one(args.skill)
    new_composite = result["composite"]

    # Run checks
    checks_passed, checks_output = run_checks(args.skill)

    # Read previous best from journal
    journal = read_journal_tail(50)
    prev_best = 0.0
    prev_behavioral = None
    for entry in journal:
        if entry.get("skill") == args.skill and entry.get("kept"):
            prev_best = max(prev_best, entry.get("new_composite", 0))
            if entry.get("behavioral"):
                prev_behavioral = entry["behavioral"].get("accuracy")
    if prev_best == 0.0:
        prev_best = new_composite

    improved = new_composite >= prev_best
    verdict = "KEEP" if improved and checks_passed else "REVERT"
    reason = ""
    if not checks_passed:
        verdict = "REVERT"
        reason = f"checks failed: {checks_output}"
    elif not improved:
        reason = f"regression: {prev_best:.3f} -> {new_composite:.3f}"

    # Behavioral spot-check (gold metric) — Gao et al. ICML 2023
    behavioral = _spot_check_behavioral(args.skill)
    if behavioral:
        # Gate: revert if behavioral accuracy drops below threshold
        if behavioral["accuracy"] < 0.60:
            verdict = "REVERT"
            reason = f"trigger accuracy below threshold: {behavioral['accuracy']:.0%}"
        # Warn on proxy-gold divergence (structural improves but behavioral doesn't)
        if prev_behavioral is not None and improved:
            behavioral_delta = behavioral["accuracy"] - prev_behavioral
            if behavioral_delta < -0.10:
                verdict = "REVERT"
                reason = f"proxy-gold divergence: structural +{new_composite - prev_best:.3f} but behavioral {behavioral_delta:+.0%}"

    # SPIN convergence detector (Chen et al., ICML 2024)
    convergence_warning = None
    iteration_count = get_iteration_count()
    if abs(new_composite - prev_best) < 0.001 and iteration_count > 5:
        convergence_warning = "SPIN convergence: proxy metric saturated — consider expanding eval dimensions"

    output = {
        "skill": args.skill,
        "composite": new_composite,
        "previous_best": prev_best,
        "delta": round(new_composite - prev_best, 4),
        "checks_passed": checks_passed,
        "checks_output": checks_output if not checks_passed else "PASSED",
        "verdict": verdict,
        "reason": reason,
        # Proxy-gold tracking (Gao et al. ICML 2023)
        "proxy_score": new_composite,
        "gold_score": behavioral["accuracy"] if behavioral else None,
        "behavioral": behavioral,
        "convergence_warning": convergence_warning,
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
    append_journal(entry)
    print(json.dumps({"status": "reverted", "iteration": iteration}))


def cmd_target(args):
    """Find weakest skill+dimension."""
    target = find_weakest(args.strategy)
    if target is None:
        print(json.dumps({"status": "all_perfect", "message": "AUTORESEARCH_COMPLETE"}))
    else:
        print(json.dumps(target))


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
    p_keep.set_defaults(func=cmd_keep)

    # revert
    p_revert = sub.add_parser("revert", help="Revert mutation (git checkout + journal)")
    p_revert.add_argument("skill")
    p_revert.add_argument("dimension")
    p_revert.add_argument("old")
    p_revert.add_argument("new")
    p_revert.add_argument("--desc", required=True)
    p_revert.add_argument("--asi", default="{}")
    p_revert.set_defaults(func=cmd_revert)

    # target
    p_target = sub.add_parser("target", help="Find weakest skill+dimension")
    p_target.add_argument("--strategy", default="targeted", choices=["targeted", "sweep", "random"])
    p_target.set_defaults(func=cmd_target)

    # status
    p_status = sub.add_parser("status", help="Show current state")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
