#!/usr/bin/env python3
"""Behavioral trigger evaluation using haiku.

Tests whether Claude routes user prompts to the correct skill
by sending all skill descriptions + one test prompt to haiku.

Supports two tiers:
  - Standard: should_trigger / should_not_trigger (threshold: 75% accuracy)
  - Hard: hard_should_trigger / hard_should_not_trigger (threshold: 50% accuracy)
    Hard prompts test terse, typo-laden, multi-intent, and confusable-pair routing.

Research basis:
  - CheckList (Ribeiro et al., ACL 2020) — MFT/INV/DIR test matrix
  - "Not All Negatives are Equal" (Suresh & Ong, EMNLP 2021) — confusable negatives
  - Proving Test Set Contamination (Oren et al., ICLR 2024) — exchangeability tests

Usage:
    python3 -m lab.eval.trigger_scorer --skill plan       # Test one skill
    python3 -m lab.eval.trigger_scorer --all               # Test all skills with triggers
    python3 -m lab.eval.trigger_scorer --all --cache       # Use cached results (no API calls)
    python3 -m lab.eval.trigger_scorer --all --confusion   # Print confusion matrix

Cost: ~$0.001 per test prompt, ~$0.04 for all 40 skills × 8 prompts.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(EVAL_DIR))
sys.path.insert(0, PROJECT_ROOT)

from lab.eval.matchers import parse_frontmatter

PLUGIN_ROOT = os.path.join(PROJECT_ROOT, "plugins", "elixir-phoenix")
TRIGGERS_DIR = os.path.join(EVAL_DIR, "triggers")
RESULTS_DIR = os.path.join(TRIGGERS_DIR, "results")


def load_all_descriptions() -> dict[str, str]:
    """Load all skill names and descriptions."""
    skills_dir = os.path.join(PLUGIN_ROOT, "skills")
    descriptions = {}
    for name in sorted(os.listdir(skills_dir)):
        skill_path = os.path.join(skills_dir, name, "SKILL.md")
        if not os.path.isfile(skill_path):
            continue
        with open(skill_path) as f:
            content = f.read()
        fm = parse_frontmatter(content)
        desc = str(fm.get("description", ""))
        if desc:
            descriptions[name] = desc
    return descriptions


def load_trigger_file(skill_name: str) -> dict | None:
    """Load trigger test prompts for a skill."""
    path = os.path.join(TRIGGERS_DIR, f"{skill_name}.json")
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return json.load(f)


def ask_haiku(all_descriptions: dict[str, str], prompt: str) -> list[str]:
    """Ask haiku which skill(s) it would load for a given prompt."""
    desc_list = "\n".join(f"- {name}: {desc[:150]}" for name, desc in all_descriptions.items())

    system_prompt = f"""You are testing skill routing for a Claude Code plugin.

Given these available skills:
{desc_list}

The user says: "{prompt}"

Which skill(s) should be loaded? Reply with ONLY the skill name(s), one per line.
If no skill should be loaded, reply with "none".
List at most 3 skills, ordered by relevance."""

    try:
        result = subprocess.run(
            [
                "claude", "-p", system_prompt,
                "--model", "haiku",
                "--output-format", "text",
                "--max-budget-usd", "0.50",
                "--no-session-persistence",
            ],
            capture_output=True, text=True, timeout=30,
        )

        if result.returncode != 0:
            return []

        text = result.stdout.strip()
        # Parse skill names from response — one per line, strip bullets/numbers
        skills = []
        for line in text.split("\n"):
            line = line.strip().lstrip("-*0123456789.) ").strip()
            # Remove explanations after dashes or parentheses
            if " — " in line:
                line = line.split(" — ")[0].strip()
            if " (" in line:
                line = line.split(" (")[0].strip()
            if " -" in line:
                line = line.split(" -")[0].strip()
            line = line.strip("`").strip()
            if line and line != "none" and not line.startswith("No "):
                skills.append(line)
        return skills

    except (subprocess.TimeoutExpired, Exception):
        return []


def _extract_prompt(item) -> str:
    """Extract prompt string from either a string or dict entry."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("prompt", "")
    return str(item)


