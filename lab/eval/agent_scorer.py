#!/usr/bin/env python3
"""Agent scoring engine — evaluates plugin agents across 5 dimensions.

Usage:
    python3 -m lab.eval.agent_scorer plugins/elixir-phoenix/agents/elixir-reviewer.md
    python3 -m lab.eval.agent_scorer --all
    python3 -m lab.eval.agent_scorer --all --pretty
"""

import argparse
import json
import os
import sys

from lab.eval.schemas import SkillScore, DimensionResult, AssertionResult
from lab.eval.matchers import (
    parse_frontmatter, frontmatter_field, description_length, line_count, max_section_lines,
    no_dangerous_patterns,
)
from lab.eval.agent_matchers import (
    agent_tools_valid, agent_readonly_enforced, agent_bypass_permissions,
    agent_model_appropriate, agent_has_skills, ORCHESTRATOR_NAMES,
)

PLUGINS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "plugins")
PLUGIN_ROOT = os.path.join(PLUGINS_DIR, "elixir-phoenix")


def score_agent(agent_path: str) -> SkillScore:
    """Score an agent across 5 dimensions."""
    agent_path = os.path.abspath(agent_path)
    with open(agent_path) as f:
        content = f.read()

    fm = parse_frontmatter(content)
    agent_name = fm.get("name", os.path.basename(agent_path).replace(".md", ""))
    plugin_root = os.path.abspath(PLUGIN_ROOT)

    # Determine if orchestrator (higher line limits)
    is_orchestrator = agent_name in ORCHESTRATOR_NAMES

    dimensions = {}

    # --- Completeness (0.25) ---
    completeness_checks = [
        ("frontmatter-name", "Has name", *frontmatter_field(content, field="name")),
        ("frontmatter-desc", "Has description", *frontmatter_field(content, field="description")),
        ("frontmatter-tools", "Has tools", *frontmatter_field(content, field="tools")),
        ("frontmatter-model", "Has model", *frontmatter_field(content, field="model")),
        ("frontmatter-effort", "Has effort", *frontmatter_field(content, field="effort")),
        ("frontmatter-perm", "Has permissionMode", *frontmatter_field(content, field="permissionMode")),
    ]
    dimensions["completeness"] = DimensionResult.from_assertions("completeness", [
        AssertionResult(id=cid, check_type="frontmatter_field", description=desc, passed=p, evidence=e)
        for cid, desc, p, e in completeness_checks
    ])

    # --- Accuracy (0.25) ---
    accuracy_assertions = []
    p, e = agent_has_skills(content, plugin_root=plugin_root)
    accuracy_assertions.append(AssertionResult(id="acc-skills", check_type="agent_has_skills",
        description="Preloaded skills exist", passed=p, evidence=e))
    p, e = agent_tools_valid(content)
    accuracy_assertions.append(AssertionResult(id="acc-tools", check_type="agent_tools_valid",
        description="Tools are valid", passed=p, evidence=e))
    dimensions["accuracy"] = DimensionResult.from_assertions("accuracy", accuracy_assertions)

    # --- Conciseness (0.15) ---
    target = 535 if is_orchestrator else 300
    tolerance = 65 if is_orchestrator else 65
    p_lc, e_lc = line_count(content, target=target, tolerance=tolerance, skill_path=agent_path)
    # Agents have reference checklists (Red Flags) and inline subagent prompts
    # Orchestrators embed ~80 lines × N agents = need 100+ line sections
    p_ms, e_ms = max_section_lines(content, max=100 if is_orchestrator else 75)
    dimensions["conciseness"] = DimensionResult.from_assertions("conciseness", [
        AssertionResult(id="conc-lines", check_type="line_count",
            description=f"Under {target + tolerance} lines", passed=p_lc, evidence=e_lc),
        AssertionResult(id="conc-sections", check_type="max_section_lines",
            description="No oversized sections", passed=p_ms, evidence=e_ms),
    ])

    # --- Safety (0.20) ---
    safety_assertions = []
    p, e = agent_bypass_permissions(content)
    safety_assertions.append(AssertionResult(id="safe-perm", check_type="agent_bypass_permissions",
        description="bypassPermissions set", passed=p, evidence=e))
    p, e = agent_readonly_enforced(content)
    safety_assertions.append(AssertionResult(id="safe-readonly", check_type="agent_readonly_enforced",
        description="Read-only agents block writes", passed=p, evidence=e))
    # no_dangerous_patterns already filters Iron Laws sections and table rows (from matchers.py)
    p, e = no_dangerous_patterns(content)
    safety_assertions.append(AssertionResult(id="safe-patterns", check_type="no_dangerous_patterns",
        description="No dangerous patterns", passed=p, evidence=e))
    dimensions["safety"] = DimensionResult.from_assertions("safety", safety_assertions)

    # --- Consistency (0.15) ---
    consistency_assertions = []
    p, e = agent_model_appropriate(content)
    consistency_assertions.append(AssertionResult(id="cons-model", check_type="agent_model_appropriate",
        description="Model matches effort", passed=p, evidence=e))
    p, e = description_length(content, min=30, max=400)
    consistency_assertions.append(AssertionResult(id="cons-desc-len", check_type="description_length",
        description="Description length OK", passed=p, evidence=e))
    dimensions["consistency"] = DimensionResult.from_assertions("consistency", consistency_assertions)

    # --- Compute composite ---
    weights = {"completeness": 0.25, "accuracy": 0.25, "conciseness": 0.15, "safety": 0.20, "consistency": 0.15}
    total_weight = sum(weights.values())
    composite = sum(weights[d] * dim.score for d, dim in dimensions.items() if d in weights) / total_weight

    return SkillScore(
        skill_name=agent_name,
        skill_path=agent_path,
        composite=composite,
        dimensions=dimensions,
    )


def find_all_agents(plugin_name: str | None = None) -> list[str]:
    """Find all agent .md files in a plugin."""
    if plugin_name:
        agents_dir = os.path.join(PLUGINS_DIR, plugin_name, "agents")
    else:
        agents_dir = os.path.join(PLUGIN_ROOT, "agents")
    if not os.path.isdir(agents_dir):
        return []
    return sorted(
        os.path.join(agents_dir, f)
        for f in os.listdir(agents_dir)
        if f.endswith(".md")
    )


def main():
    parser = argparse.ArgumentParser(description="Score plugin agents across 5 dimensions")
    parser.add_argument("agent_path", nargs="?", help="Path to agent .md file")
    parser.add_argument("--all", action="store_true", help="Score all agents")
    parser.add_argument("--plugin", help="Plugin name (default: elixir-phoenix)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print output")
    args = parser.parse_args()

    if args.all:
        results = {}
        for path in find_all_agents(args.plugin):
            name = os.path.basename(path).replace(".md", "")
            score = score_agent(path)
            results[name] = score.to_dict()
            status = "OK" if score.composite >= 0.95 else "NEEDS WORK"
            print(f"  {name}: {score.composite:.3f} [{status}]", flush=True)
        avg = sum(r["composite"] for r in results.values()) / len(results) if results else 0
        perfect = sum(1 for r in results.values() if r["composite"] >= 0.999)
        print(f"\n{len(results)} agents, {perfect} perfect, avg {avg:.3f}")
    elif args.agent_path:
        score = score_agent(args.agent_path)
        print(json.dumps(score.to_dict(), indent=2 if args.pretty else None))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
