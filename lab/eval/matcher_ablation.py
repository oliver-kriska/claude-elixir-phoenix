#!/usr/bin/env python3
"""Leave-one-out matcher ablation for the eval framework.

For each check across all eval definitions, temporarily disables it
(forces always-pass) and re-scores all skills. Identifies which checks
contribute signal vs. which are noise (never change any score).

Usage:
    python3 -m lab.eval.matcher_ablation
"""

import copy
import json
import os
import sys
from dataclasses import dataclass

from lab.eval.schemas import EvalDefinition, EvalDimension, EvalCheck
from lab.eval.scorer import score_skill, find_all_skills, find_eval


OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "matcher_ablation_results.json")


@dataclass
class CheckInfo:
    """Identifies a single check across dimension + index."""
    dimension: str
    index: int
    check_type: str
    description: str
    skill_name: str  # eval it came from ("_default" for generic)

    @property
    def key(self) -> str:
        return f"{self.dimension}:{self.check_type}:{self.description}"


def get_eval_def(skill_path: str) -> EvalDefinition:
    """Get or generate eval definition for a skill."""
    skill_name = os.path.basename(os.path.dirname(skill_path))
    eval_path = find_eval(skill_name)
    if eval_path:
        return EvalDefinition.from_file(eval_path)
    return None  # will use default_eval inside score_skill


def build_ablated_eval(eval_def: EvalDefinition, dim_name: str, check_idx: int) -> EvalDefinition:
    """Create a copy of eval_def with one check forced to always-pass.

    We do this by setting the check's weight to 0 so it doesn't affect
    the dimension score, effectively removing its contribution.
    """
    ablated = copy.deepcopy(eval_def)
    dim = ablated.dimensions.get(dim_name)
    if dim and 0 <= check_idx < len(dim.checks):
        # Remove the check entirely so it can't fail
        dim.checks.pop(check_idx)
    return ablated


def enumerate_checks(eval_def: EvalDefinition, skill_name: str) -> list[CheckInfo]:
    """List all checks in an eval definition."""
    checks = []
    for dim_name, dim in eval_def.dimensions.items():
        for i, check in enumerate(dim.checks):
            checks.append(CheckInfo(
                dimension=dim_name,
                index=i,
                check_type=check.check_type,
                description=check.description,
                skill_name=skill_name,
            ))
    return checks


