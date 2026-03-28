#!/usr/bin/env python3
"""Neighbor regression test: when a skill description changes, test it AND its confusable neighbors.

Prevents the scenario where improving one skill's routing steals prompts from similar skills.
Based on "When Single-Agent with Skills Replace Multi-Agent Systems" (arXiv:2601.04748):
skill selection degradation is driven by semantic confusability among skills.

Usage:
    python3 -m lab.eval.neighbor_regression --skill plan           # Test plan + neighbors
    python3 -m lab.eval.neighbor_regression --changed              # Auto-detect from git diff
    python3 -m lab.eval.neighbor_regression --all                  # Full 40x40 sweep
    python3 -m lab.eval.neighbor_regression --show-neighbors plan  # Show neighbors without testing
"""

import argparse
import json
import os
import re
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from lab.eval.matchers import parse_frontmatter

PLUGIN_ROOT = os.path.join(PROJECT_ROOT, "plugins", "elixir-phoenix")
TRIGGERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "triggers")
RESULTS_DIR = os.path.join(TRIGGERS_DIR, "results")
NEIGHBORS_FILE = os.path.join(TRIGGERS_DIR, "_confusable_neighbors.json")

# Known confusable pairs — bidirectional map
# Source: domain knowledge + generate_confusable_pairs.py
KNOWN_PAIRS = [
    ("investigate", "review"),
    ("investigate", "perf"),
    ("n1-check", "ecto-patterns"),
    ("n1-check", "perf"),
    ("plan", "full"),
    ("plan", "work"),
    ("quick", "investigate"),
    ("quick", "work"),
    ("review", "challenge"),
    ("review", "pr-review"),
    ("liveview-patterns", "phoenix-contexts"),
    ("ecto-patterns", "phoenix-contexts"),
    ("perf", "assigns-audit"),
    ("audit", "boundaries"),
    ("document", "compound"),
    ("compound", "learn-from-fix"),
    ("full", "work"),
]


def build_neighbor_map() -> dict[str, list[str]]:
    """Build bidirectional neighbor map from known pairs + confusion matrix."""
    neighbors: dict[str, set[str]] = {}

    # Add known pairs (bidirectional)
    for a, b in KNOWN_PAIRS:
        neighbors.setdefault(a, set()).add(b)
        neighbors.setdefault(b, set()).add(a)

    # Augment from confusion matrix if available
    if os.path.isdir(RESULTS_DIR):
        for fname in os.listdir(RESULTS_DIR):
            if fname.startswith("_") or not fname.endswith(".json"):
                continue
            skill = fname.replace(".json", "")
            try:
                with open(os.path.join(RESULTS_DIR, fname)) as f:
                    data = json.load(f)
                for result in data.get("results", []):
                    if not result.get("correct", True):
                        for chosen in result.get("chosen", []):
                            if chosen != skill:
                                neighbors.setdefault(skill, set()).add(chosen)
                                neighbors.setdefault(chosen, set()).add(skill)
            except (json.JSONDecodeError, KeyError):
                continue

    return {k: sorted(v) for k, v in sorted(neighbors.items())}


def get_changed_skills() -> list[str]:
    """Detect skills changed in current git diff."""
    try:
        # Uncommitted changes
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD", "--", "plugins/elixir-phoenix/skills/"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        files = result.stdout.strip().split("\n") if result.stdout.strip() else []

        # Staged changes
        result2 = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--", "plugins/elixir-phoenix/skills/"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        if result2.stdout.strip():
            files += result2.stdout.strip().split("\n")

        skills = set()
        for f in files:
            match = re.search(r"plugins/elixir-phoenix/skills/([^/]+)/", f)
            if match:
                skills.add(match.group(1))
        return sorted(skills)

    except Exception:
        return []


def get_test_set(skill_name: str) -> list[str]:
    """Get the skills to test: the changed skill + its confusable neighbors."""
    neighbor_map = build_neighbor_map()
    neighbors = neighbor_map.get(skill_name, [])
    # Always include the skill itself + top 3 neighbors
    test_set = [skill_name] + neighbors[:3]
    return sorted(set(test_set))


