#!/usr/bin/env python3
"""Unified skill scoring engine.

Usage:
    python -m lab.eval.scorer plugins/elixir-phoenix/skills/plan/SKILL.md
    python -m lab.eval.scorer plugins/elixir-phoenix/skills/plan/SKILL.md --eval lab/eval/evals/plan.json
    python -m lab.eval.scorer --all
"""

import argparse
import json
import os
import sys

from lab.eval.schemas import (
    EvalDefinition, EvalDimension, EvalCheck, DimensionResult,
    ScoreRequest, ScoreResult,
)
from lab.eval.dimensions import completeness, accuracy, conciseness, triggering, safety, clarity, specificity, behavioral
from lab.eval.plugins import (
    DEFAULT_PLUGIN, STRUCTURAL_PLUGINS, TRIGGER_KEYWORDS, installed_plugins, plugin_dir, plugin_name_for,
    plugin_root_for, result_key, unknown_plugins,
)

DIMENSION_MODULES = {
    "completeness": completeness,
    "accuracy": accuracy,
    "conciseness": conciseness,
    "triggering": triggering,
    "safety": safety,
    "clarity": clarity,
    "specificity": specificity,
    "behavioral": behavioral,
}

PLUGIN_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "plugins", "elixir-phoenix")


def default_eval(skill_path: str) -> EvalDefinition:
    """Generate a generic eval definition when no skill-specific eval exists."""
    skill_name = os.path.basename(os.path.dirname(skill_path))
    keyword_params = {"min": 3}
    plugin_keywords = TRIGGER_KEYWORDS.get(plugin_name_for(skill_path))
    if plugin_keywords:
        keyword_params["keywords"] = plugin_keywords
    return EvalDefinition(
        skill=skill_name,
        skill_path=skill_path,
        dimensions={
            "completeness": EvalDimension(name="completeness", weight=0.20, checks=[
                EvalCheck(check_type="section_exists", description="Has Iron Laws section", params={"section": "Iron Laws"}),
                EvalCheck(check_type="has_iron_laws", description="Iron Laws has items", params={"min_count": 1}),
                EvalCheck(check_type="frontmatter_field", description="Has name field", params={"field": "name"}),
                EvalCheck(check_type="frontmatter_field", description="Has description field", params={"field": "description"}),
            ]),
            "accuracy": EvalDimension(name="accuracy", weight=0.15, checks=[
                EvalCheck(check_type="valid_skill_refs", description="All skill references valid"),
                EvalCheck(check_type="valid_agent_refs", description="All agent references valid"),
                EvalCheck(check_type="valid_file_refs", description="All reference file paths valid"),
            ]),
            "conciseness": EvalDimension(name="conciseness", weight=0.15, checks=[
                EvalCheck(check_type="line_count", description="Near 100-line target", params={"target": 100, "tolerance": 85}),
                EvalCheck(check_type="max_section_lines", description="No section exceeds 40 lines", params={"max": 40}),
            ]),
            "triggering": EvalDimension(name="triggering", weight=0.15, checks=[
                EvalCheck(check_type="description_length", description="Description under 250-char plugin listing budget", params={"min": 50, "max": 250}),
                EvalCheck(check_type="description_keywords", description="Enough trigger keywords", params=keyword_params),
            ]),
            "safety": EvalDimension(name="safety", weight=0.10, checks=[
                EvalCheck(check_type="has_iron_laws", description="Has Iron Laws", params={"min_count": 1}),
                EvalCheck(check_type="no_dangerous_patterns", description="No unsafe patterns"),
            ]),
            "clarity": EvalDimension(name="clarity", weight=0.10, checks=[
                EvalCheck(check_type="action_density", description="High action density", params={"min_ratio": 0.25}),
                EvalCheck(check_type="no_duplication", description="No cross-section duplication"),
                EvalCheck(check_type="workflow_step_coverage", description="No missing workflow steps"),
            ]),
            "specificity": EvalDimension(name="specificity", weight=0.10, checks=[
                EvalCheck(check_type="specificity_ratio", description="Concrete over vague", params={"min_ratio": 0.15}),
                EvalCheck(check_type="has_examples", description="Has code examples"),
                EvalCheck(check_type="description_structure", description="Description has what+when"),
            ]),
            "behavioral": EvalDimension(name="behavioral", weight=0.10, checks=[]),
        },
    )


def score_skill(skill_path: str, eval_def: EvalDefinition | None = None) -> ScoreResult:
    """Score a skill across all dimensions. Returns ScoreResult; composite 0.0-1.0.
    Backwards-compat: ScoreResult.to_dict() emits the legacy SkillScore shape.
    """
    request = ScoreRequest(
        target_path=os.path.abspath(skill_path),
        target_kind="skill",
        eval_def=eval_def,
        plugin_root=plugin_root_for(skill_path),
    )
    return score_skill_request(request)


