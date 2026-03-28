#!/usr/bin/env python3
"""Haiku routing consistency test.

Tests whether haiku gives consistent routing decisions across multiple runs
for the same prompt. Unstable routing means users get unpredictable behavior.

How it works:
  1. Load all skill descriptions (reuses trigger_scorer patterns)
  2. For each skill's trigger file, take the should_trigger prompts
  3. Ask haiku N times for each prompt
  4. Measure agreement: what % of runs give the same top answer?
  5. Flag prompts with <80% agreement as "unstable"

Usage:
    python3 -m lab.eval.consistency_test --skill plan --runs 5
    python3 -m lab.eval.consistency_test --all --runs 5
    python3 -m lab.eval.consistency_test --all --runs 3 --threshold 60
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(EVAL_DIR))
sys.path.insert(0, PROJECT_ROOT)

from lab.eval.trigger_scorer import ask_haiku, load_all_descriptions, load_trigger_file

TRIGGERS_DIR = os.path.join(EVAL_DIR, "triggers")
RESULTS_PATH = os.path.join(TRIGGERS_DIR, "consistency_results.json")


def _extract_prompt(item) -> str:
    """Extract prompt string from either a string or dict entry."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("prompt", "")
    return str(item)


def _normalize_response(skills: list[str]) -> str:
    """Normalize a haiku response to a comparable string.

    Uses the top skill (first returned) as the routing decision.
    Returns "none" if no skills were returned.
    """
    if not skills:
        return "none"
    return skills[0].lower().strip()


def test_prompt_consistency(
    prompt: str,
    all_descriptions: dict[str, str],
    runs: int,
) -> dict:
    """Run haiku N times on one prompt and measure agreement."""
    responses = []
    for _ in range(runs):
        chosen = ask_haiku(all_descriptions, prompt)
        normalized = _normalize_response(chosen)
        responses.append(normalized)

    counts = Counter(responses)
    most_common_answer, most_common_count = counts.most_common(1)[0]
    agreement = most_common_count / runs

    return {
        "prompt": prompt,
        "runs": runs,
        "responses": responses,
        "response_counts": dict(counts),
        "majority_answer": most_common_answer,
        "agreement": round(agreement, 4),
        "stable": agreement >= 0.8,
    }


def test_skill_consistency(
    skill_name: str,
    triggers: dict,
    all_descriptions: dict[str, str],
    runs: int,
    threshold: float,
) -> dict:
    """Test consistency for all should_trigger prompts of one skill."""
    should_trigger = triggers.get("should_trigger", [])
    hard_should_trigger = triggers.get("hard_should_trigger", [])
    all_prompts = should_trigger + hard_should_trigger

    if not all_prompts:
        return {
            "skill": skill_name,
            "prompts_tested": 0,
            "results": [],
            "average_agreement": 0.0,
            "unstable_prompts": [],
        }

    results = []
    for item in all_prompts:
        prompt = _extract_prompt(item)
        if not prompt:
            continue
        result = test_prompt_consistency(prompt, all_descriptions, runs)
        # Tag with source tier
        if item in should_trigger:
            result["tier"] = "standard"
        else:
            result["tier"] = "hard"
            if isinstance(item, dict) and "axis" in item:
                result["axis"] = item["axis"]
        results.append(result)

    agreements = [r["agreement"] for r in results]
    avg_agreement = sum(agreements) / len(agreements) if agreements else 0.0
    unstable = [r for r in results if r["agreement"] < threshold]

    return {
        "skill": skill_name,
        "prompts_tested": len(results),
        "average_agreement": round(avg_agreement, 4),
        "stable_count": len(results) - len(unstable),
        "unstable_count": len(unstable),
        "unstable_prompts": [
            {
                "prompt": r["prompt"],
                "agreement": r["agreement"],
                "response_counts": r["response_counts"],
                "tier": r.get("tier", "standard"),
            }
            for r in unstable
        ],
        "results": results,
    }