def run_trigger_test(skill_name: str) -> dict | None:
    """Run trigger_scorer for one skill and return results."""
    try:
        result = subprocess.run(
            ["python3", "-m", "lab.eval.trigger_scorer", "--skill", skill_name],
            capture_output=True, text=True, timeout=120, cwd=PROJECT_ROOT,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return None


def compare_with_baseline(skill_name: str, new_result: dict) -> dict:
    """Compare new result with cached baseline."""
    baseline_path = os.path.join(RESULTS_DIR, f"{skill_name}.json")
    comparison = {
        "skill": skill_name,
        "new_accuracy": new_result.get("accuracy", 0),
        "new_precision": new_result.get("precision", 0),
        "new_recall": new_result.get("recall", 0),
    }

    if os.path.isfile(baseline_path):
        with open(baseline_path) as f:
            baseline = json.load(f)
        comparison["baseline_accuracy"] = baseline.get("accuracy", 0)
        comparison["baseline_precision"] = baseline.get("precision", 0)
        comparison["baseline_recall"] = baseline.get("recall", 0)
        comparison["accuracy_delta"] = round(
            comparison["new_accuracy"] - comparison["baseline_accuracy"], 4
        )
        comparison["regression"] = comparison["accuracy_delta"] < -0.10  # >10% drop = regression
    else:
        comparison["baseline_accuracy"] = None
        comparison["accuracy_delta"] = None
        comparison["regression"] = False

    return comparison


def main():
    parser = argparse.ArgumentParser(description="Test changed skills + confusable neighbors")
    parser.add_argument("--skill", help="Test one skill + its neighbors")
    parser.add_argument("--changed", action="store_true", help="Auto-detect from git diff")
    parser.add_argument("--all", action="store_true", help="Full sweep of all skills")
    parser.add_argument("--show-neighbors", metavar="SKILL", help="Show neighbors without testing")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be tested")
    args = parser.parse_args()

    neighbor_map = build_neighbor_map()

    if args.show_neighbors:
        neighbors = neighbor_map.get(args.show_neighbors, [])
        print(f"Confusable neighbors of '{args.show_neighbors}':")
        for n in neighbors:
            print(f"  - {n}")
        if not neighbors:
            print("  (none known)")
        return

    # Determine skills to test
    if args.skill:
        test_skills = get_test_set(args.skill)
        print(f"Testing {args.skill} + {len(test_skills) - 1} neighbors: {test_skills}")
    elif args.changed:
        changed = get_changed_skills()
        if not changed:
            print("No skill changes detected in git diff.")
            return
        test_skills = set()
        for s in changed:
            test_skills.update(get_test_set(s))
        test_skills = sorted(test_skills)
        print(f"Changed skills: {changed}")
        print(f"Testing {len(test_skills)} skills (changed + neighbors): {test_skills}")
    elif args.all:
        skills_dir = os.path.join(PLUGIN_ROOT, "skills")
        test_skills = sorted(
            d for d in os.listdir(skills_dir)
            if os.path.isfile(os.path.join(skills_dir, d, "SKILL.md"))
        )
        print(f"Testing all {len(test_skills)} skills")
    else:
        parser.print_help()
        return

    if args.dry_run:
        print("\nDry run — would test:")
        for s in test_skills:
            neighbors = neighbor_map.get(s, [])
            print(f"  {s} (neighbors: {', '.join(neighbors[:3]) if neighbors else 'none'})")
        return

    # Run tests
    results = []
    regressions = []
    print()

    for skill in test_skills:
        trigger_path = os.path.join(TRIGGERS_DIR, f"{skill}.json")
        if not os.path.isfile(trigger_path):
            print(f"  {skill}: no trigger file, skipping")
            continue

        print(f"  Testing {skill}...", end=" ", flush=True)
        result = run_trigger_test(skill)
        if result:
            comparison = compare_with_baseline(skill, result)
            results.append(comparison)

            delta_str = ""
            if comparison["accuracy_delta"] is not None:
                delta = comparison["accuracy_delta"]
                delta_str = f" (delta: {delta:+.0%})"
                if comparison["regression"]:
                    delta_str += " ⚠ REGRESSION"
                    regressions.append(comparison)

            print(f"accuracy={comparison['new_accuracy']:.0%}{delta_str}")
        else:
            print("FAILED (timeout or error)")

    # Summary
    print(f"\n{'='*60}")
    print(f"Tested {len(results)} skills")

    if regressions:
        print(f"\n⚠ REGRESSIONS DETECTED ({len(regressions)}):")
        for r in regressions:
            print(f"  {r['skill']}: {r['baseline_accuracy']:.0%} → {r['new_accuracy']:.0%} ({r['accuracy_delta']:+.0%})")
        print("\nA skill description change may have stolen prompts from neighbors.")
        sys.exit(1)
    else:
        print("No regressions detected.")

    # Save results
    output_path = os.path.join(TRIGGERS_DIR, "_neighbor_regression.json")
    with open(output_path, "w") as f:
        json.dump({
            "skills_tested": [r["skill"] for r in results],
            "regressions": regressions,
            "results": results,
        }, f, indent=2)
        f.write("\n")
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    main()