def run_ablation():
    """Run leave-one-out ablation across all skills."""
    skill_paths = find_all_skills()
    if not skill_paths:
        print("No skills found.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(skill_paths)} skills")

    # Phase 1: Compute baseline scores and collect all unique checks
    print("\n--- Phase 1: Baseline scoring ---")
    baselines: dict[str, float] = {}  # skill_name -> composite
    baseline_dims: dict[str, dict[str, float]] = {}  # skill_name -> {dim: score}
    eval_defs: dict[str, EvalDefinition | None] = {}  # skill_name -> eval_def or None

    for sp in skill_paths:
        sname = os.path.basename(os.path.dirname(sp))
        edef = get_eval_def(sp)
        eval_defs[sname] = edef
        result = score_skill(sp, edef)
        baselines[sname] = result.composite
        baseline_dims[sname] = {d: r.score for d, r in result.dimensions.items()}
        print(f"  {sname}: {result.composite:.4f}")

    # Phase 2: Collect all unique checks and track baseline pass/fail per check
    print("\n--- Phase 2: Enumerating checks + baseline failures ---")

    all_check_keys: dict[str, CheckInfo] = {}  # key -> first CheckInfo seen
    skill_checks: dict[str, list[CheckInfo]] = {}  # skill_name -> checks
    # Track which skills each check applies to and whether it passed
    check_pass_fail: dict[str, dict[str, bool]] = {}  # check_key -> {skill: passed}

    for sp in skill_paths:
        sname = os.path.basename(os.path.dirname(sp))
        edef = eval_defs[sname]
        if edef is None:
            from lab.eval.scorer import default_eval
            edef_for_enum = default_eval(sp)
        else:
            edef_for_enum = edef
        checks = enumerate_checks(edef_for_enum, sname)
        skill_checks[sname] = checks
        for c in checks:
            if c.key not in all_check_keys:
                all_check_keys[c.key] = c
                check_pass_fail[c.key] = {}

        # Get assertion-level results from baseline
        baseline_result = score_skill(sp, edef)
        for dim_name, dim_result in baseline_result.dimensions.items():
            for assertion in dim_result.assertions:
                # Match assertion back to check info
                for ci in checks:
                    if ci.dimension == dim_name and ci.check_type == assertion.check_type and ci.description == assertion.description:
                        check_pass_fail[ci.key][sname] = assertion.passed
                        break

    print(f"  {len(all_check_keys)} unique checks across all skills")

    # Show checks that fail for at least one skill (these are the interesting ones)
    failing_checks = {k: v for k, v in check_pass_fail.items() if any(not p for p in v.values())}
    all_pass_checks = {k: v for k, v in check_pass_fail.items() if all(p for p in v.values())}
    print(f"  {len(failing_checks)} checks fail for at least one skill")
    print(f"  {len(all_pass_checks)} checks pass universally (cannot contribute signal via ablation)")

    # Phase 3: Ablation - for each skill, for each of its checks, disable and re-score
    print("\n--- Phase 3: Ablation (this may take a moment) ---")

    # Track: for each check key, which skills changed and by how much
    check_impact: dict[str, list[dict]] = {}  # check_key -> [{skill, delta, dim_delta}]
    for key in all_check_keys:
        check_impact[key] = []

    total_ablations = sum(len(checks) for checks in skill_checks.values())
    done = 0

    for sp in skill_paths:
        sname = os.path.basename(os.path.dirname(sp))
        edef = eval_defs[sname]
        if edef is None:
            from lab.eval.scorer import default_eval
            edef_actual = default_eval(sp)
        else:
            edef_actual = edef

        checks = skill_checks[sname]
        baseline_composite = baselines[sname]

        for ci in checks:
            done += 1
            if done % 50 == 0 or done == total_ablations:
                print(f"  Progress: {done}/{total_ablations}", end="\r")

            ablated_eval = build_ablated_eval(edef_actual, ci.dimension, ci.index)
            try:
                result = score_skill(sp, ablated_eval)
            except Exception as e:
                # If scoring fails with ablated eval, skip
                continue

            delta = result.composite - baseline_composite
            dim_delta = 0.0
            if ci.dimension in result.dimensions and ci.dimension in baseline_dims[sname]:
                dim_delta = result.dimensions[ci.dimension].score - baseline_dims[sname][ci.dimension]

            if abs(delta) > 1e-6 or abs(dim_delta) > 1e-6:
                check_impact[ci.key].append({
                    "skill": sname,
                    "composite_delta": round(delta, 6),
                    "dimension_delta": round(dim_delta, 6),
                })

    print()  # clear progress line

    # Phase 4: Classify checks
    signal_checks = []  # checks that matter
    noise_checks = []   # checks that never change anything

    for key, info in all_check_keys.items():
        impacts = check_impact[key]
        if len(impacts) == 0:
            noise_checks.append(info)
        else:
            signal_checks.append((info, impacts))

    # Sort signal checks by total impact (most impactful first)
    signal_checks.sort(
        key=lambda x: sum(abs(i["composite_delta"]) for i in x[1]),
        reverse=True,
    )

    # Phase 5: Print report
    print("\n" + "=" * 80)
    print("MATCHER ABLATION REPORT")
    print("=" * 80)

    print(f"\nTotal unique checks: {len(all_check_keys)}")
    print(f"Signal checks (removing changes score): {len(signal_checks)}")
    print(f"Noise checks (removing changes nothing): {len(noise_checks)}")

    print("\n--- SIGNAL CHECKS (most impactful first) ---")
    print(f"{'Check':<50} {'Type':<25} {'Dim':<15} {'Skills affected':>15} {'Total |delta|':>14}")
    print("-" * 120)
    for info, impacts in signal_checks:
        total_abs_delta = sum(abs(i["composite_delta"]) for i in impacts)
        desc = info.description[:48]
        print(f"{desc:<50} {info.check_type:<25} {info.dimension:<15} {len(impacts):>15} {total_abs_delta:>14.4f}")

    # Subcategorize noise: universally-passing vs other
    noise_universal = [c for c in noise_checks if c.key in all_pass_checks]
    noise_failing = [c for c in noise_checks if c.key in failing_checks]

    if noise_universal:
        print(f"\n--- UNIVERSALLY PASSING CHECKS ({len(noise_universal)}) ---")
        print("These pass for every skill, so removing them never changes the score.")
        print("They may still serve as guardrails against future regressions.")
        print(f"{'Check':<50} {'Type':<25} {'Dim':<15} {'Skills using':>12}")
        print("-" * 102)
        for info in sorted(noise_universal, key=lambda c: (c.dimension, c.check_type)):
            desc = info.description[:48]
            n_skills = len(check_pass_fail.get(info.key, {}))
            print(f"{desc:<50} {info.check_type:<25} {info.dimension:<15} {n_skills:>12}")

    if noise_failing:
        print(f"\n--- TRUE NOISE CHECKS ({len(noise_failing)}) ---")
        print("These fail for some skills but removing them still doesn't change scores.")
        print("Likely: weight is too low, or other checks in the dimension dominate.")
        print(f"{'Check':<50} {'Type':<25} {'Dim':<15} {'Fails for':>10}")
        print("-" * 100)
        for info in sorted(noise_failing, key=lambda c: (c.dimension, c.check_type)):
            desc = info.description[:48]
            fails = sum(1 for p in check_pass_fail.get(info.key, {}).values() if not p)
            print(f"{desc:<50} {info.check_type:<25} {info.dimension:<15} {fails:>10}")

    # Phase 6: Build JSON output
    results = {
        "summary": {
            "total_skills": len(skill_paths),
            "total_unique_checks": len(all_check_keys),
            "signal_checks": len(signal_checks),
            "noise_checks": len(noise_checks),
        },
        "signal": [
            {
                "key": info.key,
                "check_type": info.check_type,
                "description": info.description,
                "dimension": info.dimension,
                "skills_affected": len(impacts),
                "total_abs_composite_delta": round(sum(abs(i["composite_delta"]) for i in impacts), 6),
                "impacts": impacts,
            }
            for info, impacts in signal_checks
        ],
        "noise": [
            {
                "key": info.key,
                "check_type": info.check_type,
                "description": info.description,
                "dimension": info.dimension,
            }
            for info in sorted(noise_checks, key=lambda c: (c.dimension, c.check_type))
        ],
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nJSON results written to: {OUTPUT_PATH}")


if __name__ == "__main__":
    run_ablation()