def print_skill_results(data: dict, threshold: float) -> None:
    """Print formatted results for one skill."""
    skill = data["skill"]
    avg = data["average_agreement"]
    tested = data["prompts_tested"]
    stable = data.get("stable_count", 0)
    unstable_count = data.get("unstable_count", 0)

    status = "STABLE" if unstable_count == 0 else "UNSTABLE"
    marker = " *" if unstable_count > 0 else ""
    print(f"  {skill}: agreement={avg:.0%} ({stable}/{tested} stable){marker}")

    for entry in data.get("unstable_prompts", []):
        prompt_short = entry["prompt"][:60]
        counts_str = ", ".join(
            f"{k}={v}" for k, v in sorted(entry["response_counts"].items(), key=lambda x: -x[1])
        )
        tier_tag = f" [{entry.get('tier', 'standard')}]" if entry.get("tier") == "hard" else ""
        print(f"    UNSTABLE ({entry['agreement']:.0%}): \"{prompt_short}...\"{tier_tag}")
        print(f"      responses: {counts_str}")


def main():
    parser = argparse.ArgumentParser(
        description="Test haiku routing consistency across multiple runs"
    )
    parser.add_argument("--skill", help="Test one skill by name")
    parser.add_argument("--all", action="store_true", help="Test all skills with trigger files")
    parser.add_argument("--runs", type=int, default=5, help="Number of runs per prompt (default: 5)")
    parser.add_argument(
        "--threshold", type=float, default=80,
        help="Agreement %% below which a prompt is flagged unstable (default: 80)"
    )
    args = parser.parse_args()

    if not args.skill and not args.all:
        parser.print_help()
        sys.exit(1)

    threshold = args.threshold / 100.0  # Convert percentage to fraction
    all_descriptions = load_all_descriptions()

    all_results = {}

    if args.skill:
        skill_names = [args.skill]
    else:
        # Find all skills with trigger files
        skill_names = []
        for name in sorted(all_descriptions.keys()):
            if load_trigger_file(name) is not None:
                skill_names.append(name)

    print(f"Consistency test: {len(skill_names)} skill(s), {args.runs} runs/prompt, threshold={args.threshold:.0f}%\n")

    total_prompts = 0
    total_unstable = 0
    total_agreement = 0.0
    skills_tested = 0

    for skill_name in skill_names:
        triggers = load_trigger_file(skill_name)
        if not triggers:
            if args.skill:
                print(f"No trigger file for {skill_name}", file=sys.stderr)
                sys.exit(1)
            continue

        print(f"  Testing {skill_name}...", flush=True)
        data = test_skill_consistency(skill_name, triggers, all_descriptions, args.runs, threshold)

        if data["prompts_tested"] == 0:
            continue

        all_results[skill_name] = data
        skills_tested += 1
        total_prompts += data["prompts_tested"]
        total_unstable += data["unstable_count"]
        total_agreement += data["average_agreement"]

        print_skill_results(data, threshold)

    # Summary
    if skills_tested > 0:
        overall_agreement = total_agreement / skills_tested
        stable_prompts = total_prompts - total_unstable
        print(f"\n{'=' * 60}")
        print(f"Overall router stability: {overall_agreement:.0%}")
        print(f"Prompts tested: {total_prompts} ({stable_prompts} stable, {total_unstable} unstable)")
        print(f"Skills tested: {skills_tested}")
        if total_unstable > 0:
            print(f"\n{total_unstable} unstable prompt(s) detected (< {args.threshold:.0f}% agreement)")
    else:
        print("No skills tested.")

    # Save results
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "runs": args.runs,
            "threshold": threshold,
        },
        "summary": {
            "skills_tested": skills_tested,
            "total_prompts": total_prompts,
            "stable_prompts": total_prompts - total_unstable,
            "unstable_prompts": total_unstable,
            "overall_agreement": round(overall_agreement, 4) if skills_tested > 0 else 0.0,
        },
        "per_skill": {
            name: {
                "prompts_tested": data["prompts_tested"],
                "average_agreement": data["average_agreement"],
                "stable_count": data["stable_count"],
                "unstable_count": data["unstable_count"],
                "unstable_prompts": data["unstable_prompts"],
                "results": data["results"],
            }
            for name, data in all_results.items()
        },
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)
        f.write("\n")
    print(f"\nResults saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