def _compute_metrics(results: list[dict]) -> dict:
    """Compute precision/recall/accuracy from a list of test results."""
    total = len(results)
    correct_count = sum(1 for r in results if r["correct"])

    tp = sum(1 for r in results if r["expected"] and r["correct"])
    fp = sum(1 for r in results if not r["expected"] and not r["correct"])
    fn = sum(1 for r in results if r["expected"] and not r["correct"])
    tn = sum(1 for r in results if not r["expected"] and r["correct"])

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    accuracy = correct_count / total if total > 0 else 0.0

    return {
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "total": total,
        "correct": correct_count,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


def _run_prompts(
    skill_name: str,
    should_trigger: list,
    should_not: list,
    all_descriptions: dict[str, str],
) -> list[dict]:
    """Run prompts through haiku and collect results."""
    results = []

    for item in should_trigger:
        prompt = _extract_prompt(item)
        if not prompt:
            continue
        chosen = ask_haiku(all_descriptions, prompt)
        correct = skill_name in chosen
        entry = {
            "prompt": prompt,
            "expected": True,
            "chosen": chosen,
            "correct": correct,
        }
        # Preserve metadata from dict prompts (axis, confusable_with, etc.)
        if isinstance(item, dict):
            entry["axis"] = item.get("axis", "")
            if "confusable_with" in item:
                entry["confusable_with"] = item["confusable_with"]
        results.append(entry)

    for item in should_not:
        prompt = _extract_prompt(item)
        if not prompt:
            continue
        chosen = ask_haiku(all_descriptions, prompt)
        correct = skill_name not in chosen
        entry = {
            "prompt": prompt,
            "expected": False,
            "chosen": chosen,
            "correct": correct,
        }
        if isinstance(item, dict):
            entry["axis"] = item.get("axis", "")
            if "confusable_with" in item:
                entry["confusable_with"] = item["confusable_with"]
        results.append(entry)

    return results


def score_skill_triggers(
    skill_name: str,
    triggers: dict,
    all_descriptions: dict[str, str],
    use_cache: bool = False,
) -> dict:
    """Score trigger accuracy for one skill. Returns precision/recall/accuracy.

    Supports two tiers:
      - standard: should_trigger / should_not_trigger
      - hard: hard_should_trigger / hard_should_not_trigger (CheckList-inspired)
    """
    cache_path = os.path.join(RESULTS_DIR, f"{skill_name}.json")

    if use_cache and os.path.isfile(cache_path):
        with open(cache_path) as f:
            return json.load(f)

    # Standard tier
    standard_results = _run_prompts(
        skill_name,
        triggers.get("should_trigger", []),
        triggers.get("should_not_trigger", []),
        all_descriptions,
    )
    standard_metrics = _compute_metrics(standard_results)

    # Hard tier (CheckList MFT/INV/DIR + confusable pairs)
    hard_results = _run_prompts(
        skill_name,
        triggers.get("hard_should_trigger", []),
        triggers.get("hard_should_not_trigger", []),
        all_descriptions,
    )
    hard_metrics = _compute_metrics(hard_results) if hard_results else None

    # Combined metrics (all results together)
    all_results = standard_results + hard_results
    combined_metrics = _compute_metrics(all_results)

    score_data = {
        "skill": skill_name,
        # Combined (backward-compatible)
        "accuracy": combined_metrics["accuracy"],
        "precision": combined_metrics["precision"],
        "recall": combined_metrics["recall"],
        "total": combined_metrics["total"],
        "correct": combined_metrics["correct"],
        "tp": combined_metrics["tp"],
        "fp": combined_metrics["fp"],
        "fn": combined_metrics["fn"],
        "tn": combined_metrics["tn"],
        # Per-tier breakdown
        "standard": standard_metrics,
        "hard": hard_metrics,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": all_results,
    }

    # Cache results
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(score_data, f, indent=2)
        f.write("\n")

    return score_data


def build_confusion_matrix(
    all_descriptions: dict[str, str],
    use_cache: bool = True,
) -> dict[str, dict[str, int]]:
    """Build a skill confusion matrix from cached trigger results.

    Returns {skill_name: {confused_with_skill: count}}.
    Identifies which skill pairs haiku confuses most.

    Research basis: "Not All Negatives are Equal" (Suresh & Ong, EMNLP 2021)
    """
    matrix: dict[str, dict[str, int]] = {}

    for skill_name in sorted(all_descriptions.keys()):
        triggers = load_trigger_file(skill_name)
        if not triggers:
            continue

        cache_path = os.path.join(RESULTS_DIR, f"{skill_name}.json")
        if not os.path.isfile(cache_path):
            continue

        with open(cache_path) as f:
            data = json.load(f)

        confusions: dict[str, int] = {}
        for result in data.get("results", []):
            if result["expected"] and not result["correct"]:
                # False negative: should have triggered, didn't
                for chosen in result.get("chosen", []):
                    if chosen != skill_name and chosen in all_descriptions:
                        confusions[chosen] = confusions.get(chosen, 0) + 1
            elif not result["expected"] and not result["correct"]:
                # False positive: shouldn't have triggered, did
                # The skill was incorrectly chosen for this prompt
                confusions[skill_name] = confusions.get(skill_name, 0) + 1

        if confusions:
            matrix[skill_name] = confusions

    return matrix


def main():
    parser = argparse.ArgumentParser(description="Test skill trigger accuracy with haiku")
    parser.add_argument("--skill", help="Test one skill")
    parser.add_argument("--all", action="store_true", help="Test all skills with trigger files")
    parser.add_argument("--cache", action="store_true", help="Use cached results")
    parser.add_argument("--summary", action="store_true", help="Print summary only")
    parser.add_argument("--confusion", action="store_true", help="Print confusion matrix (requires cached results)")
    args = parser.parse_args()

    all_descriptions = load_all_descriptions()

    if args.confusion:
        matrix = build_confusion_matrix(all_descriptions)
        if not matrix:
            print("No cached results. Run --all first.", file=sys.stderr)
            sys.exit(1)
        print("Skill Confusion Matrix (skill → confused with):")
        print("-" * 60)
        for skill, confusions in sorted(matrix.items()):
            pairs = sorted(confusions.items(), key=lambda x: -x[1])
            pair_strs = [f"{k}({v})" for k, v in pairs]
            print(f"  {skill}: {', '.join(pair_strs)}")
        print(f"\n{len(matrix)} skills with confusions. Top confusable pairs for hard negative generation.")
        return

    if args.skill:
        triggers = load_trigger_file(args.skill)
        if not triggers:
            print(f"No trigger file for {args.skill}", file=sys.stderr)
            sys.exit(1)
        result = score_skill_triggers(args.skill, triggers, all_descriptions, args.cache)
        if args.summary:
            line = f"{args.skill}: accuracy={result['accuracy']:.0%} P={result['precision']:.0%} R={result['recall']:.0%}"
            if result.get("hard"):
                line += f" | hard: accuracy={result['hard']['accuracy']:.0%}"
            print(line)
        else:
            print(json.dumps(result, indent=2))

    elif args.all:
        skills_tested = 0
        total_accuracy = 0
        total_hard_accuracy = 0
        skills_with_hard = 0
        results = {}

        for name in sorted(all_descriptions.keys()):
            triggers = load_trigger_file(name)
            if not triggers:
                continue
            print(f"  Testing {name}...", end=" ", flush=True)
            result = score_skill_triggers(name, triggers, all_descriptions, args.cache)
            results[name] = result
            total_accuracy += result["accuracy"]
            skills_tested += 1

            line = f"accuracy={result['accuracy']:.0%} (P={result['precision']:.0%} R={result['recall']:.0%})"
            if result.get("hard") and result["hard"]["total"] > 0:
                line += f" | hard={result['hard']['accuracy']:.0%}"
                total_hard_accuracy += result["hard"]["accuracy"]
                skills_with_hard += 1
            print(line)

        avg = total_accuracy / skills_tested if skills_tested else 0
        print(f"\n{skills_tested} skills tested, average accuracy: {avg:.0%}")
        if skills_with_hard > 0:
            avg_hard = total_hard_accuracy / skills_with_hard
            print(f"{skills_with_hard} skills with hard prompts, average hard accuracy: {avg_hard:.0%}")

        if not args.summary:
            # Save aggregate
            aggregate_path = os.path.join(RESULTS_DIR, "_aggregate.json")
            with open(aggregate_path, "w") as f:
                json.dump({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "skills_tested": skills_tested,
                    "average_accuracy": round(avg, 4),
                    "skills_with_hard": skills_with_hard,
                    "average_hard_accuracy": round(total_hard_accuracy / skills_with_hard, 4) if skills_with_hard else None,
                    "per_skill": {
                        k: {
                            "accuracy": v["accuracy"],
                            "precision": v["precision"],
                            "recall": v["recall"],
                            "hard_accuracy": v["hard"]["accuracy"] if v.get("hard") else None,
                        }
                        for k, v in results.items()
                    },
                }, f, indent=2)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