def score_skill_request(request: ScoreRequest) -> ScoreResult:
    """Canonical entrypoint — accept ScoreRequest, return ScoreResult."""
    import time
    start = time.time()
    skill_path = request.target_path
    if not os.path.isfile(skill_path):
        raise FileNotFoundError(f"Skill file not found: {skill_path}")

    with open(skill_path) as f:
        content = f.read()

    eval_def = request.eval_def or default_eval(skill_path)
    plugin_root = request.plugin_root or os.path.abspath(PLUGIN_ROOT)

    dimensions: dict[str, DimensionResult] = {}
    total_weight = 0.0
    for dim_name, dim_def in eval_def.dimensions.items():
        module = DIMENSION_MODULES.get(dim_name)
        if module is None:
            continue
        result = module.score(content, dim_def, skill_path=skill_path, plugin_root=plugin_root)
        dimensions[dim_name] = result
        total_weight += dim_def.weight

    if total_weight == 0:
        composite = 0.0
    else:
        composite = sum(
            eval_def.dimensions[name].weight * dim.score
            for name, dim in dimensions.items()
            if name in eval_def.dimensions
        ) / total_weight

    skill_name = (
        request.target_name
        or eval_def.skill
        or os.path.basename(os.path.dirname(skill_path))
    )

    return ScoreResult(
        target_name=skill_name,
        target_path=skill_path,
        target_kind="skill",
        composite=composite,
        dimensions=dimensions,
        duration=time.time() - start,
    )


def find_all_skills(plugins: tuple[str, ...] = (DEFAULT_PLUGIN,)) -> list[str]:
    """Find all SKILL.md files in the given plugins (default: elixir-phoenix only)."""
    paths = []
    for plugin in plugins:
        skills_dir = os.path.join(plugin_dir(plugin), "skills")
        if not os.path.isdir(skills_dir):
            continue
        for name in sorted(os.listdir(skills_dir)):
            skill_md = os.path.join(skills_dir, name, "SKILL.md")
            if os.path.isfile(skill_md):
                paths.append(skill_md)
    return paths


def find_eval(skill_name: str, skill_path: str | None = None) -> str | None:
    """Find the eval definition for a skill.

    elixir-phoenix skills use `evals/{skill}.json`; other plugins use
    `evals/{plugin}-{skill}.json`, so `rewrite/verify` never picks up phx's `verify.json`.
    """
    evals_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evals")
    plugin = plugin_name_for(skill_path) if skill_path else DEFAULT_PLUGIN
    filename = f"{skill_name}.json" if plugin == DEFAULT_PLUGIN else f"{plugin}-{skill_name}.json"
    eval_path = os.path.join(evals_dir, filename)
    if os.path.isfile(eval_path):
        return eval_path
    return None


def main():
    parser = argparse.ArgumentParser(description="Score plugin skills across 5 dimensions")
    parser.add_argument("skill_path", nargs="?", help="Path to SKILL.md file")
    parser.add_argument("--eval", help="Path to eval definition JSON")
    parser.add_argument("--all", action="store_true", help="Score all skills")
    parser.add_argument("--plugin", action="append",
                        help="Plugin directory to score with --all (repeatable; default: every structural plugin)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args()

    if args.plugin:
        unknown = unknown_plugins(args.plugin)
        if unknown:
            parser.error(
                f"unknown plugin(s): {', '.join(unknown)}; installed: {', '.join(installed_plugins())}"
            )
    if args.all:
        results = {}
        skill_paths = find_all_skills(tuple(args.plugin or STRUCTURAL_PLUGINS))
        if args.plugin and not skill_paths:
            parser.error(f"no skills found in plugin(s): {', '.join(args.plugin)}")
        for skill_path in skill_paths:
            skill_name = os.path.basename(os.path.dirname(skill_path))
            eval_path = find_eval(skill_name, skill_path)
            eval_def = EvalDefinition.from_file(eval_path) if eval_path else None
            score = score_skill(skill_path, eval_def)
            results[result_key(skill_path, skill_name)] = score.to_dict()
        output = json.dumps(results, indent=2 if args.pretty else None)
        print(output)
    elif args.skill_path:
        eval_def = None
        if args.eval:
            eval_def = EvalDefinition.from_file(args.eval)
        else:
            skill_name = os.path.basename(os.path.dirname(args.skill_path))
            eval_path = find_eval(skill_name, args.skill_path)
            if eval_path:
                eval_def = EvalDefinition.from_file(eval_path)

        score = score_skill(args.skill_path, eval_def)
        output = json.dumps(score.to_dict(), indent=2 if args.pretty else None)
        print(output)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
