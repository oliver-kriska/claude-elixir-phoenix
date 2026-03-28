#!/usr/bin/env python3
"""Evaluator Stress Test (EST) — detect gameable matchers.

Applies semantics-preserving perturbations to skill files and checks
whether matcher scores change. If scores change on perturbations that
preserve meaning, the matcher tests surface features, not quality.

Research basis:
  - "Detecting Proxy Gaming via Evaluator Stress Tests" (Shihab et al., 2025)
    arXiv:2507.05619
  - "Goodhart's Law Applies to NLP's Explanation Benchmarks" (Hsia et al., EACL 2024)
    arXiv:2308.14272

Usage:
    python3 -m lab.eval.evaluator_stress_test                    # Test all matchers
    python3 -m lab.eval.evaluator_stress_test --skill plan       # Test one skill
    python3 -m lab.eval.evaluator_stress_test --verbose          # Show perturbation details
"""

import argparse
import copy
import json
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(PROJECT_ROOT))

from lab.eval.scorer import score_skill, find_eval, find_all_skills, PLUGIN_ROOT
from lab.eval.schemas import EvalDefinition


def perturb_reorder_sections(content: str) -> str:
    """Reorder non-critical sections (preserves Iron Laws position)."""
    lines = content.split("\n")

    # Find section boundaries (## headers)
    sections: list[tuple[int, str, list[str]]] = []
    current_header = ""
    current_lines: list[str] = []
    in_frontmatter = False
    frontmatter_lines: list[str] = []

    for i, line in enumerate(lines):
        if i == 0 and line.strip() == "---":
            in_frontmatter = True
            frontmatter_lines.append(line)
            continue
        if in_frontmatter:
            frontmatter_lines.append(line)
            if line.strip() == "---":
                in_frontmatter = False
            continue

        if line.startswith("## "):
            if current_header or current_lines:
                sections.append((len(sections), current_header, current_lines))
            current_header = line
            current_lines = []
        else:
            current_lines.append(line)

    if current_header or current_lines:
        sections.append((len(sections), current_header, current_lines))

    # Only reorder if we have 3+ sections and Iron Laws is not first
    if len(sections) < 3:
        return content

    # Swap two non-Iron-Laws sections
    iron_laws_idx = None
    for i, (_, header, _) in enumerate(sections):
        if "Iron Laws" in header:
            iron_laws_idx = i
            break

    swappable = [i for i in range(len(sections)) if i != iron_laws_idx and i != 0]
    if len(swappable) >= 2:
        a, b = swappable[0], swappable[-1]
        sections[a], sections[b] = sections[b], sections[a]

    # Reconstruct
    result = "\n".join(frontmatter_lines) + "\n" if frontmatter_lines else ""
    for _, header, body in sections:
        if header:
            result += header + "\n"
        result += "\n".join(body) + "\n"

    return result


def perturb_reword_bullets(content: str) -> str:
    """Reword bullet points using synonyms (preserves meaning)."""
    # Simple synonym swaps that preserve meaning
    swaps = [
        (r"\bNEVER\b", "MUST NOT"),
        (r"\bALWAYS\b", "MUST ALWAYS"),
        (r"\bDo NOT\b", "NEVER"),
        (r"\bUse\b", "Employ"),
    ]

    result = content
    for pattern, replacement in swaps:
        # Only apply to first occurrence to keep changes minimal
        result = re.sub(pattern, replacement, result, count=1)

    return result


def perturb_rename_code_vars(content: str) -> str:
    """Rename variables in code examples (preserves logic)."""
    # Swap common variable names in code blocks
    in_code = False
    lines = content.split("\n")
    result = []
    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
        elif in_code:
            line = line.replace("user", "usr").replace("post", "article")
        result.append(line)
    return "\n".join(result)


PERTURBATIONS = [
    ("reorder_sections", perturb_reorder_sections),
    ("reword_bullets", perturb_reword_bullets),
    ("rename_code_vars", perturb_rename_code_vars),
]


def stress_test_skill(skill_path: str, verbose: bool = False) -> dict:
    """Run EST on one skill. Returns {dimension: {perturbation: score_delta}}."""
    skill_name = os.path.basename(os.path.dirname(skill_path))
    eval_path = find_eval(skill_name)
    eval_def = EvalDefinition.from_file(eval_path) if eval_path else None

    # Baseline score
    baseline = score_skill(skill_path, eval_def)
    baseline_scores = {name: dim.score for name, dim in baseline.dimensions.items()}

    results = {
        "skill": skill_name,
        "baseline_composite": baseline.composite,
        "baseline_dimensions": baseline_scores,
        "perturbations": {},
        "gameable_dimensions": [],
    }

    with open(skill_path) as f:
        original_content = f.read()

    for pert_name, pert_fn in PERTURBATIONS:
        perturbed_content = pert_fn(original_content)

        if perturbed_content == original_content:
            continue

        # Write perturbed content temporarily
        with open(skill_path, "w") as f:
            f.write(perturbed_content)

        try:
            perturbed_result = score_skill(skill_path, eval_def)
            perturbed_scores = {name: dim.score for name, dim in perturbed_result.dimensions.items()}

            deltas = {}
            for dim_name in baseline_scores:
                if dim_name in perturbed_scores:
                    delta = perturbed_scores[dim_name] - baseline_scores[dim_name]
                    if abs(delta) > 0.001:
                        deltas[dim_name] = round(delta, 4)

            results["perturbations"][pert_name] = {
                "composite_delta": round(perturbed_result.composite - baseline.composite, 4),
                "dimension_deltas": deltas,
            }

            if verbose and deltas:
                print(f"  {pert_name}: {deltas}")

        finally:
            # Restore original content
            with open(skill_path, "w") as f:
                f.write(original_content)

    # Identify gameable dimensions (score changed on semantic-preserving perturbation)
    gameable = set()
    for pert_data in results["perturbations"].values():
        for dim_name, delta in pert_data.get("dimension_deltas", {}).items():
            if abs(delta) > 0.01:  # >1% change = gameable
                gameable.add(dim_name)
    results["gameable_dimensions"] = sorted(gameable)

    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluator Stress Test for matchers")
    parser.add_argument("--skill", help="Test one skill")
    parser.add_argument("--verbose", action="store_true", help="Show perturbation details")
    args = parser.parse_args()

    if args.skill:
        skill_path = os.path.join(PLUGIN_ROOT, "skills", args.skill, "SKILL.md")
        if not os.path.isfile(skill_path):
            print(f"Skill not found: {args.skill}", file=sys.stderr)
            sys.exit(1)
        result = stress_test_skill(skill_path, args.verbose)
        print(json.dumps(result, indent=2))
    else:
        all_gameable: dict[str, int] = {}
        skills_tested = 0

        for skill_path in find_all_skills():
            name = os.path.basename(os.path.dirname(skill_path))
            print(f"  Testing {name}...", end=" ", flush=True)
            result = stress_test_skill(skill_path, args.verbose)
            skills_tested += 1

            if result["gameable_dimensions"]:
                print(f"GAMEABLE: {result['gameable_dimensions']}")
                for dim in result["gameable_dimensions"]:
                    all_gameable[dim] = all_gameable.get(dim, 0) + 1
            else:
                print("OK")

        print(f"\n{skills_tested} skills tested")
        if all_gameable:
            print("Gameable dimensions (per Shihab et al. arXiv:2507.05619):")
            for dim, count in sorted(all_gameable.items(), key=lambda x: -x[1]):
                print(f"  {dim}: {count} skills affected")
        else:
            print("No gameable dimensions detected — matchers are robust")


if __name__ == "__main__":
    main()
